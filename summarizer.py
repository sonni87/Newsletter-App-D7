"""
Kernfunktion: URLs scrapen, LLM-Zusammenfassung im Newsletter-Format generieren.
"""

import logging
from typing import List, Dict, Any, Optional

from scraper import scrape_url
from extractors import extract_deadline, extract_funding, extract_institution
from llm_client import LLMClient, KIConnectError

logger = logging.getLogger(__name__)

# Prompt exakt zugeschnitten auf das Format der Newsletter des Dezernats Forschungsmanagement
SUMMARY_PROMPT_TEMPLATE = """
Du bist Experte für Forschungsförderung und erstellst Einträge für einen Fördernewsletter einer Universität.
Analysiere den folgenden Text einer Förderausschreibung und extrahiere die Informationen **ausschließlich im folgenden Format**.

TEXT:
{text}

FORMAT (exakt so antworten, keine zusätzlichen Erklärungen):

**Titel der Ausschreibung:** (offizieller Titel, falls nicht erkennbar: "Keine Angabe")
**Förderinstitution:** {institution}
**Ziel / Aim:** (1–2 Sätze, was wird gefördert? Ggf. auf Deutsch und Englisch, je nach Ausschreibung)
**Zielgruppe / Target group:** (wer kann sich bewerben?)
**Dauer / Duration:** (Projektlaufzeit)
**Förderhöhe / Funding:** {funding}
**Fristende / Deadline:** {deadline}
**Weitere Informationen / Further information:** (URL oder Hinweis "siehe Webseite")
**INTERNES VERFAHREN:** (NUR wenn im Text ein Hinweis auf interne Antragsverfahren, rechtsverbindliche Unterschrift etc. vorhanden ist, sonst dieses Feld weglassen)

Wichtig:
- Halte dich exakt an die Feldbezeichnungen.
- Wenn eine Information nicht im Text steht, schreibe "Keine Angabe".
- Verwende für zweisprachige Ausschreibungen beide Sprachen (z.B. "Ziel / Aim:").
"""


def _clean_summary_output(raw_summary: str, url: str) -> str:
    """Bereinigt und validiert die LLM-Ausgabe."""
    # Entferne eventuelle Markdown-Formatierungsreste
    lines = raw_summary.strip().split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith('**') and ':**' in line:
            cleaned_lines.append(line)
        elif line and not line.startswith('**'):
            # Inhalt gehört zur vorherigen Überschrift
            if cleaned_lines:
                cleaned_lines[-1] += ' ' + line
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)
    
    cleaned = '\n'.join(cleaned_lines)
    
    # Füge Quelle hinzu, falls nicht vorhanden
    if "Weitere Informationen" not in cleaned and "Further information" not in cleaned:
        cleaned += f"\n**Weitere Informationen:** {url}"
    
    return cleaned


def summarize_urls(urls: List[str], client: Optional[LLMClient] = None) -> List[Dict[str, Any]]:
    if client is None:
        client = LLMClient()

    try:
        client._ensure_api_key()
    except KIConnectError as e:
        raise KIConnectError("Kein API-Key konfiguriert.") from e

    if not client.check_connection():
        raise KIConnectError("Keine Verbindung zur LLM-API möglich.")

    results = []

    for url in urls:
        logger.info(f"Verarbeite {url}")
        result = {
            "url": url,
            "title": None,
            "summary": None,
            "deadline": None,
            "funding": None,
            "institution": None,
            "status": "error",
            "error": None
        }

        scraped = scrape_url(url)
        if scraped["status"] != "success":
            result["error"] = scraped.get("error", "Scraping fehlgeschlagen")
            results.append(result)
            continue

        text = scraped["text"]
        result["title"] = scraped["title"]

        if not text or len(text) < 200:
            result["error"] = "Zu wenig Textinhalt"
            results.append(result)
            continue

        # Extraktion mit den verbesserten Extractors
        deadline = extract_deadline(text)
        funding = extract_funding(text)
        institution = extract_institution(text)

        result["deadline"] = deadline
        result["funding"] = funding
        result["institution"] = institution

        # Text kürzen für LLM-Kontext
        max_text_length = 8000
        text_snippet = text[:max_text_length] + ("..." if len(text) > max_text_length else "")

        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            text=text_snippet,
            institution=institution or "Unbekannt",
            deadline=deadline or "Keine Angabe",
            funding=funding or "Keine Angabe"
        )

        try:
            raw_summary = client.generate(prompt, temperature=0.1, max_tokens=800)
            cleaned_summary = _clean_summary_output(raw_summary, url)
            result["summary"] = cleaned_summary
            result["status"] = "success"
        except KIConnectError as e:
            result["error"] = f"LLM-Fehler: {e}"
            logger.error(f"LLM-Fehler für {url}: {e}")
        except Exception as e:
            result["error"] = f"Unerwarteter Fehler: {e}"
            logger.exception(f"Unerwarteter Fehler bei {url}")

        results.append(result)

    return results
