"""API для выгрузки DOCX-отчёта по компании."""
import io
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..doc_converter import DocConversionError, convert_doc_to_docx
from ..report_builder import build_company_report, safe_filename

router = APIRouter(prefix="/api", tags=["reports"])

MAX_TEMPLATE_BYTES = 15 * 1024 * 1024
DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.post("/companies/{company_id}/report")
def company_report(
    company_id: int,
    template: UploadFile = File(...),
    title: str = Form("Отчёт по компании"),
    db: Session = Depends(get_db),
):
    filename = (template.filename or "").lower()
    if not filename.endswith((".doc", ".docx")):
        raise HTTPException(400, "Шаблон должен быть файлом DOC или DOCX")

    template_bytes = template.file.read()
    if not template_bytes:
        raise HTTPException(400, "Файл шаблона пуст")
    if len(template_bytes) > MAX_TEMPLATE_BYTES:
        raise HTTPException(400, "Файл шаблона больше 15 МБ")

    report_title = (title or "").strip() or "Отчёт по компании"

    try:
        docx_bytes = (
            convert_doc_to_docx(template_bytes)
            if filename.endswith(".doc")
            else template_bytes
        )
        report_bytes = build_company_report(
            db=db,
            client_id=company_id,
            template_bytes=docx_bytes,
            title=report_title,
        )
    except ValueError as error:
        raise HTTPException(404, str(error)) from None
    except DocConversionError as error:
        raise HTTPException(400, str(error)) from None
    except Exception:
        raise HTTPException(
            400,
            "Не удалось собрать отчёт. Проверьте, что шаблон является корректным DOC/DOCX-файлом.",
        ) from None

    download_name = f"{safe_filename(report_title, 'company-report')}.docx"
    headers = {
        "Content-Disposition": (
            "attachment; filename=\"company-report.docx\"; "
            f"filename*=UTF-8''{quote(download_name)}"
        )
    }
    return StreamingResponse(
        io.BytesIO(report_bytes),
        media_type=DOCX_MEDIA_TYPE,
        headers=headers,
    )
