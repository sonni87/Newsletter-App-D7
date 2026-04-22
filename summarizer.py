"""
Kernfunktion: URLs scrapen, LLM-Zusammenfassung im D7-Newsletter-Format generieren.
"""

import logging
from typing import List, Dict, Any, Optional

from scraper import scrape_url
from extractors import extract_deadline, extract_funding, extract_institution
from llm_client import LLMClient, KIConnectError

logger = logging.getLogger(__name__)

# Allgemeingültiger Prompt für beliebige Ausschreibungen
LLM_PROMPT_TEMPLATE = """
Du bist Experte für Forschungsförderung. Analysiere den folgenden Text einer Förderausschreibung und extrahiere die gefragten Informationen.

TEXT:
{text}

FRAGEN (antworte kurz und prägnant, max. 2 Sätze pro Punkt):
1. Ziel der Förderung: Was ist das Hauptziel? Was wird gefördert?
2. Zielgruppe: Wer kann sich bewerben? Welche Einrichtungen/Personen?
3. Dauer: Wie lange können Projekte gefördert werden? (z.B. "bis zu 3 Jahre", "12 Monate")
4. Internes Verfahren: Gibt es einen Hinweis auf interne Antragswege, rechtsverbindliche Unterschrift oder eine Frist für die interne Abwicklung? Wenn ja, zitiere den Hinweis wörtlich.

Antworte NUR mit den Antworten im Format:
1. [Antwort]
2. [Antwort]
3. [Antwort]
4. [Antwort]

Falls eine Information fehlt, schreibe "Keine Angabe".
"""


def _format_summary(llm_output: str, title: str, institution: str,
                    deadline: str, funding: str, url: str) -> str:
    """Formatiert die Rohausgabe des LLM in das D7-Newsletter-Format."""
    answers = {"ziel": "Keine Angabe", "zielgruppe": "Keine Angabe",
               "dauer": "Keine Angabe", "intern": None}

    lines = llm_output.strip().split('\n')
    current_key = None
    for line in lines:
        line = line.strip()
        if line.startswith("1. "):
            current_key = "ziel"
            answers[current_key] = line[3:].strip()
        elif line.startswith("2. "):
            current_key = "zielgruppe"
            answers[current_key] = line[3:].strip()
        elif line.startswith("3. "):
            current_key = "dauer"
            answers[current_key] = line[3:].strip()
        elif line.startswith("4. "):
            current_key = "intern"
            answers[current_key] = line[3:].strip()
        elif current_key:
            answers[current_key] += " " + line

    # Titel bereinigen (ggf. kürzen)
    if len(title) > 120:
        title = title[:117] + "..."

    formatted = f"**Titel der Ausschreibung:** {title}\n"
    formatted += f"**Förderinstitution:** {institution or 'Keine Angabe'}\n"
    formatted += f"**Ziel / Aim:** {answers['ziel']}\n"
    formatted += f"**Zielgruppe / Target group:** {answers['zielgruppe']}\n"
    formatted += f"**Dauer / Duration:** {answers['dauer']}\n"
    formatted += f"**Förderhöhe / Funding:** {funding or 'Keine Angabe'}\n"
    formatted += f"**Fristende / Deadline:** {deadline or 'Keine Angabe'}\n"
    formatted += f"**Weitere Informationen / Further information:** {url}\n"
    if answers["intern"] and "Keine Angabe" not in answers["intern"]:
        formatted += f"**INTERNES VERFAHREN:** {answers['intern']}\n"

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
        result["title"] = scraped["title"] or "Keine Angabe"

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

        max_text_length = 8000
        text_snippet = text[:max_text_length] + ("..." if len(text) > max_text_length else "")

        prompt = LLM_PROMPT_TEMPLATE.format(text=text_snippet)

        try:
            llm_output = client.generate(prompt, temperature=0.1, max_tokens=600)
            formatted_summary = _format_summary(
                llm_output, result["title"], institution, deadline, funding, url
            )
            result["summary"] = formatted_summary
            result["status"] = "success"
        except KIConnectError as e:
            result["error"] = f"LLM-Fehler: {e}"
            logger.error(f"LLM-Fehler für {url}: {e}")
        except Exception as e:
            result["error"] = f"Unerwarteter Fehler: {e}"
            logger.exception(f"Unerwarteter Fehler bei {url}")

        results.append(result)

    return results
