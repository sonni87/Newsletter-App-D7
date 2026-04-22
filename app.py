"""
Streamlit App – Prompt-Client für KI:connect mit Übersetzungsoption.
Standardmäßig deutsche Analyse, bei Bedarf Übersetzung ins Englische.
"""

import streamlit as st
from llm_client import LLMClient, KIConnectError

st.set_page_config(page_title="KI:connect Prompt", page_icon="🤖", layout="wide")
st.title("🤖 KI:connect – Flexibler Prompt‑Client mit Übersetzung")
st.markdown("Gib deinen Prompt und den Ausschreibungstext ein. Die Antwort wird im Markdown‑Format ausgegeben und kann exportiert werden.")

# Session State
if "response" not in st.session_state:
    st.session_state.response = ""
if "translated_response" not in st.session_state:
    st.session_state.translated_response = ""
if "available_models" not in st.session_state:
    st.session_state.available_models = []
if "selected_model" not in st.session_state:
    st.session_state.selected_model = None

# Sidebar
with st.sidebar:
    st.header("⚙️ Konfiguration")
    api_key_input = st.text_input(
        "KIConnect API-Key",
        type="password",
        placeholder="Aus Umgebungsvariable/Secrets",
        help="Wird automatisch aus Streamlit Secrets oder KICONNECT_API_KEY geladen."
    )

    if st.button("🔌 Verbindung testen & Modelle laden"):
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

    st.divider()
    temperature = st.slider("Temperature", 0.0, 1.0, 0.1, 0.05)
    max_tokens = st.number_input("Max Tokens", 100, 4096, 2048, 100)

# Standard-Prompt (Deutsch)
default_prompt = """Du bist Experte für Forschungsförderung und erstellst Einträge für einen Fördernewsletter (D7-Format).
Analysiere den folgenden Text einer Förderausschreibung und erstelle eine kurze, strukturierte Zusammenfassung mit diesen Feldern:

**Förderung:** (4-6 Sätze: Was wird gefördert? Was ist das Ziel? Welche Kosten sind förderfähig?)
**Zielgruppe:** (Wer ist antragsberechtigt? Welche Einrichtungen/Personen?)
**Dauer:** (Projektlaufzeit, falls nicht genannt "Keine Angabe")
**Förderhöhe:** (Maximale Fördersumme oder Prozentangabe, sonst "Keine Angabe")
**Fristende:** (Einreichungsfrist, sonst "Keine Angabe")
**Website:** (URL der Ausschreibung)

Text der Ausschreibung:
{text}

Antworte NUR mit den formatierten Feldern. Keine zusätzlichen Erklärungen."""

# Zwei Spalten für Prompt und Ausschreibungstext
col1, col2 = st.columns(2)
with col1:
    st.subheader("📝 Prompt")
    prompt_template = st.text_area(
        "Prompt bearbeiten (Platzhalter `{text}`)",
        value=default_prompt,
        height=400
    )
with col2:
    st.subheader("📄 Ausschreibungstext")
    user_text = st.text_area(
        "Volltext der Ausschreibung einfügen",
        height=400,
        placeholder="Den kompletten Ausschreibungstext hier einfügen..."
    )

# Analyse-Button
if st.button("🚀 Prompt senden", type="primary"):
    if not user_text.strip():
        st.warning("Bitte Ausschreibungstext eingeben.")
    else:
        with st.spinner("Anfrage an KI:connect ..."):
            try:
                client = LLMClient(api_key=api_key_input if api_key_input else None)
                if st.session_state.selected_model:
                    client.model = st.session_state.selected_model
                final_prompt = prompt_template.replace("{text}", user_text)
                response = client.generate(final_prompt, temperature=temperature, max_tokens=max_tokens)
                st.session_state.response = response
                st.session_state.translated_response = ""  # Reset Übersetzung
            except KIConnectError as e:
                st.error(f"API-Fehler: {e}")
            except Exception as e:
                st.exception(e)

# Ergebnis anzeigen
if st.session_state.response:
    st.divider()
    st.subheader("📋 Antwort (Deutsch)")
    st.markdown(st.session_state.response)

    col_down1, col_down2 = st.columns(2)
    with col_down1:
        st.download_button(
            label="📥 Als Markdown (.md)",
            data=st.session_state.response,
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

# --- Übersetzungsbereich ---
st.divider()
st.subheader("🌐 Übersetzung (Deutsch → Englisch)")
st.markdown("Füge hier einen deutschen Text ein, um ihn ins Englische übersetzen zu lassen.")

col_trans1, col_trans2 = st.columns([3, 1])
with col_trans1:
    text_to_translate = st.text_area(
        "Zu übersetzender Text",
        height=150,
        placeholder="Deutschen Text hier einfügen...",
        key="translate_input"
    )
with col_trans2:
    st.write("")
    st.write("")
    translate_btn = st.button("🔄 Übersetzen", type="secondary")

if translate_btn and text_to_translate.strip():
    with st.spinner("Übersetze ..."):
        try:
            client = LLMClient(api_key=api_key_input if api_key_input else None)
            if st.session_state.selected_model:
                client.model = st.session_state.selected_model
            translation_prompt = f"""Übersetze den folgenden deutschen Text präzise und professionell ins Englische. 
Behalte die Formatierung (z.B. **Fettdruck**, Aufzählungen) bei.
Antworte NUR mit der Übersetzung, ohne zusätzliche Erklärungen.

Deutscher Text:
{text_to_translate}

Englische Übersetzung:"""
            translated = client.generate(translation_prompt, temperature=0.1, max_tokens=max_tokens)
            st.session_state.translated_response = translated
        except Exception as e:
            st.error(f"Übersetzungsfehler: {e}")

if st.session_state.translated_response:
    st.subheader("📋 Übersetzung (Englisch)")
    st.markdown(st.session_state.translated_response)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.download_button(
            label="📥 Übersetzung als Markdown (.md)",
            data=st.session_state.translated_response,
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
