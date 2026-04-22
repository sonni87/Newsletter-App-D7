"""
Extraktion von Metadaten aus Webseiten-Texten.
Unterstützt BMBF, BMFTR, BMWE, DFG, EU etc.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DeadlineExtractor:
    """Extrahiert Einreichungsfristen aus Text mit erweiterten Mustern."""

    MONTHS_DE = {
        "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
        "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12
    }
    MONTHS_EN = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }

    PATTERNS = [
        (r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", "DMY"),
        (r"(\d{1,2})\.\s*([a-zA-Zäöüß]+)\s*(\d{4})", "DMy"),
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "YMD"),
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "MDY"),
        (r"([a-zA-Z]+)\s+(\d{1,2}),?\s*(\d{4})", "MDY_en"),
    ]

    CONTEXT_WORDS = [
        "frist", "einreich", "bewerbungsschluss", "abgab", "einzureichen",
        "bis zum", "bis spätestens", "deadline", "stichtag", "ende der",
        "teilnahmeschluss", "antragsfrist", "einreichungsfrist", "schlusstermin",
        "deadline", "submission date", "closing date", "due date", "cut-off"
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        dates_found = []

        # Header-Datumsbereich
        header_match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})", text)
        if header_match:
            date_str = cls._parse_date_string(header_match.group(2))
            if date_str:
                return date_str

        for pattern, style in cls.PATTERNS:
            for match in re.finditer(pattern, text_lower):
                date_str = cls._parse_match(match, style)
                if date_str:
                    start = max(0, match.start() - 200)
                    end = min(len(text_lower), match.end() + 200)
                    context = text_lower[start:end]
                    if any(word in context for word in cls.CONTEXT_WORDS):
                        dates_found.append((date_str, match.start()))

        if not dates_found:
            all_dates = []
            for pattern, style in cls.PATTERNS:
                for match in re.finditer(pattern, text_lower):
                    date_str = cls._parse_match(match, style)
                    if date_str:
                        all_dates.append((date_str, match.start()))
            if all_dates:
                all_dates.sort(key=lambda x: x[0])
                return all_dates[-1][0]
            return None

        dates_found.sort(key=lambda x: x[1])
        return dates_found[0][0]

    @classmethod
    def _parse_match(cls, match: re.Match, style: str) -> Optional[str]:
        groups = match.groups()
        try:
            if style == "DMY":
                day, month, year = int(groups[0]), int(groups[1]), int(groups[2])
                if 1 <= day <= 31 and 1 <= month <= 12:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            elif style == "DMy":
                day = int(groups[0])
                year = int(groups[2])
                month_name = groups[1].lower()
                if month_name in cls.MONTHS_DE:
                    month = cls.MONTHS_DE[month_name]
                    return f"{year:04d}-{month:02d}-{day:02d}"
                elif month_name in cls.MONTHS_EN:
                    month = cls.MONTHS_EN[month_name]
                    return f"{year:04d}-{month:02d}-{day:02d}"
            elif style == "YMD":
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            elif style == "MDY":
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                if 1 <= month <= 12 and 1 <= day <= 31:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            elif style == "MDY_en":
                month_name = groups[0].lower()
                day = int(groups[1])
                year = int(groups[2])
                if month_name in cls.MONTHS_EN:
                    month = cls.MONTHS_EN[month_name]
                    return f"{year:04d}-{month:02d}-{day:02d}"
        except (ValueError, IndexError):
            pass
        return None

    @classmethod
    def _parse_date_string(cls, date_str: str) -> Optional[str]:
        match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return None


class FundingExtractor:
    """Extrahiert Fördersumme mit Kontext, um Programm-Budgets zu vermeiden."""

    PATTERNS = [
        r"(?:Zuwendung|Förderung|Zuschuss)\s+(?:soll|beträgt|in\s+Höhe\s+von|von|bis\s+zu)\s+[^\d]*(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mio\.?|Million(?:en)?)\s*(?:Euro|€|EUR)",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mrd\.?|Milliarde(?:n)?)\s*(?:Euro|€|EUR)",
        r"Förderhöhe\s*(?:beträgt\s*)?(?:bis\s+zu\s+)?(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        for pattern in cls.PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                amount = match.group(1)
                full = match.group(0)
                # Kontext: wenn "Mrd." oder "Milliarden" -> Programm-Budget, ggf. ignorieren?
                if re.search(r"Mrd|Milliarde|billion", full, re.IGNORECASE):
                    # Nur zurückgeben, wenn explizit "pro Projekt" oder ähnlich
                    if "pro projekt" not in text_lower[match.start()-100:match.end()+100]:
                        # Wahrscheinlich Gesamtbudget, nicht Projektsumme
                        continue
                clean = cls._normalize_amount(amount, full)
                return clean
        return None

    @classmethod
    def _normalize_amount(cls, raw: str, full: str) -> str:
        amount = raw.replace(" ", "").replace(".", "").replace(",", ".")
        if re.search(r"Mio|Million|million", full, re.IGNORECASE):
            return f"{amount} Mio. €"
        elif re.search(r"Mrd|Milliarde|billion", full, re.IGNORECASE):
            return f"{amount} Mrd. €"
        return f"{amount} €"


class InstitutionExtractor:
    """Erkennt fördernde Institution (BMBF, BMFTR, DFG, EU...)"""

    INDICATORS = [
        "Bundesministerium für Bildung und Forschung",
        "Bundesministerium für Forschung, Technologie und Raumfahrt",
        "Bundesministerium für Wirtschaft und Energie",
        "Bundesministerium für Umwelt",
        "BMBF", "BMFTR", "BMWE", "BMUKN", "BMWK",
        "Deutsche Forschungsgemeinschaft", "DFG",
        "Europäische Kommission", "ERC", "Horizon",
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        # Suche in den ersten 1000 Zeichen
        head = text[:1000]
        for ind in cls.INDICATORS:
            if ind.lower() in head.lower():
                # Gib den gefundenen Namen zurück
                match = re.search(rf"({ind}[^\n]*)", head, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
        return None


# Wrapper
def extract_deadline(text: str) -> Optional[str]:
    return DeadlineExtractor.extract(text)


def extract_funding(text: str) -> Optional[str]:
    return FundingExtractor.extract(text)


def extract_institution(text: str) -> Optional[str]:
    return InstitutionExtractor.extract(text)
