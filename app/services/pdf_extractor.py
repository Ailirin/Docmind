from pathlib import Path

import fitz


def extract_text_from_pdf(storage_path: str) -> str:
    """
    Достает текст из PDF через PyMuPDF
    """
    path = Path(storage_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {storage_path}")

    parts: list[str] = []

    with fitz.open(path) as doc:
        for page in doc:
            text = page.get_text("text") or ""
            text = text.strip()
            if text:
                parts.append(text)

    combined = "\n\n".join(parts)
    return " ".join(combined.split())
