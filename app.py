"""
Streamlit App – Prompt-Client für KI:connect mit Übersetzungsoption.
Layout angepasst an das Corporate Design der Universität zu Köln.
"""

import streamlit as st
from llm_client import LLMClient, KIConnectError

# --- Seiteneinstellungen & Uni-Köln-Farben ---
st.set_page_config(
    page_title="KI:connect Prompt",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS für Uni-Köln-Design
st.markdown("""
<style>
h1 { color: #005176 !important; }
section[data-testid="stSidebar"] { background-color: #F0F4F7; }
.stButton > button { background-color: #009DCC; color: white; border: none; }
.stButton > button:hover { background-color: #007BA1; color: white; }
div[data-testid="stButton"]:has(button[kind="primary"]) > button {
    background-color: #BE0A26 !important; color: white !important; font-weight: bold !important;
}
div[data-testid="stButton"]:has(button[kind="primary"]) > button:hover {
    background-color: #99071E !important;
}
.stDownloadButton > button { background-color: #EF7872; color: white; border: none; }
.stDownloadButton > button:hover { background-color: #D9655F; color: white; }
a { color: #009DCC !important; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 KI:connect – Prompt Client zur Zusammenfassung von Ausschreibungstexten")
st.markdown("Gib deinen Prompt und den Ausschreibungstext ein. Die Antwort wird im Markdown‑Format ausgegeben und kann exportiert werden.")

# --- Session State initialisieren ---
defaults = {
    "response": "",
    "translated_response": "",
    "available_models": [],
    "selected_model": None,
    "user_text": "",
    "text_area_key": 0,
    "tokens_session_prompt": 0,
    "tokens_session_completion": 0,
    "tokens_session_total": 0,
    "last_usage": None,
    "request_count": 0,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


def update_token_stats(usage: dict):
    """Kumuliert Token-Nutzung in der Session."""
    st.session_state.tokens_session_prompt     += usage.get("prompt_tokens", 0)
    st.session_state.tokens_session_completion += usage.get("completion_tokens", 0)
    st.session_state.tokens_session_total      += usage.get("total_tokens", 0)
    st.session_state.last_usage = usage
    st.session_state.request_count += 1


# ========== SIDEBAR ==========
with st.sidebar:
    st.header("⚙️ Konfiguration")
    api_key_input = st.text_input(
        "KIConnect API-Key",
        type="password",
        placeholder="Aus Umgebungsvariable/Secrets",
        help="Wird automatisch aus Streamlit Secrets oder KICONNECT_API_KEY geladen."
    )

    if st.button("🔌 Verbinde mich mit KI:connect"):
        try:
            client = LLMClient(api_key=api_key_input if api_key_input else None)
            if client.check_connection():
                st.success("✅ Verbindung erfolgreich!")
                models = client.list_models()
                st.session_state.available_models = models
                st.success(f"✅ {len(models)} Modelle geladen!")
            else:
                st.error("❌ Verbindung fehlgeschlagen.")
        except Exception as e:
            st.error(f"❌ Fehler: {e}")

    if st.session_state.available_models:
        st.divider()
        st.subheader("🤖 Modellauswahl")
        if st.session_state.selected_model not in st.session_state.available_models:
            st.session_state.selected_model = st.session_state.available_models[0]
        st.session_state.selected_model = st.selectbox(
            "Wähle ein Modell:",
            options=st.session_state.available_models,
            index=st.session_state.available_models.index(st.session_state.selected_model)
        )
        st.markdown(f"**Aktives Modell:** `{st.session_state.selected_model}`")

    # --- Token-Anzeige ---
    st.divider()
    st.subheader("🔢 Token-Verbrauch (Session)")
    if st.session_state.request_count == 0:
        st.caption("Noch keine Anfragen in dieser Session.")
    else:
        st.metric("Anfragen gesamt", st.session_state.request_count)
        col_tok1, col_tok2 = st.columns(2)
        with col_tok1:
            st.metric("Input", f"{st.session_state.tokens_session_prompt:,}".replace(",", "."))
        with col_tok2:
            st.metric("Output", f"{st.session_state.tokens_session_completion:,}".replace(",", "."))
        st.metric(
            "Tokens gesamt",
            f"{st.session_state.tokens_session_total:,}".replace(",", ".")
        )
        if st.session_state.last_usage:
            with st.expander("Letzte Anfrage"):
                lu = st.session_state.last_usage
                st.caption(
                    f"Input: {lu.get('prompt_tokens', 0):,} | "
                    f"Output: {lu.get('completion_tokens', 0):,} | "
                    f"Gesamt: {lu.get('total_tokens', 0):,}".replace(",", ".")
                )
        if st.button("🗑️ Token-Zähler zurücksetzen"):
            st.session_state.tokens_session_prompt = 0
            st.session_state.tokens_session_completion = 0
            st.session_state.tokens_session_total = 0
            st.session_state.last_usage = None
            st.session_state.request_count = 0
            st.rerun()

    st.divider()
    st.subheader("🖥️ Systemauslastung")
    try:
        import psutil
        ram = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.5)
        ram_used = ram.used / (1024 ** 3)
        ram_total = ram.total / (1024 ** 3)
        ram_pct = ram.percent
        st.progress(int(cpu), text=f"CPU: {cpu:.0f}%")
        st.progress(int(ram_pct), text=f"RAM: {ram_used:.1f} / {ram_total:.1f} GB ({ram_pct:.0f}%)")
    except ImportError:
        try:
            mem = {}
            with open("/proc/meminfo") as f:
                for line in f:
                    parts = line.split()
                    mem[parts[0].rstrip(":")] = int(parts[1])
            ram_total_gb = mem["MemTotal"] / (1024 ** 2)
            ram_avail_gb = mem["MemAvailable"] / (1024 ** 2)
            ram_used_gb = ram_total_gb - ram_avail_gb
            ram_pct = int(ram_used_gb / ram_total_gb * 100)
            import time
            def _cpu_times():
                with open("/proc/stat") as f:
                    vals = f.readline().split()[1:]
                return [int(v) for v in vals]
            t1 = _cpu_times(); time.sleep(0.5); t2 = _cpu_times()
            idle1, idle2 = t1[3], t2[3]
            total1, total2 = sum(t1), sum(t2)
            cpu_pct = int(100 * (1 - (idle2 - idle1) / (total2 - total1)))
            st.progress(cpu_pct, text=f"CPU: {cpu_pct}%")
            st.progress(ram_pct, text=f"RAM: {ram_used_gb:.1f} / {ram_total_gb:.1f} GB ({ram_pct}%)")
        except Exception as e:
            st.caption(f"Systeminfo nicht verfügbar: {e}")

    if st.button("🔄 Aktualisieren"):
        st.rerun()

    st.markdown("---")
    st.caption("Beta-Newsletter – Prompt Client v1.2")

# ========== DEFAULT PROMPT ==========
default_prompt = """Du bist Redakteur des Fördernewsletters der Universität zu Köln (Division 7 Research
Management). Du fasst Förderausschreibungen so zusammen, wie sie im Newsletter erscheinen:
kompakt, sachlich, ohne Einleitungssätze oder Marketingsprache, direkt auf die
strukturierten Felder beschränkt.

Analysiere die folgende Förderausschreibung und gib NUR die strukturierten Felder aus –
keine Einleitung, kein Kommentar, keine abschließenden Bemerkungen.

REGELN:

1. SPRACHE: Formuliere auf Englisch. Ausnahme: Die Ausschreibung ist ausschließlich auf
   Deutsch verfügbar und kann nur auf Deutsch beantragt werden – dann auf Deutsch mit
   deutschen Feldbezeichnungen (Förderung / Zielgruppe / Dauer / Förderhöhe / Fristende
   / Website).

2. FÖRDERHÖHE – KRITISCH:
   Nenne IMMER die Fördersumme PRO PROJEKT oder PRO ANTRAG, nie das Gesamtbudget der
   Förderlinie. Zeige immer den Bezugspunkt:
   - "for each German partner" / "for all German partners" / "per project"
   - Förderlinien/Phasen separat: z.B. "up to € 600,000 (funding line A) | up to
     € 1.2 million (funding line B)" oder "exploratory phase: € 100,000 | feasibility
     phase: € 500,000 (+overhead)"
   - Hochschulen: Förderquote ergänzen wenn relevant, z.B.
     "up to 100% of eligible project-related expenses + 20% project lump sum for universities"
   - Ist nur das Gesamtprogrammbudget genannt und keine Einzelprojektförderung:
     schreibe "not specified per project"

3. ZIELGRUPPE: Präzise – Antragstyp (Einzel-/Verbundprojekt, internationale Kooperation)
   UND Antragsteller (Institutionen, Karrierestufen, Mindestpartnerzahl, Länder).
   Orientiere dich an Newsletter-Einträgen wie: "transnational pre-competitive R&D
   projects with at least three partners from three participating countries" – nicht
   nur allgemein "Forschende".

4. FRISTENDE: Datum + Verfahrensart in Klammern.
   Beispiel: "5 December 2025 (submission of a project outline, two-stage procedure)"
   Bei dauerhaft offenen Calls: "continuously open"

5. FEHLENDE INFORMATIONEN: "not specified" (EN) / "Keine Angabe" (DE)

6. EIGENANTEIL: Nur wenn explizit gefordert als eigenes Feld ergänzen, sonst weglassen.

<ausschreibung>
{text}
</ausschreibung>

Ausgabe NUR in diesem Format (keine zusätzlichen Felder, keine Umsortierung):

**Title:** (Name der Ausschreibung)

**Aim:** (3–5 sachliche Sätze: Was wird gefördert? Ziel? Thematische Schwerpunkte oder
Förderbereiche? Direkt zur Sache – kein "The programme aims to" als Einstieg.)

**Target group:** (Antragstyp + antragsberechtigt Institutionen/Personen + relevante
Einschränkungen, kompakt in einem Satz oder präzisen Stichwörtern)

**Duration:** (Projektlaufzeit; bei Phasen alle nennen)

**Funding:** (Fördersumme PRO PROJEKT mit Bezugspunkt; Phasen/Varianten alle auflisten)

**Deadline:** (Datum + Verfahrensart in Klammern)

**Further information:** (URL oder "website of [Fördergeber]")"""

# ========== ZWEI SPALTEN: PROMPT | AUSSCHREIBUNGSTEXT ==========
col1, col2 = st.columns(2)

with col1:
    st.subheader("📝 Prompt")
    prompt_template = st.text_area(
        "Prompt bearbeiten (Platzhalter `{text}`)",
        value=default_prompt,
        height=400
    )

with col2:
    col2_header, col2_btn = st.columns([3, 1])
    with col2_header:
        st.subheader("📄 Ausschreibungstext")
    with col2_btn:
        st.write("")
        if st.button("🧹 Textfeld leeren"):
            st.session_state.text_area_key += 1
            st.session_state.user_text = ""
            st.session_state.url_input = ""
            st.rerun()

    user_text = st.text_area(
        "Volltext der Ausschreibung einfügen",
        value="",
        height=350,
        placeholder="Den kompletten Ausschreibungstext hier einfügen...",
        key=f"user_text_input_{st.session_state.text_area_key}"
    )
    st.session_state.user_text = user_text

    url_input = st.text_input(
        "🔗 Website / URL des Ausschreibungstextes",
        value=st.session_state.get("url_input", ""),
        placeholder="https://...",
        key=f"url_input_{st.session_state.text_area_key}"
    )
    st.session_state.url_input = url_input

# --- Großer roter Button zentriert ---
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
with col_btn2:
    summarize_clicked = st.button(
        "🚀 Ausschreibung zusammenfassen",
        use_container_width=True,
        type="primary"
    )

if summarize_clicked:
    if not st.session_state.user_text.strip():
        st.warning("Bitte Ausschreibungstext eingeben.")
    else:
        with st.spinner("Anfrage an KI:connect ..."):
            try:
                client = LLMClient(api_key=api_key_input if api_key_input else None)
                if st.session_state.selected_model:
                    client.model = st.session_state.selected_model
                final_prompt = prompt_template.replace("{text}", st.session_state.user_text)
                url = st.session_state.get("url_input", "").strip()
                if url:
                    final_prompt += (
                        f"\n\nDie URL der Ausschreibung lautet: {url}\n"
                        "Trage diese URL exakt so unter 'Further information' ein."
                    )
                # Tuple-Unpacking: (text, usage)
                response_text, usage = client.generate(final_prompt, temperature=0.1, max_tokens=2048)
                st.session_state.response = response_text
                st.session_state.translated_response = ""
                update_token_stats(usage)
            except KIConnectError as e:
                st.error(f"API-Fehler: {e}")
            except Exception as e:
                st.exception(e)

# ========== ERGEBNIS ANZEIGEN ==========
if st.session_state.response:
    st.divider()
    st.subheader("📋 Antwort (Deutsch)")
    st.markdown(st.session_state.response)

    col_down1, col_down2 = st.columns(2)
    with col_down1:
        st.download_button(
            label="📥 Als Markdown (.md)",
            data=st.session_state.response,   # garantiert ein String
            file_name="antwort_de.md",
            mime="text/markdown"
        )
    with col_down2:
        st.download_button(
            label="📄 Als Text (.txt)",
            data=st.session_state.response,
            file_name="antwort_de.txt",
            mime="text/plain"
        )

    # Übersetzungs-Button direkt unter der deutschen Antwort
    if st.button("🌐 Ins Englische übersetzen"):
        with st.spinner("Übersetze ..."):
            try:
                client = LLMClient(api_key=api_key_input if api_key_input else None)
                if st.session_state.selected_model:
                    client.model = st.session_state.selected_model
                translation_prompt = (
                    "Übersetze den folgenden deutschen Text präzise und professionell ins Englische.\n"
                    "WICHTIG: Behalte die **exakte Formatierung** bei, insbesondere **Fettdruck** "
                    "(z.B. `**Förderung:**` → `**Funding:**`).\n"
                    "Die Feldbezeichnungen MÜSSEN fett sein.\n"
                    "Antworte NUR mit der Übersetzung, ohne zusätzliche Erklärungen.\n\n"
                    f"Deutscher Text:\n{st.session_state.response}\n\nEnglische Übersetzung:"
                )
                # Tuple-Unpacking: (text, usage)
                translated_text, usage = client.generate(translation_prompt, temperature=0.1, max_tokens=2048)
                st.session_state.translated_response = translated_text
                update_token_stats(usage)
            except Exception as e:
                st.error(f"Übersetzungsfehler: {e}")

# ========== ENGLISCHE ÜBERSETZUNG ==========
if st.session_state.translated_response:
    st.divider()
    st.subheader("📋 Übersetzung (Englisch)")
    st.markdown(st.session_state.translated_response)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.download_button(
            label="📥 Übersetzung als Markdown (.md)",
            data=st.session_state.translated_response,  # garantiert ein String
            file_name="antwort_en.md",
            mime="text/markdown"
        )
    with col_t2:
        st.download_button(
            label="📄 Übersetzung als Text (.txt)",
            data=st.session_state.translated_response,
            file_name="antwort_en.txt",
            mime="text/plain"
        )
