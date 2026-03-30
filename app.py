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
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align:center'>🔐 Logga in till Solveig</h1>", unsafe_allow_html=True)
    st.markdown("<h3 style='text-align:center; color:#555;'>Din AI-assistent för tillståndsprocesser och solcellsparker</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("---")
        with st.form(key="login_form", clear_on_submit=False):
            username = st.text_input("Användarnamn")
            password = st.text_input("Lösenord", type="password")
            submitted = st.form_submit_button("Logga in", type="primary", width="stretch")
            
        if submitted:
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
    """Logga ut användaren och rensa all historik"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
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

if "users_synced" not in st.session_state:
    print("[Solveig] Startar synkning av användare...")
    try:
        from src.utils.user_management import sync_users_from_hf
        ok, msg = sync_users_from_hf()
        if not ok:
            print(f"[Solveig] Fel vid synkning: {msg}")
            st.error(f"Molnsynkning misslyckades vid uppstart: {msg}")
        else:
            print("[Solveig] Användarsynkning klar.")
    except Exception as e:
        print(f"[Solveig] Undantag vid synkning: {e}")
        st.error(f"Ett oväntat fel skedde vid synkning: {e}")
    st.session_state.users_synced = True

# Kontrollera autentisering FÖRST
print("[Solveig] Kontrollerar autentisering...")
if not check_authentication():
    print("[Solveig] Inte inloggad. Visar login-sidan.")
    login_page()
    st.stop()
print(f"[Solveig] Inloggad som: {st.session_state.get('username')}")

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
    .block-container {
        padding-top: 1.5rem !important;
    }
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
    
    /* Blå primärfärg istället för röd (gäller även formulär-knappar) */
    div.stButton > button[kind="primary"],
    div[data-testid="stFormSubmitButton"] button[kind="primary"] {
        background-color: #2196F3 !important;
        border-color: #2196F3 !important;
        color: white !important;
        transition: all 0.2s ease;
    }
    div.stButton > button[kind="primary"]:hover,
    div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
        background-color: #1976D2 !important;
        border-color: #1976D2 !important;
        color: white !important;
        box-shadow: 0 4px 12px rgba(33, 150, 243, 0.3);
    }
    
    /* Multiline-stöd för knappar (t.ex. ikon på första raden, text på andra) */
    div[data-testid="stButton"] button p,
    div[data-testid="stPopover"] button p {
        white-space: pre-line !important;
        line-height: 1.4 !important;
        text-align: center !important;
        min-width: 65px !important;
    }

    /* Totalt förbud mot expansionsknappen och verktygsfältet på bilder (Streamlit 1.35+) */
    [data-testid="stElementToolbar"],
    [data-testid="stElementToolbarButtonContainer"],
    [data-testid="stElementToolbarButton"],
    button[aria-label="Fullscreen"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    div.row-widget.stButton > button[kind="secondary"]:hover {
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
    """Hämta API-nyckel eller lista av nycklar från secrets eller environment"""
    try:
        if hasattr(st, 'secrets') and 'GOOGLE_API_KEY' in st.secrets:
            keys = st.secrets['GOOGLE_API_KEY']
            if isinstance(keys, str) and "," in keys:
                return [k.strip() for k in keys.split(",")]
            elif isinstance(keys, list):
                return keys
            return [keys]
    except:
        pass
    
    env_keys = os.environ.get('GOOGLE_API_KEY')
    if env_keys:
        if "," in env_keys:
            return [k.strip() for k in env_keys.split(",")]
        return [env_keys]
    return []

# Hämta Hugging Face Token
def get_hf_token():
    """Hämta Hugging Face API-nyckel från secrets eller environment"""
    try:
        if hasattr(st, 'secrets'): 
            if 'HF_TOKEN' in st.secrets:
                return st.secrets['HF_TOKEN']
            if 'HF_WRITE_TOKEN' in st.secrets:
                return st.secrets['HF_WRITE_TOKEN']
    except:
        pass
    return os.environ.get('HF_TOKEN') or os.environ.get('HF_WRITE_TOKEN')

@st.cache_resource(show_spinner=False)
def load_resources():
    """Ladda embeddings och initiera vektordatabasen (LLM skapas nu dynamiskt för att tillåta rotation)"""
    print("[Solveig] load_resources() startar...")

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
   
    try:
        vectordb = Chroma(
            persist_directory=str(DB_DIR),
            embedding_function=embedding_model
        )
    except Exception as e:
        return None
   
    return vectordb

def get_llm(key_index=0):
    """Skapar en LLM-instans med en specifik nyckel eller den nuvarande från session_state"""
    api_keys = get_api_key()
    if not api_keys:
        return None
    
    # Säkerställ att vi inte går utanför listan
    idx = key_index % len(api_keys)
    selected_key = api_keys[idx]
    
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview", 
        temperature=0.3,
        google_api_key=selected_key,
        max_retries=1,
        timeout=60,
    )

# Förbered DB om den inte existerar
if not DB_DIR.exists():
    if IS_CLOUD:
        st.markdown("<br>", unsafe_allow_html=True)
        with st.spinner("📥 Laddar ner och packar upp vektordatabasen... (Detta sker bara vid nystart, tar ca 1 min)"):
            success, error_msg = download_and_extract_vectordb()
            if not success:
                st.error(f"❌ Misslyckades att ladda ner databasen från Hugging Face: {error_msg}")
                st.info("Tips: Kontrollera att ditt HF_TOKEN i Secrets har läsrättigheter till datasetet 'greenpowersweden/solveig-db'.")
            else:
                st.toast("✅ Databas laddad!")
    else:
        st.error(f"⚠️ Kunde inte hitta vektordatabasen på: {DB_DIR}")

vectordb = load_resources()

if "api_key_index" not in st.session_state:
    import random
    api_keys = get_api_key()
    # Starta på ett slumpmässigt ställe för att sprida lasten (viktigt om vi har många sessioner)
    st.session_state.api_key_index = random.randint(0, max(0, len(api_keys) - 1)) if api_keys else 0

if vectordb is None:
    st.error("Fel vid laddning av vektordatabas. Starta om tjänsten.")

# LLM hämtas nu vid behov via get_llm()

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
            
            # Normalisera sökvägen (ersätt \ med / om det råkar finnas kvar från Windows-data)
            # Vi tar bort 'pdfs/' prefixet om det råkar finnas i metadata
            clean_path = str(relative_path).replace("\\", "/")
            if clean_path.startswith("pdfs/"):
                clean_path = clean_path[5:]
            
            # Försök ladda ner med den fullständiga relativa sökvägen (bevarar mappar som 'domar/')
            cached_path = hf_hub_download(
                repo_id=repo_id, 
                repo_type="dataset", 
                filename=clean_path, 
                token=token
            )
            return Path(cached_path)
        except Exception as e:
            st.error(f"❌ Fel vid hämtning av '{relative_path}': {e}")
            return None
    else:
        # Lokalt: Använd den befintliga sökvägen
        return RAW_DATA_DIR / relative_path

def is_domar_path(path_str):
    """Kontrollera om dokumentet är i den begränsade mappen 'domar' (GDPR)."""
    if not path_str:
        return False
    # Normalisera separatorer och kolla om 'domar' finns med
    normalized = str(path_str).replace("\\", "/").lower()
    return "/domar/" in normalized or normalized.startswith("domar/")

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
            with st.container(border=True):
                pdf_viewer(str(doc_path), height=800, width="100%")
    else:
        # I normalt läge är kolumnen redan smal (40%), så använd hela bredden
        with st.container(border=True):
            pdf_viewer(str(doc_path), height=800, width="100%")

# ==========================================
# 4. RAG FUNKTIONER
# ==========================================

def format_docs_with_sources(docs):
    """Formaterar hämtade dokument för LLM-prompt."""
    formatted_texts = []
    for i, doc in enumerate(docs):
        path = doc.metadata.get("full_path", "Okänd fil")
        page = doc.metadata.get("page", "?")
        content = doc.page_content
        formatted_texts.append(f"DOKUMENT ID [{i+1}]:\nSökväg: {path} (Sida {page})\nINNEHÅLL: {content}\n----------------")
    return "\n\n".join(formatted_texts)

def get_rag_response(question, system_prompt, k=10):
    """Hämtar relevanta dokument och frågar LLM."""
    if not vectordb:
        return "⚠️ Vektordatabasen är inte laddad.", []
    
    api_keys = get_api_key()
    if not api_keys:
        return "⚠️ Google API-nyckel saknas. Konfigurera GOOGLE_API_KEY i secrets eller .env", []

    retriever = vectordb.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)
    context_text = format_docs_with_sources(docs)
   
    prompt_template = f"""
    {system_prompt}
   
    VIKTIGA INSTRUKTIONER FÖR ANALYS:
    1. Granska den tillhandahållna kontexten noggrant.
    2. Om kontexten INTE innehåller **relevant** information som kan besvara FRÅGAN, svara då: "Jag har granskat de tillhandahållna dokumenten och kan konstatera att det inte finns tillräcklig information om [ämnet i frågan] i dessa."
    3. Svara ALDRIG på en fråga om kontexten är tom eller irrelevant.

    VIKTIGA INSTRUKTIONER FÖR INTEGRITET:
    1. Skriv ALDRIG ut namn på privatpersoner, även om de förekommer i dokumenten.
    2. Om ett namn är relevant för sammanhanget, beskriv personens roll istället (t.ex. "sökanden", "fastighetsägaren", "käranden").

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
    
    # Proaktiv rotation: Växla till nästa nyckel inför varje anrop för att sprida lasten
    if len(api_keys) > 1:
        st.session_state.api_key_index = (st.session_state.api_key_index + 1) % len(api_keys)
    
    # Försök anropa LLM – rotera nycklar vid fel, max en gång per nyckel
    num_keys = len(api_keys)
    
    for attempt in range(num_keys):
        current_key_idx = (st.session_state.api_key_index + attempt) % num_keys
        print(f"[Solveig] LLM-anrop försök {attempt + 1}/{num_keys}, nyckelindex={current_key_idx}")
        try:
            llm = get_llm(current_key_idx)
            chain = prompt | llm | StrOutputParser()
            answer = chain.invoke({"context": context_text, "question": question})
            # Spara index för nästa anrop (proaktiv rotation)
            st.session_state.api_key_index = (current_key_idx + 1) % num_keys
            return answer, docs
        except Exception as e:
            error_str = str(e)
            print(f"[Solveig] Fel vid anrop (försök {attempt + 1}): {error_str[:200]}")
            
            # Tillfälliga fel (rate limit, serversidan hos Google, timeout) -> rotera nyckel och försök igen
            is_rate_limit = "429" in error_str or "ResourceExhausted" in error_str
            is_server_error = any(code in error_str for code in ["500", "503", "Timeout", "ServiceUnavailable", "InternalServerError"])
            
            if is_rate_limit or is_server_error:
                if attempt < num_keys - 1:
                    # Visa en diskret toast-notis om rotationen om vi har fler nycklar att prova
                    if num_keys > 1:
                        reason = "Rate limit nådd" if is_rate_limit else "Googles server svarar inte"
                        st.toast(f"🔄 {reason} – provar reservnyckel ({attempt + 2}/{num_keys})...", icon="⚠️")
                time.sleep(1)
                continue
            else:
                # Oväntat fel (t.ex. ogiltig nyckel) – returnera direkt utan att prova fler nycklar
                return f"⚠️ Oväntat fel vid AI-anrop: {error_str[:300]}", docs
    
    # Alla nycklar är slut / alla försök misslyckades
    print("[Solveig] Alla försök misslyckades. Returnerar servicemeddelande.")
    st.toast("❌ Kvoten för Google API är uppnådd.", icon="🔧")
    return (
        "🔧 **Rate limit uppnådd för Google Gemini**\n\n"
        "AI-tjänsten svarar att kvoten är slut. Det här kan bero på:\n"
        "- **Projekt-gräns:** Om API-nycklar ligger i samma Google-projekt delar de på samma RPM (15/min).\n"
        "- **Global belastning:** Ibland begränsar Google anropen tillfälligt.\n\n"
        "**Lösning:** Vänta en minut och försök igen."
    ), docs

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
    focus_label = "💬 Lämna fokusvy (visa chatt)" if st.session_state.focus_mode else "🔍 Fokusvy (maximera dokument)"
    if st.button(focus_label, type="primary", width="stretch"):
        st.session_state.focus_mode = not st.session_state.focus_mode
        st.rerun()
    
    st.divider()
    
    if st.session_state.selected_pdf:
        doc_path = st.session_state.selected_pdf
        page = st.session_state.selected_page
        
        if st.button("⬅️ Tillbaka till listan", type="primary"):
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
                filename = Path(path_str).name if path_str else "okänd.pdf"
                
                # Kontrollera GDPR-begränsning (domar-mappen) – admin ser allt
                is_admin = is_admin_cloud(st.session_state.get("username", ""))
                restricted = is_domar_path(path_str) and not is_admin

                # Bestäm sökväg (lokal eller relativ för molnet)
                if IS_CLOUD:
                    local_ref_path = path_str
                else:
                    local_ref_path = RAW_DATA_DIR / path_str
                
                with st.container():
                    # Visa om dokumentet är begränsat
                    if restricted:
                        label_extra = " 🔒"
                    else:
                        label_extra = ""
                    st.markdown(f"""
                    <div class="source-card">
                        <b>[Källa {citation_id}] {filename}{label_extra}</b><br>
                        <span style="color:#555; font-size:0.9em;">Sida {page_num}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Dynamisk layout för knappar beroende på vy
                    if st.session_state.focus_mode:
                        # I fokusvy: Samla knappar till vänster
                        c_open, c_text, c_dl, c_path, c_spacer = st.columns([1, 1, 1, 1, 4])
                    else:
                        # I sidopanel: Kompakt layout för 4 knappar (Sökväg sist för att undvika hål)
                        c_open, c_text, c_dl, c_path = st.columns([1, 1, 1, 1])
                    
                    with c_open:
                        if restricted:
                            with st.popover("🚫\nVisa"):
                                st.warning(
                                    "🔒 **GDPR-begränsning**\n\n"
                                    "Det här dokumentet innehåller information som är skyddad enligt GDPR. "
                                    "Vi arbetar med att gå igenom och maskera dessa filer för att "
                                    "ersätta dem med en maskad version inom kort."
                                )
                        else:
                            if st.button(f"📄\nVisa", key=f"open_{i}"):
                                if IS_CLOUD:
                                    with st.spinner("📥 Hämtar dokument..."):
                                        actual_path = get_pdf_path(path_str)
                                        if actual_path:
                                            st.session_state.selected_pdf = actual_path
                                            st.session_state.selected_page = page_num
                                            st.rerun()
                                        else:
                                            st.error("Kunde inte hämta dokumentet från molnet.")
                                else:
                                    st.session_state.selected_pdf = local_ref_path
                                    st.session_state.selected_page = page_num
                                    st.rerun()
                    
                    with c_text:
                        with st.popover("📖\nAvsnitt"):
                            st.caption(doc.page_content)

                    with c_dl:
                        if restricted:
                            # Visa grå knapp som förklaring om att nedladdning inte är tillgänglig
                            with st.popover("🚫\nHämta"):
                                st.warning(
                                    "🔒 **GDPR-begränsning**\n\n"
                                    "Nedladdning av detta dokument är tillfälligt begränsad av GDPR-skäl. "
                                    "Vi arbetar med att gå igenom och maskera dessa filer för att "
                                    "ersätta dem med en maskad version inom kort."
                                )
                        else:
                            # Hämta bytes vid klick (cachas av hf_hub_download)
                            dl_key = f"dl_bytes_{i}"
                            if st.button("⬇️\nHämta", key=f"dl_btn_{i}"):
                                with st.spinner("Förbereder..."):
                                    pdf_path = get_pdf_path(path_str) if IS_CLOUD else (RAW_DATA_DIR / path_str)
                                    if pdf_path and Path(pdf_path).exists():
                                        try:
                                            with open(pdf_path, "rb") as f:
                                                st.session_state[dl_key] = f.read()
                                        except Exception as e:
                                            st.error(f"Kunde inte läsa filen: {e}")
                                    else:
                                        st.error("Kunde inte hitta källfilen.")
                                
                            if dl_key in st.session_state:
                                st.download_button(
                                    label="📥\nSpara PDF",
                                    data=st.session_state[dl_key],
                                    file_name=filename,
                                    mime="application/pdf",
                                )

                    with c_path:
                        if is_admin_cloud(st.session_state.get("username", "")):
                            with st.popover("📂\nSökväg"):
                                st.code(path_str, language="text")

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
                
                # Liten paus för att inte slå i rate limit
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
                    width="stretch"
                )
                if st.button("🗑️ Rensa Genererat Utkast", width="stretch", type="secondary"):
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
        
        # Trigger för att nollställa formulär
        if "admin_form_trigger" not in st.session_state:
            st.session_state.admin_form_trigger = 0
            
        col_form, col_preview = st.columns([3, 2], gap="large")
        
        with col_form:
            new_username = st.text_input(
                "Användarnamn",
                placeholder="t.ex. anna.svensson",
                help="Användarnamnet kan innehålla bokstäver, siffror, punkt och understreck.",
                key=f"admin_new_username_{st.session_state.admin_form_trigger}"
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
                    label_visibility="collapsed",
                    key=f"admin_new_password_{st.session_state.admin_form_trigger}"
                )
            with col_pw_gen:
                if st.button("☀️ Generera", width="stretch", key="gen_pw_btn"):
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
                key=f"admin_confirm_password_{st.session_state.admin_form_trigger}"
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
        
        if st.button("✅ Skapa användare", type="primary", width="stretch", key="admin_create_btn"):
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
                    # Nollställ formulär genom att ändra nyckeln
                    st.session_state.admin_form_trigger += 1
                    st.session_state.generated_passwords = []
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
                
                if st.button("🔄 Uppdatera lösenord", type="primary", width="stretch", key="app_reset_btn"):
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
                
                # Extra utrymme så att statusmeddelanden syns bättre
                st.markdown("<br><br>", unsafe_allow_html=True)
            
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
                    
                    if st.button("🗑️ Ta bort", type="primary", width="stretch", key="app_delete_btn"):
                        if confirm_del == del_user_sel:
                            ok, msg = delete_user(del_user_sel)
                            if ok:
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                st.error(f"❌ {msg}")
                        else:
                            st.error("Du måste skriva användarnamnet exakt för att bekräfta.")
    
    with tab_export:
        st.markdown("")
        st.subheader("Synkronisering & Backup")
        
        users = load_users()
        
        if not users:
            st.info("Inga användare att visa ännu. Skapa en användare först!")
        else:
            st.success("☁️ **Automatisk molnsynkning:** Alla ändringar du gör i användare synkroniseras nu automatiskt till en säker databas på Hugging Face.")
            
            st.markdown("")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("##### 💾 Spara ner lokal backup")
                users_json = json.dumps(users, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Ladda ner users.json",
                    data=users_json,
                    file_name="users_backup.json",
                    mime="application/json",
                    use_container_width=True,
                    key="app_download_users_json"
                )
            with col_b2:
                st.markdown("##### 🚀 Manuellt tvinga synkronisering")
                if st.button("Ladda upp till molnet", width="stretch"):
                    with st.spinner("Laddar upp..."):
                        from src.utils.user_management import sync_users_to_hf
                        ok, msg = sync_users_to_hf()
                        if ok:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")
            
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
            
            if st.button("🔍 Verifiera", width="stretch", key="app_verify_btn"):
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
            st.image(str(LOGO_PATH), width="stretch")
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
        
        # Utloggnings-knapp längst ner
        st.markdown("---")
        if st.button("🔒 Logga ut", type="secondary"):
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