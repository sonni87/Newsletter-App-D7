"""
Extraktion von Metadaten – optimiert für D7-Newsletter-Standard.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DeadlineExtractor:
    MONTHS_DE = {"januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
                 "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12}
    MONTHS_EN = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                 "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
    
    PATTERNS = [
        (r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", "DMY"),
        (r"(\d{1,2})\.\s*([a-zA-Zäöüß]+)\s*(\d{4})", "DMy"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "YMD"),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "MDY"),
        (r"([a-zA-Z]+)\s+(\d{1,2}),?\s*(\d{4})", "MDY_en"),
    ]
    
    CONTEXT = ["frist", "einreich", "deadline", "bis zum", "stichtag", "submission", "due date"]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
        header = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})", text)
        if header:
            return cls._parse_date_str(header.group(2))

        text_lower = text.lower()
        dates = []
        for pat, style in cls.PATTERNS:
            for m in re.finditer(pat, text_lower):
                date = cls._parse_match(m, style)
                if date:
                    ctx = text_lower[max(0, m.start()-150):m.end()+150]
                    if any(w in ctx for w in cls.CONTEXT):
                        dates.append((date, m.start()))
        if dates:
            dates.sort(key=lambda x: x[1])
            return dates[0][0]
        return None

    @classmethod
    def _parse_match(cls, m, style):
        g = m.groups()
        try:
            if style == "DMY":
                d, mo, y = int(g[0]), int(g[1]), int(g[2])
                return f"{y:04d}-{mo:02d}-{d:02d}"
            if style == "DMy":
                d, mon, y = int(g[0]), g[1].lower(), int(g[2])
                if mon in cls.MONTHS_DE:
                    return f"{y:04d}-{cls.MONTHS_DE[mon]:02d}-{d:02d}"
                if mon in cls.MONTHS_EN:
                    return f"{y:04d}-{cls.MONTHS_EN[mon]:02d}-{d:02d}"
            if style == "YMD":
                y, mo, d = int(g[0]), int(g[1]), int(g[2])
                return f"{y:04d}-{mo:02d}-{d:02d}"
            if style == "MDY":
                mo, d, y = int(g[0]), int(g[1]), int(g[2])
                return f"{y:04d}-{mo:02d}-{d:02d}"
            if style == "MDY_en":
                mon, d, y = g[0].lower(), int(g[1]), int(g[2])
                if mon in cls.MONTHS_EN:
                    return f"{y:04d}-{cls.MONTHS_EN[mon]:02d}-{d:02d}"
        except:
            pass
        return None

    @classmethod
    def _parse_date_str(cls, s):
        m = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", s)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        return None


class FundingExtractor:
    """
    Extrahiert die projektbezogene Förderhöhe – ignoriert Gesamtbudgets.
    """
    
    # Muster, die explizit auf Projektförderung hindeuten (Priorität)
    PRIORITY_PATTERNS = [
        # D7-typisch: "Funding up to 100% of eligible ..."
        r"(?:Funding|Förderhöhe)\s*(?:up\s+to|bis\s+zu)\s+\d{1,3}%\s+of\s+(?:the\s+)?eligible\s+(?:project-?related\s+)?expenses(?:\s+as\s+well\s+as\s+a\s+project\s+lump\s+sum\s+of\s+\d{1,2}%)?",
        r"(?:Funding|Förderhöhe)\s*(?:bis\s+zu\s+)\d{1,3}%\s+der\s+zuwendungsfähigen\s+(?:projektbezogenen\s+)?Ausgaben(?:\s+sowie\s+eine\s+Projektpauschale\s+in\s+Höhe\s+von\s+\d{1,2}%)?",
        # "up to € 400,000" im Kontext von "Funding"
        r"Funding\s*:?\s*up\s+to\s+€?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)?(?:\s+\([^)]+\))?",
        r"Förderhöhe\s*:?\s*bis\s+zu\s+(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)?",
    ]
    
    # Fallback-Muster (mit Kontext)
    FALLBACK_PATTERNS = [
        r"(?:Zuwendung|Förderung|Funding)\s+(?:in\s+Höhe\s+von|beträgt|of)\s+[^\d]*(?:€\s*)?(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        r"(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:Mio\.?|Million)\s*(?:Euro|€)?\s+(?:pro\s+(?:Projekt|Vorhaben|project))",
    ]
    
    # Begriffe, die auf Gesamtbudget hindeuten → IGNORIEREN
    IGNORE_CONTEXT = [
        "insgesamt stehen", "Gesamtbudget", "total budget", "Maßnahme stehen",
        "Fördervolumen", "für diese Bekanntmachung", "für den Förderzeitraum"
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Prüfe, ob der Text Gesamtbudget-Signale enthält
        has_ignore_context = any(ig in text_lower for ig in cls.IGNORE_CONTEXT)
        
        # 1. Priorisierte Muster
        for pat in cls.PRIORITY_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                # Wenn das Match eine Gruppe enthält (z.B. Betrag), diese zurückgeben
                if m.groups():
                    return m.group(1).strip()
                return m.group(0).strip()
        
        # 2. Fallback-Muster, aber nur wenn KEIN Ignore-Kontext vorliegt
        if not has_ignore_context:
            for pat in cls.FALLBACK_PATTERNS:
                m = re.search(pat, text_lower, re.I)
                if m:
                    amount = m.group(1)
                    # Prüfe, ob wirklich projektbezogen
                    ctx = text_lower[max(0, m.start()-100):m.end()+100]
                    if "pro projekt" in ctx or "pro vorhaben" in ctx or "per project" in ctx:
                        if "mio" in ctx or "million" in ctx:
                            return f"{amount} Mio. €"
                        return f"{amount} €"
        
        # 3. Letzte Chance: Suche nach "Funding" oder "Förderhöhe" und nimm den umgebenden Satz
        m = re.search(r"(?:Funding|Förderhöhe)\s*(?:up\s+to\s+)?([^\n]{10,120})", text_lower, re.I)
        if m:
            candidate = m.group(1).strip()
            # Verwerfe, wenn Ignore-Kontext enthalten
            if not any(ig in candidate.lower() for ig in cls.IGNORE_CONTEXT):
                return candidate
        
        return None


class InstitutionExtractor:
    INDICATORS = [
        r"Bundesministerium\s+für\s+(?:Bildung\s+und\s+Forschung|Forschung,\s+Technologie\s+und\s+Raumfahrt|Wirtschaft\s+und\s+Energie|Umwelt)[^,\n]*",
        r"Federal\s+Ministry\s+of\s+(?:Research,\s+Technology\s+and\s+Space|Education\s+and\s+Research|Economic\s+Affairs\s+and\s+Energy)[^,\n]*",
        r"BMBF|BMFTR|BMWE|BMWK|BMUV",
        r"Deutsche\s+Forschungsgemeinschaft|DFG",
        r"European\s+Research\s+Council|ERC",
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
        head = text[:1500]
        for pat in cls.INDICATORS:
            m = re.search(pat, head, re.I)
            if m:
                return m.group(0).strip()
        return None


class DurationExtractor:
    PATTERNS = [
        r"(?:Duration|Dauer)\s*(?:up\s+to\s+|bis\s+zu\s+)?(\d+(?:\s*[-–]\s*\d+)?\s*(?:years?|months?|Jahre?|Monate?))",
        r"(\d+\s*(?:years?|Jahre?))\s+(?:funding\s+period|Laufzeit)",
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
        for pat in cls.PATTERNS:
            m = re.search(pat, text, re.I)
            if m:
                return m.group(1).strip()
        return None


def extract_deadline(text): return DeadlineExtractor.extract(text)
def extract_funding(text): return FundingExtractor.extract(text)
def extract_institution(text): return InstitutionExtractor.extract(text)
def extract_duration(text): return DurationExtractor.extract(text)
