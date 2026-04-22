"""
Kernfunktion: URLs scrapen, LLM-Zusammenfassung im D7-Newsletter-Format generieren.
"""

import logging
from typing import List, Dict, Any, Optional

from scraper import scrape_url
from extractors import extract_deadline, extract_funding, extract_institution
from llm_client import LLMClient, KIConnectError

logger = logging.getLogger(__name__)

LLM_PROMPT = """
Analysiere den Text einer Förderausschreibung und extrahiere die folgenden Informationen knapp und präzise.

TEXT:
{text}

1. Ziel der Förderung: (max. 2 Sätze)
2. Zielgruppe: (wer ist antragsberechtigt?)
3. Dauer der Förderung: (z.B. "bis zu 3 Jahre")
4. Internes Verfahren: (Hinweise zu rechtsverbindlicher Unterschrift oder interner Frist, sonst "Keine Angabe")

Antworte nur mit:
1: <Antwort>
2: <Antwort>
3: <Antwort>
4: <Antwort>
"""


def _parse_llm_output(output: str) -> Dict[str, str]:
    result = {"ziel": "Keine Angabe", "zielgruppe": "Keine Angabe",
              "dauer": "Keine Angabe", "intern": "Keine Angabe"}
    lines = output.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("1:"):
            result["ziel"] = line[2:].strip()
        elif line.startswith("2:"):
            result["zielgruppe"] = line[2:].strip()
        elif line.startswith("3:"):
            result["dauer"] = line[2:].strip()
        elif line.startswith("4:"):
            result["intern"] = line[2:].strip()
    return result


def _format_summary(title: str, institution: str, deadline: str,
                    funding: str, url: str, llm_data: Dict[str, str]) -> str:
    formatted = f"**Titel der Ausschreibung:** {title}\n"
    formatted += f"**Förderinstitution:** {institution or 'Keine Angabe'}\n"
    formatted += f"**Ziel / Aim:** {llm_data['ziel']}\n"
    formatted += f"**Zielgruppe / Target group:** {llm_data['zielgruppe']}\n"
    formatted += f"**Dauer / Duration:** {llm_data['dauer']}\n"
    formatted += f"**Förderhöhe / Funding:** {funding or 'Keine Angabe'}\n"
    formatted += f"**Fristende / Deadline:** {deadline or 'Keine Angabe'}\n"
    formatted += f"**Weitere Informationen / Further information:** {url}\n"
    if llm_data["intern"] != "Keine Angabe":
        formatted += f"**INTERNES VERFAHREN:** {llm_data['intern']}\n"
    return formatted


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
        title = scraped["title"] or "Keine Angabe"

        if not text or len(text) < 200:
            result["error"] = "Zu wenig Textinhalt"
            results.append(result)
            continue

        deadline = extract_deadline(text) or "Keine Angabe"
        funding = extract_funding(text) or "Keine Angabe"
        institution = extract_institution(text) or "Keine Angabe"

        result["deadline"] = deadline
        result["funding"] = funding
        result["institution"] = institution

        prompt = LLM_PROMPT.format(text=text[:8000])
        try:
            llm_output = client.generate(prompt, temperature=0.1, max_tokens=500)
            llm_data = _parse_llm_output(llm_output)
            result["summary"] = _format_summary(title, institution, deadline, funding, url, llm_data)
            result["status"] = "success"
        except Exception as e:
            result["error"] = f"LLM-Fehler: {e}"
            logger.error(f"LLM-Fehler bei {url}: {e}")

        results.append(result)

    return results
