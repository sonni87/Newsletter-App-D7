"""
Web-Scraper mit Retry-Logik und HTML-Bereinigung.
Unterstützt HTML-Seiten, PDFs werden abgelehnt.
"""

import logging
import re
from typing import Optional, Dict, Any

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "de,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

REMOVE_SELECTORS = [
    "script", "style", "nav", "header", "footer", "aside",
    ".navigation", ".menu", ".sidebar", ".advertisement", ".cookie",
    '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]'
]


def create_session_with_retries(
    retries: int = 3,
    backoff_factor: float = 0.5,
    status_forcelist: tuple = (500, 502, 503, 504)
) -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    return session


def fetch_html(url: str, timeout: int = 30) -> Optional[str]:
    session = create_session_with_retries()
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            logger.warning(f"PDF-Datei erkannt, wird nicht unterstützt: {url}")
            return None

        if response.encoding is None:
            response.encoding = "utf-8"

        return response.text

    except requests.exceptions.RequestException as e:
        logger.error(f"Fehler beim Abrufen von {url}: {e}")
        return None


def extract_title_from_html(html: str) -> Optional[str]:
    """Extrahiert den wahrscheinlichsten Ausschreibungstitel aus dem HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Priorität 1: H1 mit aussagekräftigem Text
    for h1 in soup.find_all("h1"):
        text = h1.get_text(strip=True)
        if text and len(text) > 20:
            # Bevorzuge Titel mit Schlüsselwörtern
            if any(w in text.lower() for w in ["richtlinie", "bekanntmachung", "förderung", "ausschreibung"]):
                return text
            # Fallback: erstes langes H1
            return text

    # Priorität 2: H2 mit Schlüsselwörtern
    for h2 in soup.find_all("h2"):
        text = h2.get_text(strip=True)
        if len(text) > 30 and any(w in text.lower() for w in ["richtlinie", "bekanntmachung", "förder"]):
            return text

    # Priorität 3: HTML-Title (nur wenn nicht generisch)
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
        if title and not any(g in title for g in ["Homepage", "Startseite", "Übersicht"]):
            return title

    return None


def clean_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for selector in REMOVE_SELECTORS:
        for element in soup.select(selector):
            element.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def scrape_url(url: str) -> Dict[str, Any]:
    result = {
        "url": url,
        "title": None,
        "text": None,
        "status": "error",
        "error": None
    }

    if url.lower().endswith(".pdf"):
        result["error"] = "PDF-Dateien werden derzeit nicht unterstützt. Bitte verwenden Sie die HTML-Ausschreibungsseite."
        return result

    html = fetch_html(url)
    if html is None:
        result["error"] = "HTML konnte nicht geladen werden (möglicherweise PDF oder Serverfehler)."
        return result

    try:
        result["title"] = extract_title_from_html(html) or "Keine Angabe"
        result["text"] = clean_html(html)
        if not result["text"] or len(result["text"]) < 100:
            result["error"] = "Zu wenig Textinhalt"
        else:
            result["status"] = "success"
            logger.info(f"Erfolgreich gescraped: {url}")
    except Exception as e:
        logger.exception(f"Fehler beim Parsen von {url}")
        result["error"] = str(e)

    return result
