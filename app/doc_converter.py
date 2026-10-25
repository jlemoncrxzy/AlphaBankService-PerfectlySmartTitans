"""Конвертация legacy .doc в .docx для шаблонов отчёта.

Сначала пробуем Microsoft Word (COM) — он есть на типовой рабочей машине
Windows. Если Word недоступен, пробуем LibreOffice. Если не удалось ни то,
ни другое, пользователю возвращается понятная ошибка с просьбой сохранить
шаблон в DOCX.
"""
import shutil
import subprocess
import tempfile
from pathlib import Path


class DocConversionError(RuntimeError):
    """Не удалось преобразовать DOC в DOCX."""


def _libreoffice_path() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for candidate in (
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/usr/bin/soffice",
        "/usr/local/bin/soffice",
        "/opt/libreoffice/program/soffice",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _convert_with_word(data: bytes) -> bytes | None:
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "template.doc"
        target = Path(temp_dir) / "template.docx"
        source.write_bytes(data)

        pythoncom.CoInitialize()
        word = None
        document = None
        try:
            word = win32com.client.DispatchEx("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0
            # msoAutomationSecurityForceDisable — не запускаем макросы из шаблона.
            word.AutomationSecurity = 3
            document = word.Documents.Open(
                str(source),
                ReadOnly=True,
                AddToRecentFiles=False,
                ConfirmConversions=False,
            )
            document.SaveAs2(str(target), FileFormat=16)  # wdFormatDocumentDefault (DOCX)
        except Exception:
            return None
        finally:
            if document is not None:
                try:
                    document.Close(False)
                except Exception:
                    pass
            if word is not None:
                try:
                    word.Quit()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

        return target.read_bytes() if target.exists() else None


def _convert_with_libreoffice(data: bytes) -> bytes | None:
    office = _libreoffice_path()
    if not office:
        return None

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "template.doc"
        target = Path(temp_dir) / "template.docx"
        source.write_bytes(data)

        try:
            result = subprocess.run(
                [
                    office,
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    temp_dir,
                    str(source),
                ],
                capture_output=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        if result.returncode != 0 or not target.exists():
            return None
        return target.read_bytes()


def convert_doc_to_docx(data: bytes) -> bytes:
    if not data:
        raise DocConversionError("Файл шаблона пуст")

    converted = _convert_with_word(data)
    if converted is None:
        converted = _convert_with_libreoffice(data)
    if converted is None:
        raise DocConversionError(
            "Не удалось прочитать DOC-файл. Установите Microsoft Word или LibreOffice "
            "либо сохраните шаблон в формате DOCX."
        )
    return converted
