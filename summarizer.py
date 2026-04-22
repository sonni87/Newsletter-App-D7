import logging
from typing import List, Dict, Any, Optional
from scraper import scrape_url
from extractors import extract_deadline, extract_funding, extract_institution
from llm_client import LLMClient, KIConnectError

logger = logging.getLogger(__name__)

PROMPT = """
Analysiere den Text einer Förderausschreibung. Extrahiere präzise:

1. Ziel der Förderung (max. 2 Sätze, was wird gefördert?)
2. Zielgruppe (wer ist antragsberechtigt?)
3. Dauer der Förderung (z.B. "bis zu 3 Jahre")
4. Internes Verfahren (Hinweise auf rechtsverbindliche Unterschrift oder interne Frist. Wenn nichts erwähnt, schreibe "Keine Angabe")

Wichtig: Nenne KEINE Gesamtbudgets. Antworte nur mit:
1: <Antwort>
2: <Antwort>
3: <Antwort>
4: <Antwort>

TEXT:
{text}
"""


def _parse_llm(output: str) -> Dict[str, str]:
    res = {"ziel": "Keine Angabe", "zielgruppe": "Keine Angabe",
           "dauer": "Keine Angabe", "intern": "Keine Angabe"}
    for line in output.split("\n"):
        line = line.strip()
        if line.startswith("1:"): res["ziel"] = line[2:].strip()
        elif line.startswith("2:"): res["zielgruppe"] = line[2:].strip()
        elif line.startswith("3:"): res["dauer"] = line[2:].strip()
        elif line.startswith("4:"): res["intern"] = line[2:].strip()
    return res


def _format(title, inst, deadline, funding, url, llm):
    out = f"**Titel der Ausschreibung:** {title}\n"
    out += f"**Förderinstitution:** {inst or 'Keine Angabe'}\n"
    out += f"**Ziel / Aim:** {llm['ziel']}\n"
    out += f"**Zielgruppe / Target group:** {llm['zielgruppe']}\n"
    out += f"**Dauer / Duration:** {llm['dauer']}\n"
    out += f"**Förderhöhe / Funding:** {funding or 'Keine Angabe'}\n"
    out += f"**Fristende / Deadline:** {deadline or 'Keine Angabe'}\n"
    out += f"**Weitere Informationen / Further information:** {url}\n"
    if llm["intern"] != "Keine Angabe":
        out += f"**INTERNES VERFAHREN:** {llm['intern']}\n"
    return out


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
        title = scraped["title"] or "Keine Angabe"
        if len(text) < 200:
            result["error"] = "Zu wenig Textinhalt"
            results.append(result)
            continue

        deadline = extract_deadline(text) or "Keine Angabe"
        funding = extract_funding(text) or "Keine Angabe"
        institution = extract_institution(text) or "Keine Angabe"

        result["deadline"] = deadline
        result["funding"] = funding
        result["institution"] = institution

        try:
            llm_out = client.generate(PROMPT.format(text=text[:8000]), temperature=0.1, max_tokens=500)
            llm_data = _parse_llm(llm_out)
            result["summary"] = _format(title, institution, deadline, funding, url, llm_data)
            result["status"] = "success"
        except Exception as e:
            result["error"] = f"LLM-Fehler: {e}"

        results.append(result)
    return results
