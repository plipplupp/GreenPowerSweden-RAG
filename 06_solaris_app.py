import streamlit as st
import os
import pandas as pd
import re
import yaml
import gdown
import zipfile
import shutil
from pathlib import Path
from dotenv import load_dotenv
from yaml.loader import SafeLoader

# Försök importera authenticator, hantera om det saknas
try:
    import streamlit_authenticator as stauth
    AUTH_ENABLED = True
except ImportError:
    AUTH_ENABLED = False

# LangChain & Chroma
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# PDF Viewer
from streamlit_pdf_viewer import pdf_viewer

# ==========================================
# 1. KONFIGURATION OCH SETUP
# ==========================================
st.set_page_config(
    page_title="Solaris Insight",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

load_dotenv()

# --- MILJÖDETEKTERING (ROBUST) ---
# Vi sätter IS_CLOUD till False som standard
IS_CLOUD = False

try:
    # Vi kollar om attributet 'secrets' ens existerar på st-objektet
    # och försöker sedan läsa från det.
    if hasattr(st, "secrets"):
        # OBS: Att bara anropa st.secrets kan krascha om filen saknas lokalt.
        # Vi måste fånga felet som uppstår.
        if "IS_CLOUD" in st.secrets and st.secrets["IS_CLOUD"] == True:
            IS_CLOUD = True
except Exception:
    # Om något går fel (t.ex. FileNotFoundError för secrets.toml), kör vi lokalt.
    IS_CLOUD = False

# Definiera bas-sökvägar baserat på miljö
if IS_CLOUD:
    BASE_DIR = Path(".") 
    # I molnet sparar vi den nedladdade databasen i en lokal mapp 'vector_db'
    DB_DIR = BASE_DIR / "vector_db"
    # PDF:er i molnet (Använd en liten demo-mapp om du har, annars saknas de)
    RAW_DATA_DIR = BASE_DIR / "demo_pdfs" 
else:
    # Lokala sökvägar (Din dator)
    BASE_DIR = Path(r"C:\Users\Dator\Documents\Data_Science\11_Examensarbete\green_power_sweden")
    
    # Försök hitta den lokala original-databasen först
    LOCAL_ORIGINAL_DB = BASE_DIR / "data" / "03_vector_db" / "green_power_sweden_db"
    if LOCAL_ORIGINAL_DB.exists():
        DB_DIR = LOCAL_ORIGINAL_DB
    else:
        # Om du flyttat koden eller kör på en annan lokal maskin
        DB_DIR = Path("vector_db")
        
    RAW_DATA_DIR = BASE_DIR / "data" / "01_raw"


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

# --- CSS STYLING ---
st.markdown("""
<style>
    /* Sidebar Knappar */
    section[data-testid="stSidebar"] button {
        width: 100% !important;
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
    /* Källkort */
    .source-card {
        padding: 15px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 5px solid #2196F3;
    }
    /* Knappar (Generell) */
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
    /* Nedladdningsknapp (Grön) */
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
    /* Övrigt */
    .stTextArea textarea { font-size: 16px !important; }
    h1 { font-size: 2.0rem; font-weight: 700; color: #2c3e50; margin-bottom: 0px; }
    h3 { font-size: 1.2rem; font-weight: 600; color: #555; margin-top: 0px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LADDNING AV RESURSER & DATABAS
# ==========================================

def download_vectordb():
    """Laddar ner DB från Google Drive om den saknas."""
    FILE_ID = "1EbU2XJ1TyzlHTW_989hRg3IpS2-eDQ3v" # Ditt fil-ID
    OUTPUT_ZIP = "vector_db.zip"
    TARGET_DIR = Path("vector_db")

    # Om mappen redan finns och verkar innehålla data, hoppa över
    if TARGET_DIR.exists() and any(TARGET_DIR.iterdir()):
        return True

    with st.status("📥 Initierar moln-miljö (Laddar ner databas)...", expanded=True) as status:
        try:
            st.write("Laddar ner från Google Drive (ca 1-2 min)...")
            url = f'https://drive.google.com/uc?id={FILE_ID}'
            # gdown laddar ner filen
            output = gdown.download(url, OUTPUT_ZIP, quiet=False)
            
            if not output:
                 st.error("Nedladdning misslyckades.")
                 return False

            st.write("Packar upp databas...")
            with zipfile.ZipFile(OUTPUT_ZIP, 'r') as zip_ref:
                zip_ref.extractall(".")
            
            # Städning
            if os.path.exists(OUTPUT_ZIP):
                os.remove(OUTPUT_ZIP)
            
            status.update(label="Klar! Databas laddad.", state="complete", expanded=False)
            return True
        except Exception as e:
            st.error(f"Kunde inte ladda ner databasen: {e}")
            return False

@st.cache_resource
def load_resources():
    # 1. Embedding Modell
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )
    
    # 2. Databas (Vektorer)
    # Om vi är i molnet och DB saknas, ladda ner den
    current_db_path = DB_DIR
    
    if IS_CLOUD or not DB_DIR.exists():
        # Om vi är i molnet eller inte hittar lokal DB, försök ladda ner/använda 'vector_db'
        if not DB_DIR.exists() and not Path("vector_db").exists():
             if not download_vectordb():
                 return None, None
             current_db_path = Path("vector_db")
        elif Path("vector_db").exists():
             current_db_path = Path("vector_db")

    try:
        vectordb = Chroma(
            persist_directory=str(current_db_path),
            embedding_function=embedding_model
        )
    except Exception as e:
        st.error(f"Fel vid initiering av ChromaDB på sökväg {current_db_path}: {e}")
        return None, None

    # 3. API Nyckel (Gemini)
    api_key = None
    # Försök hämta från Secrets (Cloud)
    try:
        if hasattr(st, "secrets"):
            api_key = st.secrets.get("GEMINI_API_KEY")
    except Exception:
        pass
    
    # Fallback till Environment (Lokal)
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        st.error("Ingen API-nyckel hittades. Konfigurera GEMINI_API_KEY i .env (lokalt) eller Secrets (moln).")
        return None, None

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3,
        api_key=api_key
    )
    
    return vectordb, llm

vectordb, llm = load_resources()

# ==========================================
# 3. RAG FUNKTIONER
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
        return "⚠️ Systemet är inte redo (Databas eller API-nyckel saknas).", []

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
# 4. SIDA: CHATT (Research)
# ==========================================
def show_chat_page():
    
    st.markdown("# 👋 Välkommen till Solaris Insight")
    st.markdown("### Din AI-assistent för tillståndsprocesser och solcellsparker.")
    st.divider()

    col_chat, col_ref = st.columns([1, 1], gap="large") 

    # --- VÄNSTER: CHATT ---
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
                        sys_prompt = "Du är Solaris Legal. Svara professionellt på svenska och använd sakliga termer."
                        response, docs = get_rag_response(prompt, sys_prompt, k=10)
                        st.markdown(response)

            # State-uppdatering
            NEGATIVE_PHRASE = "Jag har granskat"
            if response.strip().startswith(NEGATIVE_PHRASE):
                final_sources = []
            else:
                final_sources = docs 
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.current_sources = final_sources
            st.session_state.selected_pdf = None
            st.rerun()
            
        st.write("") 
        # Ändrad: use_container_width=True -> width='stretch'
        if st.session_state.messages:
            if st.button("🗑️ Rensa historik", type="secondary", width='stretch'):
                st.session_state.messages = []
                st.session_state.current_sources = []
                st.session_state.selected_pdf = None
                st.rerun()

    # --- HÖGER: DOKUMENT ---
    with col_ref:
        st.header("📄 Källor & Dokument")
        
        if st.session_state.selected_pdf:
            doc_path = st.session_state.selected_pdf
            page = st.session_state.selected_page
            
            if st.button("⬅️ Tillbaka till listan"):
                st.session_state.selected_pdf = None
                st.session_state.selected_page = 1
                st.rerun()
            
            st.markdown(f"**Visar:** `{doc_path.name if isinstance(doc_path, Path) else Path(doc_path).name}` (Sida {page})")
            
            # --- PDF VISNING ---
            if doc_path.exists():
                # Bredd sätts via argumentet width i pdf_viewer, inte st.button
                pdf_viewer(str(doc_path), height=800, width="100%") 
            else:
                if IS_CLOUD:
                    st.warning("⚠️ **PDF-visning begränsad i molnet**")
                    st.info("För att spara utrymme i demot är inte alla 16GB PDF-filer uppladdade.")
                    st.caption(f"Filen `{doc_path.name}` finns inte på servern.")
                else:
                    st.error(f"Fil saknas lokalt: {doc_path}")

        elif st.session_state.current_sources:
            st.info(f"Listan visar de **{len(st.session_state.current_sources)}** mest relevanta dokumenten. Källhänvisningarna i chatten (t.ex. **[Källa: 7]**) refererar till dokumentets nummer i denna lista.")
            
            sources_container = st.container(border=False)
            
            with sources_container:
                for i, doc in enumerate(st.session_state.current_sources):
                    citation_id = i + 1
                    path_str = doc.metadata.get("full_path")
                    page_num = doc.metadata.get("page")
                    
                    # Hantera sökvägar (olika för moln/lokal)
                    full_os_path = RAW_DATA_DIR / path_str
                    
                    with st.container():
                        st.markdown(f"""
                        <div class="source-card">
                            <b>[Källa {citation_id}] {Path(path_str).name}</b><br>
                            <span style="color:#555; font-size:0.9em;">Sida {page_num}</span>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        c_open, c_path, c_text = st.columns([1, 1, 1])
                        
                        with c_open:
                            if st.button(f"📄 Öppna PDF", key=f"open_{i}"):
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
# 5. SIDA: SKAPA ANSÖKAN (Generator)
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
            
            marktyp = st.text_area("Beskriv marktypen", value=default_inputs.get("marktyp", "Lågproduktiv jordbruksmark..."), height=100)
            naturvarden = st.text_area("Naturvärden & Skydd", value=default_inputs.get("naturvarden", "Området ligger inte inom Natura 2000..."), height=100)

        col_left, col_center, col_right = st.columns([1, 3, 1])
        with col_center:
            # Ändrad: use_container_width=True -> width='stretch'
            submitted = st.form_submit_button("✨ Generera Utkast", type="primary", width='stretch')
            # Ändrad: use_container_width=True -> width='stretch'
            clear_form = st.form_submit_button("🔄 Rensa Input", type="secondary", width='stretch')

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
        
        # --- DEL 1 ---
        with st.status("🔍 Del 1/2: Analyserar markval...", expanded=True):
            query_loc = f"Argument för att bygga solceller på {marktyp} i {kommun}. Hur motiverar man intrång på jordbruksmark för ett projekt på {size}?"
            sys_prompt = "Du ska skriva avsnittet 'Lokalisering' och vara saklig. Använd fetstil för källhänvisning [Källa: X]."
            text_loc, docs_loc = get_rag_response(query_loc, sys_prompt)
            st.write("Klar.")
            
            full_draft_text += f"\n## 1. LOKALISERING & MARKVAL\n{text_loc}\n\n**Referenser:**\n"
            for i, d in enumerate(docs_loc): 
                full_draft_text += f"- [{i+1}] {d.metadata.get('full_path')} (Sid {d.metadata.get('page')})\n"
        
        # --- DEL 2 ---
        with st.status("🌱 Del 2/2: Tar fram skyddsåtgärder...", expanded=True):
            query_env = f"Vilka skyddsåtgärder krävs för {naturvarden} vid anläggning av en solcellspark? Beskriv även miljöpåverkan."
            sys_prompt = "Du ska skriva avsnittet 'Miljöpåverkan och skyddsåtgärder'. Använd fetstil för källhänvisning [Källa: X]."
            text_env, docs_env = get_rag_response(query_env, sys_prompt)
            st.write("Klar.")

            full_draft_text += f"\n## 2. MILJÖPÅVERKAN OCH SKYDDSÅTGÄRDER\n{text_env}\n\n**Referenser:**\n"
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
            # Ändrad: use_container_width=True -> width='stretch'
            st.download_button(
                label="💾 Ladda ner Ansökan (.md)",
                data=st.session_state.application_draft,
                file_name=f"Ansokan_{safe_name}.md",
                mime="text/markdown",
                type="primary",
                width='stretch'
            )
            # Ändrad: use_container_width=True -> width='stretch'
            if st.button("🗑️ Rensa Genererat Utkast", width='stretch', type="secondary"):
                st.session_state.application_draft = ""
                st.rerun()

# ==========================================
# 6. HUVUDLOOP & INLOGGNING
# ==========================================
def main():
    
    # --- LOGGA ---
    LOGO_PATH = BASE_DIR / "assets" / "gps-logo.svg"
    
    # --- AUTH CONFIG ---
    CONFIG_PATH = BASE_DIR / "config.yaml"
    # Fallback om vi kör från roten (vanligt i molnet)
    if not CONFIG_PATH.exists():
        CONFIG_PATH = Path("config.yaml")

    # --- INLOGGNINGSLOGIK ---
    # Kör inloggning om biblioteket finns, config finns, OCH vi kör i molnet (eller vill tvinga lokalt)
    SHOULD_LOGIN = AUTH_ENABLED and CONFIG_PATH.exists() and IS_CLOUD 

    if SHOULD_LOGIN:
        try:
            with open(CONFIG_PATH) as file:
                config = yaml.load(file, Loader=SafeLoader)

            authenticator = stauth.Authenticate(
                config['credentials'],
                config['cookie']['name'],
                config['cookie']['key'],
                config['cookie']['expiry_days'],
            )

            name, authentication_status, username = authenticator.login('main')
            
            if authentication_status is False:
                st.error('Fel användarnamn eller lösenord')
                return
            elif authentication_status is None:
                st.warning('Vänligen logga in')
                return
            
            # --- Inloggad ---
            authenticator.logout('Logga ut', 'sidebar')
            st.sidebar.write(f'Inloggad som: **{name}**')
            
        except Exception as e:
            st.error(f"Inloggningsfel: {e}")
            pass 
    else:
        if not IS_CLOUD:
            st.sidebar.caption("🔧 Dev Mode")

    # --- APPENS UI ---
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width='stretch') # Ändrad: use_container_width=True -> width='stretch'
        else:
            st.header("Solaris Insight")
        
        st.divider()
        
        if st.button("🔎  Sök & Analys", type="primary" if st.session_state.current_page == "Sök & Analys" else "secondary", width='stretch'): # Ändrad: use_container_width=True -> width='stretch'
            st.session_state.current_page = "Sök & Analys"
            st.rerun()
            
        if st.button("📝  Skapa Ansökan", type="primary" if st.session_state.current_page == "Skapa Ansökan" else "secondary", width='stretch'): # Ändrad: use_container_width=True -> width='stretch'
            st.session_state.current_page = "Skapa Ansökan"
            st.rerun()

    if st.session_state.current_page == "Sök & Analys":
        show_chat_page()
    elif st.session_state.current_page == "Skapa Ansökan":
        show_application_page()

if __name__ == "__main__":
    main()