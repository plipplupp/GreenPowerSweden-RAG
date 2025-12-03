import streamlit as st
import os
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

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

# Sökvägar
BASE_DIR = Path(r"C:\Users\Dator\Documents\Data_Science\11_Examensarbete\green_power_sweden")
DB_DIR = BASE_DIR / "data" / "03_vector_db" / "green_power_sweden_db" 
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

# --- CSS STYLING (Professionell & Stabil) ---
st.markdown("""
<style>
    /* --- SIDEBAR KNAPPAR (Neutrala & Blåa) --- */
    /* Standardknapp i sidebar */
    section[data-testid="stSidebar"] button {
        width: 200px !important; /* Fyller bredden */
        background-color: #f8f9fa;
        color: #444;
        border: 1px solid #ddd;
        text-align: left;
        padding-left: 15px;
        transition: all 0.25s ease;
    }
    
    /* Hover i sidebar (Ljusblå) */
    section[data-testid="stSidebar"] button:hover {
        background-color: #e3f2fd;
        border-color: #2196F3;
        color: #0b5394;
    }

    /* Aktiv knapp i sidebar (Sätts via type="primary" i Python men stylas här) */
    section[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #e3f2fd;
        border-color: #2196F3;
        color: #0b5394;
        font-weight: 600;
        border-left: 5px solid #2196F3; /* Markör till vänster */
    }

    /* --- KÄLLKORT (Höger spalt) --- */
    .source-card {
        padding: 15px;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        margin-bottom: 12px;
        border-left: 5px solid #2196F3; /* Blå accent */
        /* Ingen hover-effekt på själva kortet */
    }

    /* --- KNAPPAR I HÖGER SPALT & GENERATE --- */
    div.stButton > button {
        border-radius: 6px;
        font-weight: 500;
    }
    /* Hover effekt på vanliga knappar (t.ex. Öppna PDF) */
    div.row-widget.stButton > button:hover {
        border-color: #2196F3;
        color: #2196F3;
        background-color: #f0f7ff;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* --- NEDLADDNINGSKNAPP (Grön/Success Färg) --- */
    /* Använder stDownloadButton test-ID för att isolera stilen */
    div[data-testid="stDownloadButton"] > button {
        background-color: #4CAF50 !important; /* Standard Success Green */
        border-color: #4CAF50 !important;
        color: white !important;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    div[data-testid="stDownloadButton"] > button:hover {
        background-color: #45a049 !important; /* Slightly darker green on hover */
        border-color: #45a049 !important;
        color: white !important;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
    }


    /* --- TEXTAREAS --- */
    .stTextArea textarea {
        font-size: 16px !important;
    }
    
    /* --- RUBRIKER --- */
    h1 { font-size: 2.0rem; font-weight: 700; color: #2c3e50; margin-bottom: 0px; }
    h3 { font-size: 1.2rem; font-weight: 600; color: #555; margin-top: 0px; }

</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LADDNING AV RESURSER
# ==========================================
@st.cache_resource
def load_resources():
    embedding_model = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2",
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': False}
    )
    
    if not DB_DIR.exists():
        st.error(f"Kunde inte hitta databasen på: {DB_DIR}")
        return None, None
        
    vectordb = Chroma(
        persist_directory=str(DB_DIR),
        embedding_function=embedding_model
    )
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.3
    )
    
    return vectordb, llm

vectordb, llm = load_resources()

# ==========================================
# 3. RAG FUNKTIONER
# ==========================================

def format_docs_with_sources(docs):
    formatted_texts = []
    # Vi numrerar dokumenten [1], [2], [3] här
    for i, doc in enumerate(docs):
        # ANVÄNDER FULL_PATH för bättre spårbarhet
        path = doc.metadata.get("full_path", "Okänd fil")
        page = doc.metadata.get("page", "?")
        content = doc.page_content
        # Lägger till ett ID [X] som LLM kan referera till
        formatted_texts.append(f"DOKUMENT ID [{i+1}]:\nSökväg: {path} (Sida {page})\nINNEHÅLL: {content}\n----------------")
    return "\n\n".join(formatted_texts)

def get_rag_response(question, system_prompt, k=6):
    retriever = vectordb.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)
    context_text = format_docs_with_sources(docs)
    
    prompt = ChatPromptTemplate.from_template(f"""
    {system_prompt}
    
    VIKTIGA INSTRUKTIONER FÖR KÄLLOR:
    1. Du har tillgång till numrerade dokument, t.ex. "DOKUMENT ID [1]".
    2. När du använder information från ett dokument, lägg till en hänvisning i fetstil direkt efter meningen.
    3. Formatet SKA vara: **[Källa: X]** (där X är dokumentets ID-nummer).
    4. Skriv INTE ut filnamnet i löptexten, använd bara numret.
    
    ANVÄND FÖLJANDE KONTEXT:
    {{context}}
    
    FRÅGA:
    {{question}}
    """)
    
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context_text, "question": question})
    return answer, docs

# ==========================================
# 4. SIDA: CHATT (Research)
# ==========================================
def show_chat_page():
    
    # Rubrik och Underrubrik (Clean design)
    st.markdown("# 👋 Välkommen till Solaris Insight")
    st.markdown("### Din AI-assistent för tillståndsprocesser och solcellsparker.")
    st.divider()

    # Huvudlayout: Chatt (Vänster) | Källor (Höger)
    col_chat, col_ref = st.columns([1, 1], gap="large") 

    # --- VÄNSTER: CHATT ---
    with col_chat:
        st.header("💬 Chatt")
        
        # Container för chatthistorik (Stabiliserar layouten)
        chat_container = st.container()
        
        with chat_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

        # Inputfältet (Ligger alltid längst ner)
        if prompt := st.chat_input("Ex: Hur motiverar man byggnation på jordbruksmark?"):
            # Visa användarens fråga direkt
            with chat_container:
                st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Generera svar
            with chat_container:
                with st.chat_message("assistant"):
                    with st.spinner("Söker och analyserar..."):
                        sys_prompt = "Du är Solaris Legal. Svara professionellt på svenska."
                        response, docs = get_rag_response(prompt, sys_prompt, k=10)
                        st.markdown(response)
            
            # Spara state
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.current_sources = docs
            st.session_state.selected_pdf = None 
            st.rerun()
            
        # Rensa-knapp (Längst ner under inputen)
        st.write("") # Lite luft
        if st.session_state.messages:
            if st.button("🗑️ Rensa historik", type="secondary", use_container_width=True):
                st.session_state.messages = []
                st.session_state.current_sources = []
                st.session_state.selected_pdf = None
                st.rerun()

    # --- HÖGER: DOKUMENT ---
    with col_ref:
        st.header("📄 Källor & Dokument")
        
        # Scenario A: Visa PDF
        if st.session_state.selected_pdf:
            doc_path = st.session_state.selected_pdf
            page = st.session_state.selected_page
            
            if st.button("⬅️ Tillbaka till listan"):
                st.session_state.selected_pdf = None
                st.session_state.selected_page = 1
                st.rerun()
            
            st.markdown(f"**Visar:** `{doc_path.name}` (Sida {page})")
            
            if doc_path.exists():
                # Streamlit PDF Viewer tar en sträng för filepath
                pdf_viewer(str(doc_path), pages_to_stream=[page], height=800, width="100%")
            else:
                st.error(f"Fil saknas: {doc_path}")

        # Scenario B: Visa Lista
        elif st.session_state.current_sources:
            st.write(f"Hittade {len(st.session_state.current_sources)} relevanta avsnitt.")
            
            for i, doc in enumerate(st.session_state.current_sources):
                path_str = doc.metadata.get("full_path")
                page_num = doc.metadata.get("page")
                full_os_path = RAW_DATA_DIR / path_str
                
                # Källkortet (Bara info, ej klickbart)
                with st.container():
                    st.markdown(f"""
                    <div class="source-card">
                        <b>[{i+1}] {Path(path_str).name}</b><br>
                        <span style="color:#555; font-size:0.9em;">Sida {page_num}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Knappar för interaktion
                    c_open, c_path, c_text = st.columns([1, 1, 1])
                    
                    with c_open:
                        if st.button(f"📄 Öppna PDF", key=f"open_{i}"):
                            st.session_state.selected_pdf = full_os_path
                            st.session_state.selected_page = page_num
                            st.rerun()
                    
                    with c_path:
                        # Visa sökväg i en popover (ny funktion!)
                        with st.popover("📂 Visa sökväg"):
                            st.code(path_str, language="text")
                            
                    with c_text:
                        with st.popover("📝 Läs text"):
                            st.caption(doc.page_content)
        else:
            st.info("Källor visas här när du ställer en fråga.")

# ==========================================
# 5. SIDA: SKAPA ANSÖKAN (Generator)
# ==========================================
def show_application_page():
    st.title("📝 Skapa Ansökan")
    # Ändrad rubriknivå till ### enligt önskemål
    st.markdown("### Generera utkast till en **Samrådsanmälan** baserat på tidigare data.")

    default_inputs = st.session_state.get("application_inputs", {})

    with st.form("application_input"):
        st.subheader("Projektinformation")
        
        # Använder st.container för att gruppera inmatningsfälten snyggt
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

        # START: Ändrad logik för att centrera och göra knapparna lika stora som nedladdningsknappen (3/5 bredd)
        
        # Omsluter knapparna i kolumner för att begränsa bredden
        col_left, col_center, col_right = st.columns([1, 3, 1])
        
        with col_center:
            # Generera Utkast - Primär knapp
            submitted = st.form_submit_button("✨ Generera Utkast", type="primary", use_container_width=True)
            # Rensa Input - Sekundär knapp, ligger under och har samma bredd
            clear_form = st.form_submit_button("🔄 Rensa Input", type="secondary", use_container_width=True)

        # SLUT: Ändrad logik
            

    # Logik för rensa input-knappen
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
            # Lägger till inputs i queryn för att göra den mer specifik
            query_loc = f"Argument för att bygga solceller på {marktyp} i {kommun}. Hur motiverar man intrång på jordbruksmark för ett projekt på {size}?"
            sys_prompt = "Du ska skriva avsnittet 'Lokalisering' och vara saklig. Använd fetstil för källhänvisning [Källa: X]."
            text_loc, docs_loc = get_rag_response(query_loc, sys_prompt)
            st.write("Klar.")
            
            # ANVÄNDER NY RUBRIK OCH FULLSTÄNDIGA SÖKVÄGAR
            full_draft_text += f"\n## 1. LOKALISERING & MARKVAL\n{text_loc}\n\n**Referenser för Lokalisering och markval:**\n"
            # Iterera över de dokument som användes för att generera DEL 1
            for i, d in enumerate(docs_loc): 
                # Använder full_path här
                full_draft_text += f"- [{i+1}] {d.metadata.get('full_path')} (Sid {d.metadata.get('page')})\n"
        
        # --- DEL 2 ---
        with st.status("🌱 Del 2/2: Tar fram skyddsåtgärder...", expanded=True):
            query_env = f"Vilka skyddsåtgärder krävs för {naturvarden} vid anläggning av en solcellspark? Beskriv även miljöpåverkan."
            sys_prompt = "Du ska skriva avsnittet 'Miljöpåverkan och skyddsåtgärder'. Använd fetstil för källhänvisning [Källa: X]."
            text_env, docs_env = get_rag_response(query_env, sys_prompt)
            st.write("Klar.")

            full_draft_text += f"\n## 2. MILJÖPÅVERKAN OCH SKYDDSÅTGÄRDER\n{text_env}\n\n**Referenser för Miljöpåverkan:**\n"
            # Iterera över de dokument som användes för att generera DEL 2
            for i, d in enumerate(docs_env): 
                # Använder full_path här för konsekvens
                full_draft_text += f"- [{i+1}] {d.metadata.get('full_path')} (Sid {d.metadata.get('page')})\n"

        st.session_state.application_draft = full_draft_text
        st.success("Utkastet är färdigt!")

    # Visa utkast och nedladdningsknapp
    if st.session_state.application_draft:
        st.markdown(st.session_state.application_draft)
        st.divider()
        
        safe_name = st.session_state.application_inputs.get("project_name", "Utkast").replace(" ", "_").replace(":", "").replace("/", "")
        
        # Centrera nedladdningsknappen och rensa-utkast knappen
        col_dl_left, col_dl_center, col_dl_right = st.columns([1, 3, 1])
        
        with col_dl_center:
            # KNAPPEN FÅR NU GRÖN FÄRG VIA CSS SELECTORN data-testid="stDownloadButton"
            st.download_button(
                label="💾 Ladda ner Ansökan (.md)",
                data=st.session_state.application_draft,
                file_name=f"Ansokan_{safe_name}.md",
                mime="text/markdown",
                # Behåller type="primary" för Streamlits interna struktur, men stilen är överkörd av CSS.
                type="primary", 
                use_container_width=True
            )
            # Rensa utkast-knappen (för att rensa det genererade utkastet)
            if st.button("🗑️ Rensa Genererat Utkast", use_container_width=True, type="secondary"):
                st.session_state.application_draft = ""
                st.rerun()


# ==========================================
# 6. NAVIGATION & MENY
# ==========================================
def main():
    # Hårdkodar en path som kanske inte finns i alla miljöer, men behåller som den var.
    LOGO_PATH = BASE_DIR / "assets" / "gps-logo.svg" 
    with st.sidebar:
        if LOGO_PATH.exists():
            # Kontrollerar om filen är en SVG (vanlig bildtyp för Streamlit)
            if LOGO_PATH.suffix.lower() == '.svg':
                # Streamlit kan visa SVG direkt, men om det är en vanlig fil path fungerar st.image.
                try:
                    st.image(str(LOGO_PATH), use_container_width=True)
                except:
                    # Fallback om SVG-rendering misslyckas
                    st.header("Solaris Insight")
            else:
                st.image(str(LOGO_PATH), use_container_width=True)
        else:
            st.header("Solaris Insight")
        
        st.divider()
        
        # NAVIGERING - Vi sätter typen baserat på state för att få färgmarkering
        if st.button("🔎  Sök & Analys", type="primary" if st.session_state.current_page == "Sök & Analys" else "secondary"):
            st.session_state.current_page = "Sök & Analys"
            st.rerun()
            
        if st.button("📝  Skapa Ansökan", type="primary" if st.session_state.current_page == "Skapa Ansökan" else "secondary"):
            st.session_state.current_page = "Skapa Ansökan"
            st.rerun()

    if st.session_state.current_page == "Sök & Analys":
        show_chat_page()
    elif st.session_state.current_page == "Skapa Ansökan":
        show_application_page()

if __name__ == "__main__":
    main()