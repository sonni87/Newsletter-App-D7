"""
Extraktion von Metadaten aus Förderausschreibungen.
Maximale Abdeckung durch umfangreiche Synonyme und Muster.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AimExtractor:
    """Extrahiert das Förderziel / Aim."""
    
    # Deutsche Synonyme für "Ziel"
    DE_KEYWORDS = [
        "Ziel", "Zweck", "Förderziel", "Förderzweck", "Zuwendungszweck",
        "Gegenstand der Förderung", "Fördergegenstand", "Aufgabe", "Förderaufgabe"
    ]
    # Englische Synonyme für "Aim"
    EN_KEYWORDS = [
        "Aim", "Purpose", "Objective", "Goal", "Funding objective",
        "The aim is to", "The purpose of this", "Objectives of the"
    ]
    
    # Verbindungswörter nach dem Schlüsselwort
    CONNECTORS = ["ist", "ist es", "soll", "dient", "ist darauf ausgerichtet", "verfolgt das Ziel",
                  "is to", "is", "are to", "aims to", "seeks to", "will"]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
            
        # Kombiniere alle Keywords mit optionalen Connectoren
        de_pattern = r"(?:" + "|".join(cls.DE_KEYWORDS) + r")\s+(?:" + "|".join(cls.CONNECTORS) + r"\s+)?([^\n]{50,400})"
        en_pattern = r"(?:" + "|".join(cls.EN_KEYWORDS) + r")\s+(?:" + "|".join(cls.CONNECTORS) + r"\s+)?([^\n]{50,400})"
        
        # Suche zuerst Deutsch, dann Englisch
        for pattern in [de_pattern, en_pattern]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None


class TargetGroupExtractor:
    """Extrahiert die Zielgruppe / Antragsberechtigte."""
    
    DE_KEYWORDS = [
        "Zielgruppe", "Antragsberechtigt", "Antragsteller", "Teilnahmeberechtigt",
        "Einreicher", "wer kann sich bewerben", "Förderempfänger", "Zuwendungsempfänger",
        "Begünstigte", "Adressaten", "wer ist antragsberechtigt"
    ]
    EN_KEYWORDS = [
        "Target group", "Eligible applicants", "Who can apply", "Eligibility",
        "Applicants", "Beneficiaries", "Eligible institutions", "Eligible entities"
    ]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
        de_pattern = r"(?:" + "|".join(cls.DE_KEYWORDS) + r")\s*:?\s*([^\n]{20,300})"
        en_pattern = r"(?:" + "|".join(cls.EN_KEYWORDS) + r")\s*:?\s*([^\n]{20,300})"
        for pattern in [de_pattern, en_pattern]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None


class DurationExtractor:
    """Extrahiert die Projektlaufzeit / Dauer."""
    
    DE_KEYWORDS = [
        "Dauer", "Laufzeit", "Projektdauer", "Projektlaufzeit", "Förderdauer",
        "Förderzeitraum", "Bewilligungszeitraum", "Zeitraum", "maximale Dauer"
    ]
    EN_KEYWORDS = [
        "Duration", "Funding period", "Project duration", "Period", "Length",
        "Maximum duration", "Up to", "For a period of"
    ]
    
    # Muster für Zeitangaben
    TIME_PATTERNS = [
        r"(\d+(?:\s*[-–]\s*\d+)?\s*(?:Jahre?|Monate?|Wochen?|Tage?))",
        r"(\d+(?:\s*[-–]\s*\d+)?\s*(?:years?|months?|weeks?|days?))",
        r"(bis zu\s+\d+\s+(?:Jahre?|Monate?|years?|months?))",
        r"(up to\s+\d+\s+(?:years?|months?))",
    ]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
            
        # Suche zuerst nach Schlüsselwort + Zeitangabe
        de_pattern = r"(?:" + "|".join(cls.DE_KEYWORDS) + r")\s*:?\s*([^\n]{5,50})"
        en_pattern = r"(?:" + "|".join(cls.EN_KEYWORDS) + r")\s*:?\s*([^\n]{5,50})"
        
        for pattern in [de_pattern, en_pattern]:
            m = re.search(pattern, text, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # Extrahiere die eigentliche Zeitangabe
                for tp in cls.TIME_PATTERNS:
                    tm = re.search(tp, candidate, re.IGNORECASE)
                    if tm:
                        return tm.group(1).strip()
                return candidate
                
        # Fallback: Suche nach typischen Zeitangaben im gesamten Text
        for tp in cls.TIME_PATTERNS:
            m = re.search(tp, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None


class FundingExtractor:
    """
    Extrahiert die Förderhöhe – ignoriert Gesamtbudgets.
    Maximale Synonym-Abdeckung.
    """
    
    # Deutsche Keywords für Fördersumme
    DE_FUNDING_KEYS = [
        "Förderhöhe", "Fördersumme", "Zuwendung", "Zuschuss", "Finanzierung",
        "Fördervolumen pro", "Mittel pro", "Förderung in Höhe von", "Zuwendung in Höhe von",
        "bewilligte Mittel", "Förderbetrag", "Zuwendungsbetrag", "Förderung beträgt"
    ]
    
    # Englische Keywords
    EN_FUNDING_KEYS = [
        "Funding", "Grant amount", "Award amount", "Financial support", "Budget",
        "Funding up to", "Grant of up to", "Maximum funding", "Funding level"
    ]
    
    # Muster für absolute Beträge
    AMOUNT_PATTERNS = [
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        r"(?:Euro|€|EUR)\s*(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mio\.?|Million(?:en)?)\s*(?:Euro|€|EUR)?",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Mrd\.?|Milliarde(?:n)?)\s*(?:Euro|€|EUR)?",
        r"(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Tausend|Tsd\.?)\s*(?:Euro|€|EUR)?",
    ]
    
    # Prozentangaben
    PERCENT_PATTERNS = [
        r"(?:bis zu\s+)?(\d{1,3})\s*%\s+(?:der|des)\s+(?:zuwendungsfähigen|förderfähigen|projektbezogenen)\s+(?:Ausgaben|Kosten|Gesamtkosten)",
        r"(?:bis zu\s+)?(\d{1,3})\s*%\s+(?:Förderquote|Förderanteil|Zuschuss)",
        r"(?:up to\s+)?(\d{1,3})\s*%\s+of\s+(?:eligible|project-?related)\s+(?:expenses|costs)",
        r"Förderquote\s*(?:von\s+)?(?:bis zu\s+)?(\d{1,3})\s*%",
        r"Projektpauschale\s*(?:in Höhe von|von)?\s*(\d{1,2})\s*%",
    ]
    
    # Sonderfall: "Zuwendung soll ... Euro nicht unterschreiten/überschreiten"
    SPECIAL_PATTERNS = [
        r"Zuwendung\s+soll\s+(?:im\s+Regelfall\s+)?(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)\s+(?:nicht\s+unterschreiten|nicht\s+überschreiten|betragen)",
        r"Die\s+beantragte\s+Zuwendung\s+soll\s+(?:im\s+Regelfall\s+)?(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)\s+(?:nicht\s+unterschreiten|nicht\s+überschreiten)",
        r"Förderung\s+(?:beträgt|in Höhe von)\s+(?:maximal\s+)?(\d{1,3}(?:[.,\s]?\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)",
        r"Funding\s+(?:amount\s+)?(?:is\s+)?(?:up\s+to\s+)?€?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)\s*(?:Euro|€|EUR)?",
    ]
    
    # Ignore-Kontext (Gesamtbudgets)
    IGNORE_CONTEXT = [
        "insgesamt stehen", "Gesamtbudget", "Gesamtfördervolumen", "Gesamthöhe",
        "für die Maßnahme stehen", "für diese Bekanntmachung", "Fördervolumen der Maßnahme",
        "total budget", "overall budget", "total funding available", "total call budget"
    ]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
            
        text_lower = text.lower()
        
        # Prüfe, ob der Text ein Gesamtbudget signalisiert
        has_ignore = any(ig in text_lower for ig in cls.IGNORE_CONTEXT)
        
        # 1. Spezielle Muster (höchste Priorität)
        for pat in cls.SPECIAL_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                amount = cls._clean_number(m.group(1))
                if "Mio" in m.group(0).lower() or "Million" in m.group(0).lower():
                    return f"{amount} Mio. €"
                elif "Mrd" in m.group(0).lower() or "Milliarde" in m.group(0).lower():
                    return f"{amount} Mrd. €"
                return f"{amount} €"
        
        # 2. Prozentangaben (sehr häufig in D7)
        for pat in cls.PERCENT_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return f"{m.group(1)}%"
        
        # 3. Absolute Beträge im Kontext von Förder-Keywords
        #    (nur wenn kein Gesamtbudget-Signal)
        if not has_ignore:
            # Kombiniere Keywords mit Betragsmustern
            for fk in cls.DE_FUNDING_KEYS + cls.EN_FUNDING_KEYS:
                for ap in cls.AMOUNT_PATTERNS:
                    # Suche nach Keyword gefolgt von Betrag innerhalb von 80 Zeichen
                    pat = rf"{fk}[^\n]{{0,80}}?{ap}"
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        amount = cls._clean_number(m.group(1))
                        if "Mio" in m.group(0).lower() or "Million" in m.group(0).lower():
                            return f"{amount} Mio. €"
                        elif "Mrd" in m.group(0).lower() or "Milliarde" in m.group(0).lower():
                            return f"{amount} Mrd. €"
                        return f"{amount} €"
        
        # 4. Fallback: Suche nach "Funding" oder "Förderhöhe" und nimm den umgebenden Satz
        m = re.search(r"(?:Funding|Förderhöhe|Fördersumme)\s*:?\s*([^\n]{10,120})", text_lower, re.I)
        if m and not has_ignore:
            return m.group(1).strip()
            
        return None
    
    @staticmethod
    def _clean_number(s: str) -> str:
        """Entfernt Tausendertrennzeichen und normalisiert Dezimaltrenner."""
        s = re.sub(r"\s+", "", s)           # Leerzeichen entfernen
        s = s.replace(".", "").replace(",", ".")  # Punkte (Tausender) weg, Komma zu Punkt
        return s


class InstitutionExtractor:
    """Extrahiert die fördernde Institution."""
    
    INDICATORS = [
        # Deutsche Vollnamen
        r"Bundesministerium\s+für\s+Bildung\s+und\s+Forschung",
        r"Bundesministerium\s+für\s+Forschung,\s+Technologie\s+und\s+Raumfahrt",
        r"Bundesministerium\s+für\s+Wirtschaft\s+und\s+Energie",
        r"Bundesministerium\s+für\s+Wirtschaft\s+und\s+Klimaschutz",
        r"Bundesministerium\s+für\s+Umwelt,\s+Naturschutz,\s+nukleare\s+Sicherheit\s+und\s+Verbraucherschutz",
        r"Bundesministerium\s+für\s+Familie,\s+Senioren,\s+Frauen\s+und\s+Jugend",
        # Englische Vollnamen
        r"Federal\s+Ministry\s+of\s+Education\s+and\s+Research",
        r"Federal\s+Ministry\s+of\s+Research,\s+Technology\s+and\s+Space",
        r"Federal\s+Ministry\s+for\s+Economic\s+Affairs\s+and\s+Energy",
        r"Federal\s+Ministry\s+for\s+Economic\s+Affairs\s+and\s+Climate\s+Action",
        r"Federal\s+Ministry\s+for\s+the\s+Environment,\s+Nature\s+Conservation,\s+Nuclear\s+Safety\s+and\s+Consumer\s+Protection",
        # Abkürzungen
        r"BMBF|BMFTR|BMWE|BMWK|BMUV|BMUKN|BMBFSFJ",
        # Forschungsförderer
        r"Deutsche\s+Forschungsgemeinschaft|DFG",
        r"European\s+Research\s+Council|ERC",
        r"European\s+Commission|Europäische\s+Kommission",
        r"Alexander\s+von\s+Humboldt[- ]Stiftung",
        r"Volkswagen\s*Stiftung",
        r"Fritz\s+Thyssen\s+Stiftung",
        r"Gerda\s+Henkel\s+Stiftung",
        r"Wübben\s+Stiftung",
        r"Boehringer\s+Ingelheim\s+Foundation",
        r"Joachim\s+Herz\s+Stiftung",
        r"Klaus\s+Tschira\s+Stiftung",
        r"Fonds\s+der\s+Chemischen\s+Industrie|FCI",
        r"DAAD|Deutscher\s+Akademischer\s+Austauschdienst",
        r"Max[- ]Weber[- ]Stiftung",
    ]
    
    @classmethod
    def extract(cls, text: str) -> Optional[str]:
        if not text:
            return None
        head = text[:2000]  # Institution steht meist am Anfang
        for pat in cls.INDICATORS:
            m = re.search(pat, head, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return None


# Wrapper-Funktionen für einfachen Import
def extract_aim(text: str) -> Optional[str]:
    return AimExtractor.extract(text)

def extract_target_group(text: str) -> Optional[str]:
    return TargetGroupExtractor.extract(text)

def extract_duration(text: str) -> Optional[str]:
    return DurationExtractor.extract(text)

def extract_funding(text: str) -> Optional[str]:
    return FundingExtractor.extract(text)

def extract_deadline(text: str) -> Optional[str]:
    return DeadlineExtractor.extract(text)

def extract_institution(text: str) -> Optional[str]:
    return InstitutionExtractor.extract(text)
