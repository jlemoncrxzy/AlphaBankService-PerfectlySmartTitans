"""Скрипт для загрузки PDF и нарезки их на чанки (RAG)."""
import os
import datetime
from pathlib import Path
from pypdf import PdfReader
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
    print(f"Найдено {len(pdf_files)} PDF-файлов. Начинаем нарезку...")
    
    # Очищаем старые чанки и аналитику, чтобы не дублировать
    db.query(DocumentChunk).delete()
    db.commit()

    for file_path in pdf_files:
        filename = file_path.name
        try:
            reader = PdfReader(file_path)
            text_parts = []
            # Читаем ВЕСЬ текст (все страницы)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = " ".join(" ".join(text_parts).split())
            if not full_text:
                continue

            meta = _infer_metadata(filename)

            # 1. Сохраняем общую карточку аналитики (для UI)
            analytic = BankAnalytic(
                title=filename, body=full_text[:1000] + "...", category=meta["category"],
                published_at=datetime.datetime.utcnow(), industries=meta["industries"],
                regions=["Россия"], magnitude=0.8
            )
            db.add(analytic)

            # 2. Нарезаем на чанки и сохраняем для RAG
            chunks = chunk_text(full_text, CHUNK_SIZE, CHUNK_OVERLAP)
            for ch in chunks:
                db.add(DocumentChunk(
                    doc_title=filename, category=meta["category"],
                    industries=meta["industries"], text=ch
                ))
            
            print(f"[+] Загружен: {filename} (нарезано {len(chunks)} чанков)")

        except Exception as e:
            print(f"[!] Ошибка в {filename}: {e}")

    db.commit()
    db.close()
    print("✅ База знаний из PDF готова!")

if __name__ == "__main__":
    run_pdf_ingestion()