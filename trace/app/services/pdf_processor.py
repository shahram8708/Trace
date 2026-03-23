import os
import io
from typing import Dict
import pdfplumber
from pdfminer.pdfparser import PDFSyntaxError


def validate_pdf_file(file_storage) -> bool:
    max_mb = int(os.getenv("MAX_PDF_SIZE_MB", 20))
    file_storage.stream.seek(0, io.SEEK_END)
    size_bytes = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size_bytes > max_mb * 1024 * 1024:
        raise ValueError(f"PDF file size exceeds the {max_mb}MB limit.")

    magic = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    if not magic.startswith(b"%PDF-"):
        raise ValueError("The uploaded file does not appear to be a valid PDF.")
    return True


def extract_text_from_pdf(file_path: str) -> Dict[str, object]:
    try:
        with pdfplumber.open(file_path) as pdf:
            texts = []
            for page in pdf.pages:
                page_text = page.extract_text() if page else None
                if page_text:
                    texts.append(page_text.strip())
            joined = "\n\n".join(texts)
            if len(joined.strip()) < 100:
                raise ValueError(
                    "This PDF does not contain extractable text. It may be a scanned document or image-based PDF. Text extraction is not supported for scanned PDFs."
                )
            word_count = len(joined.split())
            return {
                "text": joined,
                "page_count": len(pdf.pages),
                "word_count": word_count,
            }
    except PDFSyntaxError as exc:
        raise ValueError("This file does not appear to be a valid PDF or may be corrupted.") from exc
    except Exception as exc:  # pragma: no cover
        raise ValueError("This file does not appear to be a valid PDF or may be corrupted.") from exc
