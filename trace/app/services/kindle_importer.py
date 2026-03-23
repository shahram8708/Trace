import csv
from typing import List, Dict


def parse_kindle_csv(file_bytes: bytes) -> List[Dict[str, object]]:
    if not file_bytes:
        raise ValueError("Could not read this file as a CSV. Please ensure you're uploading the correct Kindle highlights export file.")
    decoded = None
    try:
        decoded = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = file_bytes.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise ValueError("Could not read this file as a CSV. Please ensure you're uploading the correct Kindle highlights export file.") from exc

    reader = csv.DictReader(decoded.splitlines())
    if not reader.fieldnames:
        raise ValueError("Could not read this file as a CSV. Please ensure you're uploading the correct Kindle highlights export file.")

    field_map = None
    headers = [h.strip() for h in reader.fieldnames]
    if {"Book Title", "Book Author", "Highlight"}.issubset(headers):
        field_map = {"title": "Book Title", "author": "Book Author", "highlight": "Highlight"}
    elif {"Title", "Author", "Highlight"}.issubset(headers):
        field_map = {"title": "Title", "author": "Author", "highlight": "Highlight"}
    else:
        raise ValueError("No valid highlights found in this file. Please ensure you're uploading a Kindle highlights CSV export.")

    books = {}
    for row in reader:
        title = (row.get(field_map["title"], "") or "").strip()
        author = (row.get(field_map["author"], "") or "").strip()
        highlight = (row.get(field_map["highlight"], "") or "").strip()
        if not title or len(highlight) < 30:
            continue
        key = title.lower()
        book_entry = books.setdefault(
            key,
            {"title": title, "author": author, "highlights": [], "highlight_count": 0},
        )
        if highlight in book_entry["highlights"]:
            continue
        book_entry["highlights"].append(highlight)
        book_entry["highlight_count"] = len(book_entry["highlights"])

    if not books:
        raise ValueError("No valid highlights found in this file. Please ensure you're uploading a Kindle highlights CSV export.")

    sorted_books = sorted(books.values(), key=lambda b: b["highlight_count"], reverse=True)
    return sorted_books


def build_kindle_source_text(book_data: Dict[str, object]) -> str:
    title = str(book_data.get("title", "Untitled"))
    highlights = book_data.get("highlights", []) or []
    lines = [title, ""]
    for idx, highlight in enumerate(highlights, start=1):
        lines.append(f"{idx}. {highlight}")
    return "\n".join(lines)
