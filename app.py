"""
Streamlit Web-App für Beta-Newsletter Förderausschreibungen.
Analyse direkt aus eingefügtem Volltext.
"""

import os
import logging
import sys

import streamlit as st

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

from summarizer import summarize_text
from llm_client import LLMClient, KIConnectError

st.set_page_config(
    page_title="Beta-Newsletter",
    page_icon="📰",
    layout="wide"
)

st.title("📰 Beta-Newsletter – Förderausschreibungen")
st.markdown("Füge den **Volltext** einer Förderausschreibung ein – das Tool extrahiert automatisch die D7‑Newsletter‑Felder.")

# Session State für Modelle und Ergebnisse
if 'available_models' not in st.session_state:
    st.session_state.available_models = []
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = None
if 'last_result' not in st.session_state:
    st.session_state.last_result = None

with st.sidebar:
    st.header("⚙️ Konfiguration")

    api_key_input = st.text_input(
        "KIConnect API-Key",
        type="password",
        placeholder="Aus Umgebungsvariable/Secrets",
        help="API-Key hier eingeben oder als KICONNECT_API_KEY setzen."
    )

    if st.button("🔌 API-Verbindung testen & Modelle laden"):
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
    else:
        st.divider()
        st.markdown("**Keine Modelle geladen. Bitte Verbindung testen.**")

    st.divider()
    st.markdown("---")
    st.caption("Beta-Newsletter v0.5.0 – Textanalyse")

# Hauptbereich: Texteingabe
text_input = st.text_area(
    "Volltext der Ausschreibung einfügen:",
    height=300,
    placeholder="Den kompletten Text der Bekanntmachung hier einfügen..."
)

col1, col2, col3 = st.columns([1, 1, 3])
with col1:
    analyze_button = st.button("🔍 Text analysieren", type="primary")
with col2:
    clear_button = st.button("🧹 Eingabe löschen")

if clear_button:
    st.session_state.last_result = None
    st.rerun()

if analyze_button and text_input:
    with st.spinner("Analysiere Text... "):
        try:
            client = LLMClient(api_key=api_key_input if api_key_input else None)
            if st.session_state.selected_model:
                client.model = st.session_state.selected_model

            result = summarize_text(text_input.strip(), client=client)
            st.session_state.last_result = result

        except KIConnectError as e:
            st.error(f"API-Fehler: {e}")
        except Exception as e:
            st.exception(e)
            st.error("Ein unerwarteter Fehler ist aufgetreten.")

# Ergebnis anzeigen
if st.session_state.last_result:
    st.divider()
    st.subheader("📋 D7-Newsletter-Eintrag")
    res = st.session_state.last_result
    if res["status"] == "success":
        st.markdown(res["summary"])
        # Download-Button
        st.download_button(
            label="📥 Als Markdown herunterladen",
            data=res["summary"],
            file_name=f"{res.get('title', 'ausschreibung')[:30]}.md",
            mime="text/markdown"
        )
    else:
        st.error(f"Fehler: {res.get('error', 'Unbekannter Fehler')}")

elif analyze_button:
    st.warning("Bitte Text einfügen.")

st.sidebar.markdown("---")
st.sidebar.caption("Beta-Newsletter v0.5.0")
