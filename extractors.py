"""
Extraktion von Metadaten aus Webseiten-Texten.
Unterstützt eine Vielzahl von Ausschreibungsformaten (BMBF, DFG, EU, Stiftungen etc.).
"""

import re
import logging
from typing import Optional, List

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

    # Datumsmuster (international)
    PATTERNS = [
        (r"(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{4})", "DMY"),           # 31.12.2025
        (r"(\d{1,2})\.\s*([a-zA-Zäöüß]+)\s*(\d{4})", "DMy"),       # 31. Dezember 2025
        (r"(\d{4})-(\d{1,2})-(\d{1,2})", "YMD"),                   # 2025-12-31
        (r"(\d{1,2})/(\d{1,2})/(\d{4})", "MDY"),                   # 12/31/2025
        (r"([a-zA-Z]+)\s+(\d{1,2}),?\s*(\d{4})", "MDY_en"),        # December 31, 2025
    ]

    # Begriffe, die eine Frist ankündigen (deutsch/englisch)
    CONTEXT_WORDS = [
        # Deutsch
        "frist", "einreich", "bewerbungsschluss", "abgab", "einzureichen",
        "bis zum", "bis spätestens", "deadline", "stichtag", "ende der",
        "teilnahmeschluss", "antragsfrist", "einreichungsfrist", "schlusstermin",
        # Englisch
        "deadline", "submission date", "closing date", "due date", "cut-off",
        "applications must be submitted by", "proposals due"
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        dates_found = []

        # 1. Explizite Datumsbereiche im Header (wie "26.04.2021 - 25.05.2021")
        header_match = re.search(r"(\d{2}\.\d{2}\.\d{4})\s*[-–]\s*(\d{2}\.\d{2}\.\d{4})", text)
        if header_match:
            date_str = cls._parse_date_string(header_match.group(2))
            if date_str:
                logger.info(f"Frist aus Header gefunden: {date_str}")
                return date_str

        # 2. Alle Datumsfunde sammeln
        for pattern, style in cls.PATTERNS:
            for match in re.finditer(pattern, text_lower):
                date_str = cls._parse_match(match, style)
                if date_str:
                    # Kontext prüfen (150 Zeichen vor/nach dem Match)
                    start = max(0, match.start() - 200)
                    end = min(len(text_lower), match.end() + 200)
                    context = text_lower[start:end]
                    if any(word in context for word in cls.CONTEXT_WORDS):
                        dates_found.append((date_str, match.start()))

        if not dates_found:
            # Fallback: das späteste Datum im gesamten Text, falls kein Kontextwort gefunden wurde
            all_dates = []
            for pattern, style in cls.PATTERNS:
                for match in re.finditer(pattern, text_lower):
                    date_str = cls._parse_match(match, style)
                    if date_str:
                        all_dates.append((date_str, match.start()))
            if all_dates:
                all_dates.sort(key=lambda x: x[0])  # nach Datum sortieren
                return all_dates[-1][0]  # das späteste Datum nehmen
            return None

        dates_found.sort(key=lambda x: x[1])
        return dates_found[0][0]

    @classmethod
    def _parse_match(cls, match: re.Match, style: str) -> Optional[str]:
        """Parst ein Regex-Match je nach Stil."""
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
        """Parst DD.MM.YYYY."""
        match = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", date_str)
        if match:
            day, month, year = match.groups()
            return f"{year}-{month}-{day}"
        return None


class FundingExtractor:
    """Extrahiert Förderbeträge mit erweiterten Synonymen und Einheiten."""

    # Muster für Beträge mit verschiedenen Schreibweisen
    AMOUNT_PATTERNS = [
        # Deutsch
        r"(?:Zuwendung|Förder(?:summe|höhe|betrag)|Zuschuss|Finanzierung)\s+(?:soll|beträgt|in\s+Höhe\s+von|von|bis\s+zu)\s+[^\d]*(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mio\.?|Million(?:en)?)\s*(?:Euro|€|EUR)?",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mrd\.?|Milliarde(?:n)?)\s*(?:Euro|€|EUR)?",
        r"(?:beantragte\s+Zuwendung|Zuwendung)\s+(?:soll\s+(?:im\s+Regelfall\s+)?)?(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        # Englisch
        r"(?:funding|grant|budget)\s+(?:amount|of|up\s+to)\s+[^\d]*(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR|USD)",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:million|m)\s*(?:Euro|€|EUR|USD)",
        # Allgemein: Zahl gefolgt von Euro-Symbol im Kontext
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)(?:\s+(?:nicht\s+unterschreiten|werden\s+gewährt|als\s+Zuschuss|pro\s+Projekt))"
    ]

    CONTEXT_WORDS = [
        "zuwendung", "förder", "zuschuss", "finanzierung", "mittel", "budget",
        "funding", "grant", "amount", "award"
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        text_lower = text.lower()
        candidates = []

        for pattern in cls.AMOUNT_PATTERNS:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                raw_amount = match.group(1)
                full_match = match.group(0)

                # Kontext prüfen
                start = max(0, match.start() - 200)
                end = min(len(text_lower), match.end() + 50)
                context = text_lower[start:end]
                if any(word in context for word in cls.CONTEXT_WORDS):
                    clean = cls._normalize_amount(raw_amount, full_match)
                    candidates.append((clean, match.start()))

        if candidates:
            candidates.sort(key=lambda x: x[1])
            return candidates[0][0]

        return None

    @classmethod
    def _normalize_amount(cls, raw: str, full: str) -> str:
        """Bereinigt den Betrag und fügt Einheit hinzu."""
        # Entferne alle Leerzeichen und Punkte (Tausendertrenner)
        amount = raw.replace(" ", "").replace(".", "")
        # Komma durch Punkt ersetzen (Dezimaltrenner)
        amount = amount.replace(",", ".")

        # Einheit erkennen
        if re.search(r"Mio|Million|million", full, re.IGNORECASE):
            return f"{amount} Mio. €"
        elif re.search(r"Mrd|Milliarde|billion", full, re.IGNORECASE):
            return f"{amount} Mrd. €"
        else:
            return f"{amount} €"


class InstitutionExtractor:
    """Extrahiert die fördernde Institution mit erweiterten Indikatoren."""

    INDICATORS = [
        # Deutsche Institutionen
        "ministerium", "stiftung", "fonds", "agentur", "institut", "zentrum",
        "förder", "projektträger", "bundesamt", "landesamt", "gmbh", "e.v.",
        "bmbf", "bmwk", "bmuv", "bmftr", "bmwe", "bmbfsfj", "bmukn",
        "dfg", "deutsche forschungsgemeinschaft",
        "alexander von humboldt", "volkswagen", "fritz thyssen", "gerda henkel",
        "joachim herz", "klaus tschira", "boehringer ingelheim",
        "daad", "max weber", "wübben",
        # International
        "european commission", "erc", "horizon", "marie skłodowska",
        "national science foundation", "nsf", "nih", "wellcome",
        "jsps", "eth zürich", "ecb", "unesco", "who"
    ]

    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None

        # Zuerst nach expliziter Zeile mit "Bundesministerium" suchen
        lines = text.split("\n")
        for line in lines[:50]:  # Nur die ersten 50 Zeilen
            if "Bundesministerium" in line:
                clean = re.sub(r"\s+", " ", line).strip()
                if len(clean) < 150:
                    return clean
            if any(ind in line.lower() for ind in cls.INDICATORS):
                clean = re.sub(r"\s+", " ", line).strip()
                if 5 < len(clean) < 150:
                    return clean

        # Fallback: Suche im ersten Drittel des Textes
        first_part = text[: len(text) // 3]
        for indicator in cls.INDICATORS:
            match = re.search(rf"([^\n]*{indicator}[^\n]*)", first_part, re.IGNORECASE)
            if match:
                clean = re.sub(r"\s+", " ", match.group(1)).strip()
                if 5 < len(clean) < 150:
                    return clean

        return None


# Wrapper-Funktionen
def extract_deadline(text: str) -> Optional[str]:
    return DeadlineExtractor.extract(text)


def extract_funding(text: str) -> Optional[str]:
    return FundingExtractor.extract(text)


def extract_institution(text: str) -> Optional[str]:
    return InstitutionExtractor.extract(text)
