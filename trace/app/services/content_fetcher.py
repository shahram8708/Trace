import ipaddress
from urllib.parse import urlparse
import trafilatura


def is_url_safe(url: str) -> bool:
    parsed = urlparse(url or "")
    host = parsed.hostname or ""
    if not host:
        return False
    host_lower = host.lower()
    if host_lower in {"localhost", "127.0.0.1", "0.0.0.0"}:
        return False
    try:
        ip = ipaddress.ip_address(host_lower)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        if host_lower.startswith("10.") or host_lower.startswith("192.168."):
            return False
        if host_lower.startswith("172."):
            try:
                second_octet = int(host_lower.split(".")[1])
                if 16 <= second_octet <= 31:
                    return False
            except (IndexError, ValueError):
                pass
    return True


def fetch_article_from_url(url: str) -> dict:
    if not is_url_safe(url):
        raise ValueError("Could not access this URL. Please check that it is publicly accessible and not behind a login wall.")
    try:
        downloaded = trafilatura.fetch_url(url)
    except Exception as exc:  # pragma: no cover
        raise ValueError("Unable to fetch the URL right now. Please try again.") from exc

    if not downloaded:
        raise ValueError("Could not access this URL. Please check that it is publicly accessible and not behind a login wall.")

    try:
        extracted_text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
    except Exception as exc:  # pragma: no cover
        raise ValueError("Could not extract readable content from this URL. The page may be unsupported.") from exc

    if not extracted_text or len(extracted_text.strip()) < 150:
        raise ValueError(
            "Could not extract readable content from this URL. The page may be a video, image, or dynamically rendered content not accessible to text extraction."
        )

    metadata = trafilatura.extract_metadata(downloaded)
    title = getattr(metadata, "title", None) if metadata else None
    author = getattr(metadata, "author", None) if metadata else None
    cover_image = None
    if metadata and getattr(metadata, "image", None):
        cover_image = metadata.image

    word_count = len(extracted_text.split())
    return {
        "title": title or url,
        "text": extracted_text,
        "author": author,
        "url": url,
        "word_count": word_count,
        "cover_image_url": cover_image,
    }
