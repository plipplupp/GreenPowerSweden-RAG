import streamlit as st
import os
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

# Logga i sidopanelen
LOGO_PATH = BASE_DIR / "assets" / "gps-logo.svg"

with st.sidebar:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True) # Visar loggan
    else:
        st.header("Solaris Insight") # Fallback-titel om loggan inte hittas

# CSS
st.markdown("""
<style>
    .source-card {
        padding: 10px;
        background-color: #f0f2f6;
        border-radius: 5px;
        margin-bottom: 10px;
        border-left: 5px solid #ff4b4b;
    }
    .stTextArea textarea {
        font-size: 16px !important;
    }
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
    for doc in docs:
        path = doc.metadata.get("full_path", "Okänd fil")
        page = doc.metadata.get("page", "?")
        content = doc.page_content
        formatted_texts.append(f"KÄLLA: {path} (Sida {page})\nTEXT: {content}")
    return "\n\n".join(formatted_texts)

def get_rag_response(question, system_prompt, k=6):
    """Generell funktion för att hämta svar baserat på DB."""
    retriever = vectordb.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(question)
    context_text = format_docs_with_sources(docs)
    
    prompt = ChatPromptTemplate.from_template(f"""
    {system_prompt}
    
    ANVÄND FÖLJANDE KONTEXT FRÅN DATABASEN:
    {{context}}
    
    UPPGIFT/FRÅGA:
    {{question}}
    """)
    
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"context": context_text, "question": question})
    return answer, docs

# ==========================================
# 4. SIDA: CHATT (Research)
# ==========================================
def show_chat_page():
    st.title("🔎 Sök & Analys")
    st.info("Här kan du söka fritt i databasen för att hitta prejudikat och information.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "current_sources" not in st.session_state:
        st.session_state.current_sources = []
    if "selected_pdf" not in st.session_state:
        st.session_state.selected_pdf = None
    if "selected_page" not in st.session_state:
        st.session_state.selected_page = 1

    col_chat, col_ref = st.columns([1, 1]) 

    # --- VÄNSTER: CHATT ---
    with col_chat:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Ex: Hur har man resonerat kring riksintresse för kulturmiljö?"):
            st.chat_message("user").markdown(prompt)
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("assistant"):
                with st.spinner("Söker i domar och underlag..."):
                    sys_prompt = "Du är Solaris Legal. Svara på frågan baserat på kontexten. Hänvisa till källor."
                    response, docs = get_rag_response(prompt, sys_prompt, k=10)
                    st.markdown(response)
            
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.current_sources = docs
            st.session_state.selected_pdf = None
            st.rerun()

    # --- HÖGER: DOKUMENT ---
    with col_ref:
        st.subheader("Källor")
        if st.session_state.selected_pdf:
            if st.button("⬅️ Tillbaka till listan"):
                st.session_state.selected_pdf = None
                st.rerun()
            
            f_path = st.session_state.selected_pdf
            pg = st.session_state.selected_page
            st.markdown(f"**{f_path.name}** (Sida {pg})")
            
            if f_path.exists():
                pdf_viewer(str(f_path), height=800, width="100%")
            else:
                st.error(f"Fil saknas: {f_path}")

        elif st.session_state.current_sources:
            for i, doc in enumerate(st.session_state.current_sources):
                path_str = doc.metadata.get("full_path")
                page_num = doc.metadata.get("page")
                full_os_path = RAW_DATA_DIR / path_str
                
                with st.container():
                    st.markdown(f"""<div class="source-card"><b>{i+1}. {Path(path_str).name}</b><br>Sida {page_num}</div>""", unsafe_allow_html=True)
                    if st.button(f"Öppna PDF #{i+1}", key=f"btn_{i}"):
                        st.session_state.selected_pdf = full_os_path
                        st.session_state.selected_page = page_num
                        st.rerun()
                    with st.expander("Text"):
                        st.text(doc.page_content[:300] + "...")
        else:
            st.write("Inga källor att visa än.")

# ==========================================
# 5. SIDA: SKAPA ANSÖKAN (Generator)
# ==========================================
def show_application_page():
    st.title("📝 Skapa Ansökan")
    st.markdown("""
    Här genererar vi utkast till en **Samrådsanmälan (enl. 12 kap. 6 § MB)**. 
    AI:n använder din input och söker i databasen efter *framgångsrika formuleringar* från tidigare ärenden.
    """)

    with st.form("application_input"):
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("Projektnamn", "Solpark Ekbacken")
            kommun = st.text_input("Kommun & Län", "Kalmar kommun, Kalmar län")
            size = st.text_input("Storlek/Effekt", "45 hektar, ca 30 MW")
        with col2:
            marktyp = st.text_area("Beskriv marktypen", 
                                   "Lågproduktiv jordbruksmark som delvis är igenväxt. Ligger nära skogskant. Inga kända fornlämningar.",
                                   height=100,
                                   help="Beskriv marken så detaljerat du kan. Är det åker? Bete? Skog?")
            
            naturvarden = st.text_area("Naturvärden & Skydd", 
                                       "Området ligger inte inom Natura 2000. Finns diken i söder.",
                                       height=100)

        submitted = st.form_submit_button("Generera Ansökningsutkast")

    if submitted:
        st.divider()
        st.subheader(f"Utkast: {project_name}")
        
        # --- SEKTION 1: LOKALISERING (Jordbruksmark) ---
        with st.status("Skriver sektion: Lokalisering...", expanded=True):
            st.write("Söker argument för markval...")
            
            # Här gör vi en RAG-sökning specifikt för att hitta argument
            query_loc = f"Argument för att bygga solceller på {marktyp} i {kommun}. Hur motiverar man intrång på jordbruksmark?"
            sys_prompt_loc = """
            Du ska skriva avsnittet "Lokalisering och Markval" till en ansökan.
            Använd användarens projektdata.
            Viktigast: Hitta argument i databasen för varför denna typ av mark är lämplig och hur andra har fått godkänt (t.ex. att det är lågproduktiv mark).
            Skriv formellt och övertygande.
            """
            
            text_loc, docs_loc = get_rag_response(query_loc, sys_prompt_loc)
            st.markdown("### 1. Lokalisering och val av plats")
            st.write(text_loc)
            
            with st.expander("Källor som användes för detta stycke"):
                for doc in docs_loc[:3]:
                    st.caption(f"{doc.metadata.get('full_path')} (Sid {doc.metadata.get('page')})")

        # --- SEKTION 2: PÅVERKAN & SKYDDSÅTGÄRDER ---
        with st.status("Skriver sektion: Miljöpåverkan...", expanded=True):
            st.write("Letar efter standardåtgärder...")
            
            query_env = f"Vilka skyddsåtgärder krävs för naturvärden vid solcellsparker? Specifikt kring: {naturvarden}."
            sys_prompt_env = """
            Du ska skriva avsnittet "Miljöpåverkan och Skyddsåtgärder".
            Lista konkreta åtgärder baserat på vad som brukar krävas i domar (t.ex. skyddsavstånd, stängselhöjd för vilt).
            """
            
            text_env, docs_env = get_rag_response(query_env, sys_prompt_env)
            st.markdown("### 2. Miljöpåverkan och Skyddsåtgärder")
            st.write(text_env)

# ==========================================
# 6. HUVUDNAVIGATION
# ==========================================
def main():
    # Meny i sidopanelen
    st.sidebar.title("Meny")
    page = st.sidebar.radio("Gå till:", ["Sök & Analys", "Skapa Ansökan"])
    
    st.sidebar.divider()
    
    if page == "Sök & Analys":
        show_chat_page()
    elif page == "Skapa Ansökan":
        show_application_page()

if __name__ == "__main__":
    main()