"""Скрипт для загрузки PDF. Сначала пробует текстовый слой, если его нет — включает AI-OCR."""
import os
import datetime
import io
from pathlib import Path
import pdfplumber
import fitz  # PyMuPDF для рендера картинок
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session
from .database import SessionLocal, engine, Base
from .models import BankAnalytic, DocumentChunk

PDF_DIR = "data/raw/pdfs"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150

def _infer_metadata(filename: str) -> dict:
    name_lower = filename.lower()
    category = "Макроэкономика"
    industries = ["Макро"]
    if "steel" in name_lower or "metal" in name_lower:
        category, industries = "Металлургия", ["Металлургия", "Добыча"]
    elif "gold" in name_lower:
        category, industries = "Драгоценные металлы", ["Добыча", "Металлургия"]
    elif "inflation" in name_lower or "macro" in name_lower or "consumption" in name_lower:
        category, industries = "Макроэкономика", ["Ритейл", "Финансы", "Макро"]
    elif "fi_strategy" in name_lower:
        category, industries = "Финансовые рынки", ["Финансы", "Инвестиции"]
    return {"category": category, "industries": industries}

def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

def run_pdf_ingestion():
    if not os.path.exists(PDF_DIR):
        os.makedirs(PDF_DIR)
        return

    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    pdf_files = list(Path(PDF_DIR).glob("*.pdf"))
    print(f"Найдено {len(pdf_files)} PDF-файлов.")
    
    # Инициализация AI-OCR
    print("Инициализация AI-OCR (easyocr)...")
    import easyocr
    reader = easyocr.Reader(['ru', 'en'], gpu=False)

    # DocumentChunk можно пересобрать полностью, а BankAnalytic обновляем
    # по названию файла: ID документов используются в event_insights,
    # и перезапись «с нуля» ломала бы связь инсайтов с источниками.
    db.query(DocumentChunk).delete()
    db.commit()

    for file_path in pdf_files:
        filename = file_path.name
        full_text = ""
        
        # 1. Пытаемся прочитать текстовый слой
        try:
            with pdfplumber.open(file_path) as pdf:
                text_parts = [page.extract_text() for page in pdf.pages if page.extract_text()]
            full_text = " ".join(" ".join(text_parts).split())
        except Exception:
            pass
            
        # 2. Если текста нет (скан) — используем AI OCR
        if not full_text or len(full_text) < 50:
            print(f"[*] {filename} — скан. Распознаем через AI (это может занять время)...")
            full_text = ""
            doc = fitz.open(file_path)
            text_parts = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(dpi=150)
                img_data = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_data))
                
                result = reader.readtext(np.array(img), detail=0, paragraph=True)
                text_parts.append(" ".join(result))
                print(f"    - Страница {i+1}/{len(doc)} распознана")
            doc.close()
            full_text = " ".join(" ".join(text_parts).split())
            
        if not full_text or len(full_text) < 50:
            print(f"[!] Не удалось распознать {filename}.")
            continue

        meta = _infer_metadata(filename)
        analytic = db.query(BankAnalytic).filter(BankAnalytic.title == filename).first()
        if analytic:
            analytic.body = full_text[:1000] + "..."
            analytic.category = meta["category"]
            analytic.industries = meta["industries"]
            analytic.regions = ["Россия"]
            analytic.magnitude = 0.8
        else:
            db.add(BankAnalytic(
                title=filename, body=full_text[:1000] + "...", category=meta["category"],
                published_at=datetime.datetime.utcnow(), industries=meta["industries"],
                regions=["Россия"], magnitude=0.8
            ))

        chunks = chunk_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
        for ch in chunks:
            db.add(DocumentChunk(
                doc_title=filename, category=meta["category"],
                industries=meta["industries"], text=ch
            ))
        
        print(f"[+] Загружен: {filename} (нарезано {len(chunks)} чанков)")

    db.commit()
    db.close()
    print("✅ База знаний из PDF готова!")

if __name__ == "__main__":
    run_pdf_ingestion()