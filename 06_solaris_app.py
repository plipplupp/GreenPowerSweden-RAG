import streamlit as st
import os
import pandas as pd
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import io
import zipfile
import tempfile
import time

# Importera nedladdningsfunktionen
from download_vectordb import download_and_extract_vectordb

# Projektets sökvägar
from src.utils.paths import PROJECT_ROOT, VECTOR_DB_DIR, RAW_DATA_DIR
import torch

# LangChain & Chroma
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# PDF Viewer
from streamlit_pdf_viewer import pdf_viewer

# ==========================================
# 0. AUTENTISERING
# ==========================================

def hash_password(password):
    """Hash ett lösenord med SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed_password):
    """Verifiera ett lösenord mot en hash"""
    return hash_password(password) == hashed_password

def check_authentication():
    """Kontrollera om användaren är inloggad"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def login_page():
    """Visa inloggningssida"""
    st.markdown("# 🔐 Logga in till Solveig")
    st.markdown("### Din AI-assistent för tillståndsprocesser och solcellsparker")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        username = st.text_input("Användarnamn", key="login_username")
        password = st.text_input("Lösenord", type="password", key="login_password")
        
        if st.button("Logga in", type="primary", width="stretch"):
            # Hämta användaruppgifter från Streamlit secrets eller environment
            valid_users = get_user_credentials()
            
            if username in valid_users:
                if verify_password(password, valid_users[username]):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.success("Inloggning lyckades!")
                    st.rerun()
                else:
                    st.error("Fel lösenord")
            else:
                st.error("Användarnamnet finns inte")
        
        st.markdown("---")
        st.caption("Kontakta administratören om du har glömt ditt lösenord.")

def get_user_credentials():
    """Hämta användaruppgifter från secrets eller environment"""
    # För Streamlit Cloud: Använd st.secrets
    # För lokal utveckling: Använd environment variables
    
    try:
        # Försök hämta från Streamlit secrets först
        if hasattr(st, 'secrets') and 'users' in st.secrets:
            return dict(st.secrets['users'])
    except:
        pass
    
    # Fallback till environment variables för lokal utveckling
    users = {}
    # Format: USER_CRED_admin=hashed_password
    # (Bytte prefix till USER_CRED_ för att undvika krock med systemvariabler som USER_ZDOTDIR)
    for key, value in os.environ.items():
        if key.startswith("USER_CRED_"):
            username = key.replace("USER_CRED_", "")
            users[username] = value
    
    # Om inga användare definierats (eller om vi kör lokalt), se till att admin finns
    if "admin" not in users:
        st.warning("⚠️ Använder default-lösenord för 'admin'. Konfigurera secrets/env för produktion!")
        # Om vi vill ha admin som fallback:
        users["admin"] = hash_password("changeme123")
    
    return users

def logout():
    """Logga ut användaren"""
    st.session_state.authenticated = False
    st.session_state.username = None
    st.rerun()

# ==========================================
# 1. KONFIGURATION OCH SETUP
# ==========================================
st.set_page_config(
    page_title="Solveig",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Kontrollera autentisering FÖRST
if not check_authentication():
    login_page()
    st.stop()

load_dotenv()

# Detektera om vi kör lokalt eller i molnet
IS_CLOUD = os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"

if IS_CLOUD:
    # Molnkonfiguration - använd relativa paths (för Streamlit Cloud)
    BASE_DIR = Path(".")
    DB_DIR = BASE_DIR / "vector_db"
    RAW_DATA_DIR = BASE_DIR / "pdfs"
else:
    # Lokal konfiguration - använd centraliserade sökvägar från src.utils.paths
    BASE_DIR = PROJECT_ROOT
    DB_DIR = VECTOR_DB_DIR
    RAW_DATA_DIR = RAW_DATA_DIR  # Redan importerad från src.utils.paths

# --- INITIERA SESSION STATE ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "Sök & Analys"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_sources" not in st.session_state:
    st.session_state.current_sources = []
if "selected_pdf" not in st.session_state:
    st.session_state.selected_pdf = None
if "selected_page" not in st.session_state:
    st.session_state.selected_page = 1
if "application_draft" not in st.session_state:
    st.session_state.application_draft = ""
if "application_inputs" not in st.session_state:
    st.session_state.application_inputs = {}
if "pdf_cache" not in st.session_state:
    st.session_state.pdf_cache = {}
if "focus_mode" not in st.session_state:
    st.session_state.focus_mode = False

# --- CSS STYLING ---
st.markdown("""
<style>
    section[data-testid="stSidebar"] button {
        width: 200px !important;
        background-color: #f8f9fa;
        color: #444;
        border: 1px solid #ddd;
        text-align: left;
        padding-left: 15px;
        transition: all 0.25s ease;
    }
   
    section[data-testid="stSidebar"] button:hover {
        background-color: #e3f2fd;
        border-color: #2196F3;
        color: #0b5394;
    }

    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #e3f2fd;
        border-color: #2196F3;
        color: #0b5394;
        font-weight: 600;
        border-left: 5px solid #2196F3;
    }

    .source-card {
        padding: 15px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 5px solid #2196F3;
    }

    div.stButton > button {
        border-radius: 6px;
        font-weight: 500;
    }
    div.row-widget.stButton > button:hover {
        border-color: #2196F3;
        color: #2196F3;
        background-color: #f0f7ff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
   
    div[data-testid="stDownloadButton"] > button {
        background-color: #4CAF50 !important;
        border-color: #4CAF50 !important;
        color: white !important;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #45a049 !important;
        border-color: #45a049 !important;
        color: white !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    }

    .stTextArea textarea { font-size: 16px !important; }
    h1 { font-size: 2.0rem; font-weight: 700; color: #2c3e50; margin-bottom: 0px; }
    h3 { font-size: 1.2rem; font-weight: 600; color: #555; margin-top: 0px; }
    
    /* Centrera PDF-visaren */
    [data-testid="stHorizontalBlock"] > div {
        display: flex;
        justify-content: center;
    }
    .st-emotion-cache-12fm70x {
        display: flex;
        justify-content: center;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LADDNING AV RESURSER
# ==========================================

def get_api_key():
    """Hämta API-nyckel från secrets eller environment"""
    try:
        if hasattr(st, 'secrets') and 'GOOGLE_API_KEY' in st.secrets:
            return st.secrets['GOOGLE_API_KEY']
    except:
        pass
    return os.environ.get('GOOGLE_API_KEY')

# Hämta Hugging Face Token
def get_hf_token():
    """Hämta Hugging Face API-nyckel från secrets eller environment"""
    try:
        if hasattr(st, 'secrets') and 'HF_TOKEN' in st.secrets:
            return st.secrets['HF_TOKEN']
    except:
        pass
    return os.environ.get('HF_TOKEN') # Fallback till environment variable

@st.cache_resource
def load_resources():
    """Ladda embeddings och LLM"""

    # Detektera enhet (GPU/MPS/CPU)
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
        
    # Använd BGE-M3
    embedding_model = HuggingFaceEmbeddings(
        model_name="BAAI/bge-m3",
        model_kwargs={'device': device},
        encode_kwargs={'normalize_embeddings': False}
    )
   
    if not DB_DIR.exists():
            if IS_CLOUD:
                with st.spinner("📥 Laddar ner och packar upp vektordatabasen... (Detta sker bara en gång)"):
                    # Anropa funktionen från din andra fil
                    success = download_and_extract_vectordb()
                    
                    if not success:
                        st.error("❌ Misslyckades att ladda ner databasen från Google Drive.")
                        return None, None
                    else:
                        st.success("✅ Databas laddad!")
            else:
                # Om vi är lokalt och den saknas
                st.error(f"⚠️ Kunde inte hitta vektordatabasen på: {DB_DIR}")
                return None, None
    
    try:
        vectordb = Chroma(
            persist_directory=str(DB_DIR),
            embedding_function=embedding_model
        )
    except Exception as e:
        st.error(f"Fel vid laddning av vektordatabas: {e}")
        return None, None
   
    api_key = get_api_key()
    if not api_key:
        st.error("⚠️ Google API-nyckel saknas. Konfigurera GOOGLE_API_KEY i secrets eller .env")
        return vectordb, None
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3,
        google_api_key=api_key
    )
   
    return vectordb, llm

vectordb, llm = load_resources()

# ==========================================
# 3. PDF-HANTERING FÖR MOLNET
# ==========================================

def get_pdf_path(relative_path):
    """Returnera korrekt PDF-sökväg beroende på miljö"""
    if IS_CLOUD:
        # I molnet: Försök hitta PDF i cache eller lokal temporär mapp
        return None  # PDFs är inte tillgängliga i molnet (se alternativ nedan)
    else:
        # Lokalt: Använd den befintliga sökvägen
        return RAW_DATA_DIR / relative_path

def show_pdf_or_message(doc_path, page_num):
    """Visa PDF om tillgänglig, annars visa hjälpsamt meddelande"""
    if IS_CLOUD:
        st.info(f"""
        📄 **Dokumentvisning i molnversionen**
        
        **Dokument:** {doc_path.name if isinstance(doc_path, Path) else Path(doc_path).name}  
        **Sida:** {page_num}
        
        I molnversionen av Solveig är PDF-visning begränsad på grund av lagringsbegränsningar.
        
        **Alternativ:**
        - Kontakta administratören för att få tillgång till originaldokumentet
        - Dokumentets innehåll är redan analyserat och tillgängligt i chattens källor
        """)
    else:
        if doc_path.exists():
            # Om vi är i fokusläge (100% bredd), använd en centrerad kolumn för att PDF:en inte ska "klistra" åt vänster
            if st.session_state.get("focus_mode", False):
                _, cent_co, _ = st.columns([1, 8, 1])
                with cent_co:
                    pdf_viewer(str(doc_path), height=800, width="100%")
            else:
                # I normalt läge är kolumnen redan smal (40%), så använd hela bredden
                pdf_viewer(str(doc_path), height=800, width="100%")
        else:
            st.error(f"❌ Fil saknas: {doc_path}")

# ==========================================
# 4. RAG FUNKTIONER
# ==========================================

def format_docs_with_sources(docs):
    formatted_texts = []
    for i, doc in enumerate(docs):
        path = doc.metadata.get("full_path", "Okänd fil")
        page = doc.metadata.get("page", "?")
        content = doc.page_content
        formatted_texts.append(f"DOKUMENT ID [{i+1}]:\nSökväg: {path} (Sida {page})\nINNEHÅLL: {content}\n----------------")
    return "\n\n".join(formatted_texts)

def get_rag_response(question, system_prompt, k=10):
    if not vectordb or not llm:
        return "⚠️ Systemet är inte korrekt konfigurerat. Kontakta administratören.", []
    
    retriever = vectordb.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)
    context_text = format_docs_with_sources(docs)
   
    prompt_template = f"""
    {system_prompt}
   
    VIKTIGA INSTRUKTIONER FÖR ANALYS:
    1. Granska den tillhandahållna kontexten noggrant.
    2. Om kontexten INTE innehåller **relevant** information som kan besvara FRÅGAN, svara då: "Jag har granskat de tillhandahållna dokumenten och kan konstatera att det inte finns tillräcklig information om [ämnet i frågan] i dessa."
    3. Svara ALDRIG på en fråga om kontexten är tom eller irrelevant.

    VIKTIGA INSTRUKTIONER FÖR KÄLLOR (endast om svar kan ges):
    1. Du har tillgång till numrerade dokument, t.ex. "DOKUMENT ID [1]".
    2. När du använder information från ett dokument, lägg till en hänvisning i fetstil direkt efter meningen.
    3. Formatet SKA vara: **[Källa: X]** (där X är dokumentets ID-nummer).
    4. Skriv INTE ut filnamnet i löptexten, använd bara numret.
   
    ANVÄND FÖLJANDE KONTEXT:
    {{context}}
   
    FRÅGA:
    {{question}}
    """
   
    prompt = ChatPromptTemplate.from_template(prompt_template)
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context_text, "question": question})
    return answer, docs

# ==========================================
# 5. SIDA: CHATT
# ==========================================
def show_chat_page():
    st.markdown("# Välkommen till chatbotten Solveig ☀️🔋")
    st.markdown("### Din AI-assistent för tillståndsprocesser och solcellsparker.")
    st.divider()

    # Logik för dynamisk layout
    if st.session_state.focus_mode:
        # I fokusläge visar vi BARA referenskolumnen (ingen st.columns behövs)
        show_references_section()
    else:
        # Normalt läge: 60/40 split
        col_chat, col_ref = st.columns([6, 4], gap="large")

        with col_chat:
            st.header("💬 Chatt")
            
            chat_container = st.container()
            
            with chat_container:
                for message in st.session_state.messages:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

            if prompt := st.chat_input("Ex: Hur motiverar man byggnation på jordbruksmark?"):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with chat_container:
                    with st.chat_message("user"):
                        st.markdown(prompt)
                
                with chat_container:
                    with st.chat_message("assistant"):
                        with st.spinner("Söker och analyserar..."):
                            sys_prompt = "Du är Solveig Legal. Svara professionellt på svenska och använd sakliga termer."
                            response, docs = get_rag_response(prompt, sys_prompt, k=10)
                            st.markdown(response)

                NEGATIVE_PHRASE = "Jag har granskat de tillhandahållna dokumenten"
                if response.strip().startswith(NEGATIVE_PHRASE):
                    final_sources = []
                else:
                    final_sources = docs
                
                st.session_state.messages.append({"role": "assistant", "content": response})
                st.session_state.current_sources = final_sources
                st.session_state.selected_pdf = None
                st.rerun()
                
            st.write("")
            if st.session_state.messages:
                if st.button("🗑️ Rensa historik", type="secondary", width="stretch"):
                    st.session_state.messages = []
                    st.session_state.current_sources = []
                    st.session_state.selected_pdf = None
                    st.rerun()

        with col_ref:
            show_references_section()

def show_references_section():
    """Hjälpfunktion för att visa referenssektionen (används i både normalt och fokusläge)"""
    st.header("📄 Källor & Dokument")
    
    # Knapp för att växla fokusvy
    focus_label = "🏥 Lämna fokusvy (visa chatt)" if st.session_state.focus_mode else "🔍 Fokusvy (maximera dokument)"
    if st.button(focus_label, type="secondary", use_container_width=True):
        st.session_state.focus_mode = not st.session_state.focus_mode
        st.rerun()
    
    st.divider()
    
    if st.session_state.selected_pdf:
        doc_path = st.session_state.selected_pdf
        page = st.session_state.selected_page
        
        if st.button("⬅️ Tillbaka till listan"):
            st.session_state.selected_pdf = None
            st.session_state.selected_page = 1
            st.rerun()
        
        st.markdown(f"**Visar:** `{doc_path.name if isinstance(doc_path, Path) else Path(doc_path).name}` (Sida {page})")
        show_pdf_or_message(doc_path, page)

    elif st.session_state.current_sources:
        st.info(f"Listan visar de **{len(st.session_state.current_sources)}** mest relevanta dokumenten som analyserades i sökningen. Källhänvisningarna i chatten (t.ex. **[Källa: 7]**) refererar till dokumentets nummer i denna lista.")
        
        sources_container = st.container(border=False)
        
        with sources_container:
            for i, doc in enumerate(st.session_state.current_sources):
                citation_id = i + 1
                path_str = doc.metadata.get("full_path")
                page_num = doc.metadata.get("page")
                full_os_path = get_pdf_path(path_str) if not IS_CLOUD else Path(path_str)
                
                with st.container():
                    st.markdown(f"""
                    <div class="source-card">
                        <b>[Källa {citation_id}] {Path(path_str).name}</b><br>
                        <span style="color:#555; font-size:0.9em;">Sida {page_num}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    c_open, c_path, c_text = st.columns([1, 1, 1])
                    
                    with c_open:
                        if st.button(f"📄 Visa källa", key=f"open_{i}"):
                            st.session_state.selected_pdf = full_os_path
                            st.session_state.selected_page = page_num
                            st.rerun()
                    
                    with c_path:
                        with st.popover("📂 Visa sökväg"):
                            st.code(path_str, language="text")
                            
                    with c_text:
                        with st.popover("📝 Läs avsnitt"):
                            st.caption(doc.page_content)

                    st.markdown("")
    else:
        st.info("Källor visas här när du ställer en fråga.")

# ==========================================
# 6. SIDA: SKAPA ANSÖKAN
# ==========================================
def show_application_page():
    st.title("📝 Skapa Ansökan")
    st.markdown("### Generera utkast till en **Samrådsanmälan** baserat på tidigare data.")

    default_inputs = st.session_state.get("application_inputs", {})

    with st.form("application_input"):
        st.subheader("Projektinformation")
        
        with st.container():
            project_name = st.text_input("Projektnamn", value=default_inputs.get("project_name", "Solpark Ekbacken"))
            kommun = st.text_input("Kommun & Län", value=default_inputs.get("kommun", "Kalmar kommun, Kalmar län"))
            size = st.text_input("Storlek/Effekt", value=default_inputs.get("size", "45 hektar, ca 30 MW"))
            
            marktyp = st.text_area("Beskriv marktypen",
                                    value=default_inputs.get("marktyp", "Lågproduktiv jordbruksmark som delvis är igenväxt. Ligger nära skogskant."),
                                    height=100)
            naturvarden = st.text_area("Naturvärden & Skydd",
                                        value=default_inputs.get("naturvarden", "Området ligger inte inom Natura 2000. Finns diken i söder."),
                                        height=100)

        col_left, col_center, col_right = st.columns([1, 3, 1])
        
        with col_center:
            submitted = st.form_submit_button("✨ Generera Utkast", type="primary", width="stretch")
            clear_form = st.form_submit_button("🔄 Rensa Input", type="secondary", width="stretch")

    if clear_form:
        st.session_state.application_inputs = {}
        st.session_state.application_draft = ""
        st.rerun()

    if submitted:
        st.session_state.application_inputs = {
            "project_name": project_name, "kommun": kommun, "size": size,
            "marktyp": marktyp, "naturvarden": naturvarden
        }

        full_draft_text = f"""# SAMRÅDSANMÄLAN - UTKAST\n**Projekt:** {project_name}\n**Datum:** {pd.Timestamp.now().strftime('%Y-%m-%d')}\n\n---"""
        
        st.divider()
        st.subheader(f"Utkast: {project_name}")
        
        with st.status("🔍 Del 1/2: Analyserar markval...", expanded=True):
            query_loc = f"Argument för att bygga solceller på {marktyp} i {kommun}. Hur motiverar man intrång på jordbruksmark för ett projekt på {size}?"
            sys_prompt = "Du ska skriva avsnittet 'Lokalisering' och vara saklig. Använd fetstil för källhänvisning [Källa: X]."
            
            text_loc, docs_loc = get_rag_response(query_loc, sys_prompt)
            st.write("Klar.")
            
            full_draft_text += f"\n## 1. LOKALISERING & MARKVAL\n{text_loc}\n\n**Referenser för Lokalisering och markval (Ursprungliga ID:n):**\n"
            for i, d in enumerate(docs_loc):
                full_draft_text += f"- [{i+1}] {d.metadata.get('full_path')} (Sid {d.metadata.get('page')})\n"
            
            # Lägg till en paus på 2 sekunder mellan de två anropen
            time.sleep(2)
        
        with st.status("🌱 Del 2/2: Tar fram skyddsåtgärder...", expanded=True):
            query_env = f"Vilka skyddsåtgärder krävs för {naturvarden} vid anläggning av en solcellspark? Beskriv även miljöpåverkan."
            sys_prompt = "Du ska skriva avsnittet 'Miljöpåverkan och skyddsåtgärder'. Använd fetstil för källhänvisning [Källa: X]."
            
            text_env, docs_env = get_rag_response(query_env, sys_prompt)
            st.write("Klar.")

            full_draft_text += f"\n## 2. MILJÖPÅVERKAN OCH SKYDDSÅTGÄRDER\n{text_env}\n\n**Referenser för Miljöpåverkan (Ursprungliga ID:n):**\n"
            for i, d in enumerate(docs_env):
                full_draft_text += f"- [{i+1}] {d.metadata.get('full_path')} (Sid {d.metadata.get('page')})\n"

        st.session_state.application_draft = full_draft_text
        st.success("Utkastet är färdigt!")

    if st.session_state.application_draft:
        st.markdown(st.session_state.application_draft)
        st.divider()
        
        safe_name = st.session_state.application_inputs.get("project_name", "Utkast").replace(" ", "_").replace(":", "").replace("/", "")
        
        col_dl_left, col_dl_center, col_dl_right = st.columns([1, 3, 1])
        with col_dl_center:
            st.download_button(
                label="💾 Ladda ner Ansökan (.md)",
                data=st.session_state.application_draft,
                file_name=f"Ansokan_{safe_name}.md",
                mime="text/markdown",
                type="primary",
                use_container_width=True
            )
            if st.button("🗑️ Rensa Genererat Utkast", use_container_width=True, type="secondary"):
                st.session_state.application_draft = ""
                st.rerun()

# ==========================================
# 7. NAVIGATION & MENY
# ==========================================
def main():
    LOGO_PATH = BASE_DIR / "assets" / "gps-logo.svg"

    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        else:
            st.header("Chatboten Solveig")
        
        st.divider()
        
        # Visa inloggad användare
        if st.session_state.get("username"):
            st.caption(f"👤 Inloggad som: **{st.session_state.username}**")
        
        if st.button("🔎  Sök & Analys", type="primary" if st.session_state.current_page == "Sök & Analys" else "secondary"):
            st.session_state.current_page = "Sök & Analys"
            st.rerun()
            
        if st.button("📝  Skapa Ansökan", type="primary" if st.session_state.current_page == "Skapa Ansökan" else "secondary"):
            st.session_state.current_page = "Skapa Ansökan"
            st.rerun()
        
        st.divider()
        
        if st.button("🚪 Logga ut", type="secondary"):
            logout()

    if st.session_state.current_page == "Sök & Analys":
        show_chat_page()
    elif st.session_state.current_page == "Skapa Ansökan":
        show_application_page()

if __name__ == "__main__":
    main()