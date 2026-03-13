import streamlit as st
import os
import pandas as pd
import hashlib
import json
import bcrypt
import threading
from pathlib import Path
from dotenv import load_dotenv
import io
import zipfile
import tempfile
import time
from datetime import datetime

# Projektets sökvägar
from src.utils.paths import PROJECT_ROOT, VECTOR_DB_DIR, RAW_DATA_DIR

# Användarhantering (delad modul)
from src.utils.user_management import (
    load_users, save_users, create_user, delete_user, reset_user_password,
    hash_password_bcrypt, verify_password_bcrypt, verify_password_smart,
    hash_password_sha256, validate_password, password_strength,
    generate_multiple_passwords, generate_secrets_toml_snippet,
    update_secrets_file, get_user_credentials_from_file, is_admin,
    get_user_role, USERS_FILE
)

# Bakgrundsladdare för att snabba upp uppstarten
def prewarm_resources_silent():
    """Importerar tunga moduler i bakgrunden så att de redan finns i cachen när användaren loggat in."""
    try:
        import torch
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Vi försöker inte anropa streamlit-funktioner härifrån för att undvika kontext-fel
    except:
        pass

# Starta bakgrundsladdningen direkt
threading.Thread(target=prewarm_resources_silent, daemon=True).start()

# ==========================================
# 0. AUTENTISERING
# ==========================================

def hash_password(password):
    """Hash ett lösenord med SHA-256 (legacy/fallback). Wrapper runt delad modul."""
    return hash_password_sha256(password)

def check_authentication():
    """Kontrollera om användaren är inloggad"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    return st.session_state.authenticated

def login_page():
    """Visa inloggningssida"""
    st.markdown("<h1 style='text-align:center'>🔐 Logga in till Solveig</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; color:#555;'>Din AI-assistent för tillståndsprocesser och solcellsparker</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        username = st.text_input("Användarnamn", key="login_username")
        password = st.text_input("Lösenord", type="password", key="login_password")
        
        if st.button("Logga in", type="primary", width="stretch"):
            # Hämta användaruppgifter
            valid_users = get_user_credentials()
            
            # Normalisera användarnamn till lowercase
            username_lower = username.strip().lower()
            
            if username_lower in valid_users:
                if verify_password_smart(password, valid_users[username_lower]):
                    st.session_state.authenticated = True
                    st.session_state.username = username_lower
                    st.success("Inloggning lyckades!")
                    st.rerun()
                else:
                    st.error("Fel lösenord")
            else:
                st.error("Användarnamnet finns inte")
        
        st.markdown("---")
        st.caption("Kontakta administratören om du har glömt ditt lösenord.")

def get_user_credentials():
    """Hämta användaruppgifter – prioriterar users.json (admin-verktyget), 
    sedan secrets.toml, sedan environment variables."""
    # 1. Primärkälla: users.json (delad modul)
    users = get_user_credentials_from_file()
    
    # 2. Streamlit secrets (för Streamlit Cloud / HF Spaces)
    if not users:
        try:
            if hasattr(st, 'secrets'):
                # Kolla efter USERS_DICT (smidigaste sättet för många användare på HF)
                if 'USERS_DICT' in st.secrets:
                    try:
                        import json
                        # Kan vara antingen en sträng (från env) eller ett objekt (från secrets.toml)
                        u_dict = st.secrets['USERS_DICT']
                        if isinstance(u_dict, str):
                            users_data = json.loads(u_dict)
                        else:
                            users_data = dict(u_dict)
                        
                        for uname, pw_hash in users_data.items():
                            users[uname.lower().strip()] = pw_hash
                    except Exception as e:
                        st.error(f"Fel vid inläsning av USERS_DICT: {e}")
                
                # Fallback: Kolla efter [users]-sektionen (från lokala secrets.toml)
                if 'users' in st.secrets:
                    for uname, pw_hash in dict(st.secrets['users']).items():
                        users[uname.lower().strip()] = pw_hash
        except:
            pass
    
    # 3. Fallback: Environment variables (Viktigt för HF Spaces)
    if not users:
        u_dict_env = os.environ.get('USERS_DICT')
        if u_dict_env:
            try:
                import json
                users_data = json.loads(u_dict_env)
                # Spara roller i session state för senare bruk (eftersom USERS_FILE saknas i molnet)
                if "user_roles" not in st.session_state:
                    st.session_state.user_roles = {}
                
                for uname, data in users_data.items():
                    u_lower = uname.lower().strip()
                    if isinstance(data, dict):
                        users[u_lower] = data.get("password_hash")
                        st.session_state.user_roles[u_lower] = data.get("role", "user")
                    else:
                        users[u_lower] = data
                        # Om det bara är en hash, gissa roll (admin/maddovdv är admin)
                        role = "admin" if u_lower in ["admin", "maddovdv"] else "user"
                        st.session_state.user_roles[u_lower] = role
            except Exception as e:
                print(f"DEBUG: Kunde inte parsa USERS_DICT: {e}")
                pass
    
    # 4. Om inga användare definierats alls, visa varning
    if not users:
        st.warning("⚠️ Inga användare konfigurerade. Kontrollera dina Secrets på Hugging Face.")
        users["admin"] = hash_password_sha256("solveig2024")
    
    return users

def is_admin_cloud(username):
    """Special-version av is_admin för molnet som kollar session_state"""
    if not IS_CLOUD:
        from src.utils.user_management import is_admin
        return is_admin(username)
    
    # I molnet litar vi på de roller vi laddade in i login-steget
    if "user_roles" in st.session_state:
        return st.session_state.user_roles.get(username.lower(), "user") == "admin"
    
    # Fallback om något gått snett
    return username.lower() in ["admin", "maddovdv"]


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

# --- TUNGA IMPORTER (Händer bara efter inlogg) ---
import torch
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from streamlit_pdf_viewer import pdf_viewer
from download_vectordb import download_and_extract_vectordb

load_dotenv()

# Detektera om vi kör lokalt eller i molnet
IS_CLOUD = os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud" or "SPACE_ID" in os.environ

if IS_CLOUD:
    # Molnkonfiguration - använd relativa paths (för Streamlit Cloud)
    BASE_DIR = Path(".")
    DB_DIR = BASE_DIR / "vector_db_bgem3"
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

from huggingface_hub import hf_hub_download

def get_pdf_path(relative_path):
    """Returnera korrekt PDF-sökväg beroende på miljö"""
    if IS_CLOUD:
        # I molnet: Ladda ner filen från Hugging Face dataset (löser problemet med 18 GB utan att fylla repot!)
        try:
            repo_id = "greenpowersweden/solveig-data"
            token = get_hf_token()
            file_name = Path(relative_path).name
            
            cached_path = hf_hub_download(
                repo_id=repo_id, 
                repo_type="dataset", 
                filename=file_name, 
                token=token
            )
            return Path(cached_path)
        except Exception as e:
            return None
    else:
        # Lokalt: Använd den befintliga sökvägen
        return RAW_DATA_DIR / relative_path

def show_pdf_or_message(doc_path, page_num):
    """Visa PDF om tillgänglig, annars visa hjälpsamt meddelande"""
    if doc_path is None or not doc_path.exists():
        if IS_CLOUD:
            st.info(f"""
            📄 **Dokumentvisning tillfälligt otillgänglig**
            
            Kunde inte hämta dokumentet från molndatasetet. 
            Detta kan bero på att `HF_TOKEN` saknas i Streamlit Secrets eller att filen ännu laddas upp.
            
            **Alternativ:**
            - Dokumentets innehåll är redan analyserat och tillgängligt i chattens källor.
            """)
        else:
            st.error(f"❌ Fil saknas: {doc_path}")
        return

    # Om vi har doc_path och den existerar (lokalt eller cachad i molnet)
    if st.session_state.get("focus_mode", False):
        _, cent_co, _ = st.columns([1, 8, 1])
        with cent_co:
            pdf_viewer(str(doc_path), height=800, width="100%")
    else:
        # I normalt läge är kolumnen redan smal (40%), så använd hela bredden
        pdf_viewer(str(doc_path), height=800, width="100%")

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
    # Centrera och dra in sidans innehåll med marginaler
    _, page_col, _ = st.columns([1, 8, 1])
    with page_col:
        st.markdown("<h1 style='text-align:center'>📝 Skapa Ansökan</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#555; font-size:1.1rem;'>Generera utkast till en <strong>Samrådsanmälan</strong> baserat på tidigare data.</p>", unsafe_allow_html=True)
    st.markdown("")
    _, main_col, _ = st.columns([1, 8, 1])
    with main_col:

        default_inputs = st.session_state.get("application_inputs", {})

        with st.form("application_input"):
            st.subheader("Projektinformation")
            
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
# 7. SIDA: ADMIN (BARA FÖR ADMINS)
# ==========================================
def show_admin_page():
    """Admin-sida för användarhantering – syns bara för admin-användare."""
    # Centrera rubriker och dra in sidans innehåll med marginaler
    _, hdr_col, _ = st.columns([1, 8, 1])
    with hdr_col:
        st.markdown("<h1 style='text-align:center'>🔧 Användarhantering</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#555; font-size:1.1rem;'>Hantera användare och behörigheter i Solveig</p>", unsafe_allow_html=True)
    st.markdown("")
    _, page_col, _ = st.columns([1, 8, 1])
    with page_col:
    
        users = load_users()
        current_user = st.session_state.get("username", "")
        
        # Statistik
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Registrerade användare", len(users))
        with col2:
            admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
            st.metric("Administratörer", admin_count)
        with col3:
            st.metric("Vanliga användare", len(users) - admin_count)
        
        st.markdown("")
    
        # Tabs
        tab_add, tab_users, tab_export = st.tabs([
            "➕ Lägg till användare", 
            "👥 Hantera användare",
            "📋 Exportera / Secrets"
        ])
    
    # ======================
    # TAB 1: Lägg till
    # ======================
    with tab_add:
        st.markdown("")
        st.subheader("Skapa ny användare")
        
        col_form, col_preview = st.columns([3, 2], gap="large")
        
        with col_form:
            new_username = st.text_input(
                "Användarnamn",
                placeholder="t.ex. anna.svensson",
                help="Användarnamnet kan innehålla bokstäver, siffror, punkt och understreck.",
                key="admin_new_username"
            )
            
            # Lösenordsgenerator
            st.markdown("**Lösenord**")
            if "generated_passwords" not in st.session_state:
                st.session_state.generated_passwords = []
            
            col_pw_input, col_pw_gen = st.columns([3, 1])
            with col_pw_input:
                new_password = st.text_input(
                    "Lösenord",
                    type="password",
                    placeholder="Minst 8 tecken...",
                    help="Lösenordet hashas med bcrypt innan det sparas.",
                    key="admin_new_password",
                    label_visibility="collapsed"
                )
            with col_pw_gen:
                if st.button("☀️ Generera", use_container_width=True, key="gen_pw_btn"):
                    st.session_state.generated_passwords = generate_multiple_passwords(5)
            
            # Visa genererade lösenord
            if st.session_state.generated_passwords:
                st.markdown("**Förslag** *(klicka för att kopiera)*:")
                for i, pw in enumerate(st.session_state.generated_passwords):
                    st.code(pw, language=None)
                
                if st.button("🔄 Generera nya förslag", key="regen_pw_btn"):
                    st.session_state.generated_passwords = generate_multiple_passwords(5)
                    st.rerun()
            
            confirm_password = st.text_input(
                "Bekräfta lösenord",
                type="password",
                placeholder="Upprepa lösenordet...",
                key="admin_confirm_password"
            )
            
            st.caption("🔒 Rollen sätts alltid till Användare. Skapa admins via det fristående `admin.py`-verktyget.")
        
        with col_preview:
            st.markdown("**Lösenordskrav:**")
            if new_password:
                strength_text, strength_color, strength_val = password_strength(new_password)
                
                checks = [
                    ("✅" if len(new_password) >= 8 else "❌", "Minst 8 tecken"),
                    ("✅" if any(c.isupper() for c in new_password) else "❌", "En versal (A-Z)"),
                    ("✅" if any(c.islower() for c in new_password) else "❌", "En gemen (a-z)"),
                    ("✅" if any(c.isdigit() for c in new_password) else "❌", "En siffra (0-9)"),
                    ("✅" if any(c in "!@#$%^&*()_+-=[]{}|;':"",./<>?" for c in new_password) else "➖", "Specialtecken (valfritt)"),
                ]
                
                for icon, text in checks:
                    st.markdown(f"{icon} {text}")
                
                st.markdown("")
                if strength_text == "Svagt":
                    st.markdown(f"**Styrka:** 🔴 {strength_text}")
                elif strength_text == "Medel":
                    st.markdown(f"**Styrka:** 🟡 {strength_text}")
                else:
                    st.markdown(f"**Styrka:** 🟢 {strength_text}")
                st.progress(strength_val)
            else:
                st.caption("Ange ett lösenord för att se kraven.")
        
        st.markdown("")
        
        if st.button("✅ Skapa användare", type="primary", use_container_width=True, key="admin_create_btn"):
            # Rollen är alltid 'user' inifrån appen – admins skapas via admin.py
            if not new_password:
                st.error("Lösenord får inte vara tomt.")
            elif new_password != confirm_password:
                st.error("Lösenorden matchar inte.")
            else:
                ok, msg = create_user(new_username, new_password, role="user", created_by=current_user)
                if ok:
                    st.success(f"✅ {msg} Secrets.toml uppdaterades automatiskt.")
                    st.balloons()
                    time.sleep(2.0)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    # ======================
    # TAB 2: Hantera
    # ======================
    with tab_users:
        st.markdown("")
        st.subheader("Registrerade användare")
        
        # Ladda om användare (kan ha ändrats i tab 1)
        users = load_users()
        
        if not users:
            st.info("Inga användare registrerade ännu. Gå till fliken 'Lägg till användare' för att skapa den första.")
        else:
            for username, info in sorted(users.items()):
                role_label = "🔧 Admin" if info.get("role") == "admin" else "👤 Användare"
                created = info.get("created_at", "Okänt")
                if created != "Okänt":
                    try:
                        dt = datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.markdown(f"**{username}**")
                        st.caption(role_label)
                    with c2:
                        st.caption(f"Skapad: {created}")
                    with c3:
                        if username == current_user:
                            st.caption("(du)")
            
            st.markdown("")
            st.divider()
            
            # Åtgärder
            col_action1, col_action2 = st.columns(2, gap="medium")
            
            with col_action1:
                st.markdown("**🔄 Återställ lösenord**")
                # Admins kan bara återställa lösenord för vanliga användare
                # eller sig själva – inte för andra admins.
                resettable = sorted([
                    u for u in users.keys()
                    if users[u].get("role") != "admin" or u == current_user
                ])
                st.caption("🔒 Andra adminers lösenord kan bara återställas via `admin.py`.")
                reset_user_sel = st.selectbox(
                    "Välj användare",
                    options=resettable,
                    key="app_reset_user_select"
                )
                
                # Lösenordsgenerator för reset
                col_reset_pw, col_reset_gen = st.columns([3, 1])
                with col_reset_pw:
                    new_pw = st.text_input(
                        "Nytt lösenord",
                        type="password",
                        key="app_reset_new_pw",
                        placeholder="Nytt lösenord..."
                    )
                with col_reset_gen:
                    st.markdown("")
                    if st.button("☀️", key="gen_reset_pw_btn", help="Generera lösenord"):
                        suggestions = generate_multiple_passwords(3)
                        st.session_state.reset_pw_suggestions = suggestions
                
                if st.session_state.get("reset_pw_suggestions"):
                    for pw in st.session_state.reset_pw_suggestions:
                        st.code(pw, language=None)
                
                confirm_pw = st.text_input(
                    "Bekräfta nytt lösenord",
                    type="password",
                    key="app_reset_confirm_pw",
                    placeholder="Bekräfta..."
                )
                
                if st.button("🔄 Uppdatera lösenord", use_container_width=True, key="app_reset_btn"):
                    if not new_pw:
                        st.error("Ange ett nytt lösenord.")
                    elif new_pw != confirm_pw:
                        st.error("Lösenorden matchar inte.")
                    else:
                        ok, msg = reset_user_password(reset_user_sel, new_pw)
                        if ok:
                            st.success(f"✅ {msg}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
            
            with col_action2:
                st.markdown("**🗑️ Ta bort användare**")
                
                # Bara vanliga användare (ej admins) kan tas bort inifrån appen.
                # Admins kan bara tas bort via det fristående admin.py-verktyget.
                deletable = [
                    u for u in users.keys()
                    if users[u].get("role") != "admin"
                ]
                
                if not deletable:
                    st.info("Inga vanliga användare att ta bort.")
                    st.caption("🔒 Admins kan bara tas bort via det fristående `admin.py`-verktyget.")
                else:
                    del_user_sel = st.selectbox(
                        "Välj användare att ta bort",
                        options=sorted(deletable),
                        key="app_delete_user_select"
                    )
                    
                    st.warning(f"⚠️ Att ta bort **{del_user_sel}** kan inte ångras!")
                    st.caption("🔒 Admins visas inte här – de kan bara tas bort via `admin.py`.")
                    
                    confirm_del = st.text_input(
                        f"Skriv '{del_user_sel}' för att bekräfta",
                        key="app_confirm_delete_input",
                        placeholder=f"Skriv {del_user_sel}..."
                    )
                    
                    if st.button("🗑️ Ta bort", type="secondary", use_container_width=True, key="app_delete_btn"):
                        if confirm_del == del_user_sel:
                            ok, msg = delete_user(del_user_sel)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
                        else:
                            st.error("Du måste skriva användarnamnet exakt för att bekräfta.")
    
    # ======================
    # TAB 3: Export / Secrets
    # ======================
    with tab_export:
        st.markdown("")
        st.subheader("Exportera konfiguration")
        
        users = load_users()
        
        if not users:
            st.info("Inga användare att exportera. Skapa en användare först!")
        else:
            st.markdown("`secrets.toml` **uppdateras automatiskt** när du lägger till eller ändrar användare. Nedan kan du se aktuell konfiguration.")
            
            st.markdown("")
            st.markdown("##### 📋 Aktuell `[users]`-sektion för `secrets.toml`")
            
            snippet = generate_secrets_toml_snippet(users)
            st.code(snippet, language="toml")
            
            st.info("💡 **Tips för Streamlit Cloud:** Kopiera ovanstående och klistra in under *App settings → Secrets* i din Streamlit Cloud-app.")
            
            st.markdown("")
            st.markdown("##### 📄 Fullständig användardata (JSON)")
            
            users_json = json.dumps(users, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Ladda ner users.json",
                data=users_json,
                file_name="users_backup.json",
                mime="application/json",
                use_container_width=True,
                key="app_download_users_json"
            )
            
            st.markdown("")
            st.markdown("##### 🔍 Verifiera lösenord")
            
            col_verify_user, col_verify_pw = st.columns(2)
            with col_verify_user:
                verify_user = st.selectbox(
                    "Användare",
                    options=list(users.keys()),
                    key="app_verify_user_select"
                )
            with col_verify_pw:
                verify_pw = st.text_input(
                    "Lösenord att testa",
                    type="password",
                    key="app_verify_pw_input",
                    placeholder="Skriv lösenordet..."
                )
            
            if st.button("🔍 Verifiera", use_container_width=True, key="app_verify_btn"):
                if verify_pw and verify_user in users:
                    if verify_password_bcrypt(verify_pw, users[verify_user]["password_hash"]):
                        st.success("✅ Lösenordet är korrekt!")
                    else:
                        st.error("❌ Fel lösenord.")
                else:
                    st.error("Ange ett lösenord att testa.")


# ==========================================
# 8. NAVIGATION & MENY
# ==========================================
def main():
    LOGO_PATH = BASE_DIR / "assets" / "gps-logo.svg"

    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), use_container_width=True)
        else:
            st.header("Chatboten Solveig")
        
        st.divider()
        
        # Visa inloggad användare och roll
        current_username = st.session_state.get("username", "")
        if current_username:
            user_role = get_user_role(current_username)
            role_icon = "🔧" if user_role == "admin" else "👤"
            st.caption(f"{role_icon} Inloggad som: **{current_username}**")
        
        if st.button("🔎  Sök & Analys", type="primary" if st.session_state.current_page == "Sök & Analys" else "secondary"):
            st.session_state.current_page = "Sök & Analys"
            st.rerun()
            
        if st.button("📝  Skapa Ansökan", type="primary" if st.session_state.current_page == "Skapa Ansökan" else "secondary"):
            st.session_state.current_page = "Skapa Ansökan"
            st.rerun()
        
        # Admin-knapp – syns bara för admin-användare
        if current_username and is_admin_cloud(current_username):
            if st.button("🔧  Admin", type="primary" if st.session_state.current_page == "Admin" else "secondary"):
                st.session_state.current_page = "Admin"
                st.rerun()
        
        st.divider()
        
        if st.button("🚪 Logga ut", type="secondary"):
            logout()

    if st.session_state.current_page == "Sök & Analys":
        show_chat_page()
    elif st.session_state.current_page == "Skapa Ansökan":
        show_application_page()
    elif st.session_state.current_page == "Admin" and current_username and is_admin_cloud(current_username):
        show_admin_page()
    else:
        show_chat_page()

if __name__ == "__main__":
    main()