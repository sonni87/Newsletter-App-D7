"""
Kernfunktion – D7-Newsletter-Format mit LLM-Unterstützung für Aim/Target Group.
"""

import logging
from typing import List, Dict, Any, Optional

from scraper import scrape_url
from extractors import extract_deadline, extract_funding, extract_institution, extract_duration
from llm_client import LLMClient, KIConnectError

logger = logging.getLogger(__name__)

# Extrem klarer Prompt für das LLM
LLM_PROMPT = """
Extrahiere aus dem folgenden Text einer Förderausschreibung zwei Informationen:

1. Aim: Das Hauptziel der Förderung. Was wird gefördert? (2-3 prägnante Sätze, auf Englisch wenn der Text englisch ist)
2. Target group: Wer ist antragsberechtigt? Welche Einrichtungen/Personen? (1-2 Sätze)

Antworte NUR im folgenden Format (keine zusätzlichen Erklärungen):
Aim: <Text>
Target group: <Text>

TEXT:
{text}
"""


def _get_title_via_llm(text: str, client: LLMClient) -> str:
    """Fallback: Titel per LLM extrahieren."""
    prompt = "Wie lautet der offizielle Titel dieser Förderbekanntmachung? Antworte nur mit dem Titel."
    try:
        return client.generate(prompt.format(text=text[:2000]), temperature=0.0, max_tokens=100).strip()
    except:
        return "Keine Angabe"


def _format_d7(title: str, institution: str, aim: str, target: str,
               duration: str, funding: str, deadline: str, url: str,
               internal: bool = False) -> str:
    """Formatiert streng nach D7-Newsletter-Standard."""
    lines = [f"## {title}\n"]
    if aim and aim != "Keine Angabe":
        lines.append(f"Aim {aim}\n")
    if target and target != "Keine Angabe":
        lines.append(f"Target group {target}\n")
    if duration and duration != "Keine Angabe":
        lines.append(f"Duration {duration}\n")
    if funding and funding != "Keine Angabe":
        lines.append(f"Funding {funding}\n")
    if deadline and deadline != "Keine Angabe":
        lines.append(f"Deadline {deadline}\n")
    lines.append(f"Further information website\n")
    if internal:
        lines.append("\nINTERNAL PROCEDURE: Please note that the application form must be signed "
                     "by an authorised representative of the university (in German: \"rechtsverbindliche Unterschrift\"). "
                     "Therefore, please contact Department 73 - National Funding as soon as you decide to write a proposal "
                     "(a73_Antrag@verw.uni-koeln.de) to arrange an appointment for support in the preparation of the proposal.\n")
    lines.append("\n---")
    return "\n".join(lines)


def _needs_internal_procedure(institution: str) -> bool:
    if not institution:
        return False
    inst_lower = institution.lower()
    return any(x in inst_lower for x in ["bmbf", "bmftr", "bmwe", "bmwk", "bundesministerium"])


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
        result = {"url": url, "title": None, "summary": None, "deadline": None,
                  "funding": None, "institution": None, "status": "error", "error": None}

        scraped = scrape_url(url)
        if scraped["status"] != "success":
            result["error"] = scraped.get("error", "Scraping fehlgeschlagen")
            results.append(result)
            continue

        text = scraped["text"]
        title = scraped["title"]
        if len(text) < 200:
            result["error"] = "Zu wenig Textinhalt"
            results.append(result)
            continue

        # Metadaten per Regex
        deadline = extract_deadline(text) or "Keine Angabe"
        funding = extract_funding(text) or "Keine Angabe"
        institution = extract_institution(text) or "Keine Angabe"
        duration = extract_duration(text) or "Keine Angabe"

        # Titel: Falls None oder generisch, LLM-Fallback
        if not title or title == "Keine Angabe" or "Homepage" in title:
            title = _get_title_via_llm(text, client)

        # Aim und Target Group per LLM
        aim = "Keine Angabe"
        target = "Keine Angabe"
        try:
            llm_out = client.generate(LLM_PROMPT.format(text=text[:6000]), temperature=0.1, max_tokens=400)
            for line in llm_out.split("\n"):
                if line.startswith("Aim:"):
                    aim = line[4:].strip()
                elif line.startswith("Target group:"):
                    target = line[13:].strip()
        except Exception as e:
            logger.warning(f"LLM-Fehler für {url}: {e}")

        internal = _needs_internal_procedure(institution)

        result["title"] = title
        result["deadline"] = deadline
        result["funding"] = funding
        result["institution"] = institution
        result["summary"] = _format_d7(
            title, institution, aim, target, duration, funding, deadline, url, internal
        )
        result["status"] = "success"
        results.append(result)

    return results
