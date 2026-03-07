# ☀️ Solaris - AI-assistent för Solcellsparker

> **Din intelligenta AI-assistent för tillståndsprocesser och ansökningar inom solcellsparksutveckling**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app-url.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()

---

## 📋 Innehållsförteckning

- [Om Projektet](#-om-projektet)
- [Funktioner](#-funktioner)
- [Arkitektur](#-arkitektur)
- [Installation](#-installation)
  - [Lokal Installation](#lokal-installation)
  - [Deployment till Streamlit Cloud](#deployment-till-streamlit-cloud)
- [Användning](#-användning)
- [Konfiguration](#-konfiguration)
- [Projektstruktur](#-projektstruktur)
- [Teknisk Stack](#-teknisk-stack)
- [Säkerhet](#-säkerhet)
- [Felsökning](#-felsökning)
- [Utveckling](#-utveckling)
- [Kontakt](#-kontakt)

---

## 🌟 Om Projektet

**Solaris** är en avancerad RAG-baserad (Retrieval-Augmented Generation) AI-chatbot utvecklad för att effektivisera arbetet med tillståndsansökningar och research inom solcellsparksutveckling. Systemet analyserar historiska dokument och genererar högkvalitativa utkast baserat på tidigare godkända ansökningar.

### Huvudmål
- 🔍 **Intelligent dokumentsökning** - Hitta relevant information snabbt från stora dokumentsamlingar
- 📝 **Automatisk ansökningsgenerering** - Skapa utkast till samrådsanmälan baserat på projektspecifika parametrar
- 🎯 **Källhantering** - Transparent spårbarhet med exakta hänvisningar till originaldokument
- 🔒 **Säker åtkomst** - Skyddad med autentisering för företagsanvändning

### Användningsområden
- Analys av miljökonsekvensbeskrivningar (MKB)
- Research kring lokalisering och markval
- Undersökning av lagkrav och riktlinjer
- Generering av samrådsanmälan och tillståndsansökningar
- Benchmarking mot tidigare projekt

---

## ✨ Funktioner

### 🔎 Sök & Analys
- **Semantisk sökning** med HuggingFace embeddings
- **RAG-pipeline** som kombinerar vektordatabas med LLM (Gemini 2.5)
- **Top-K retrieval** - Hämtar de 10 mest relevanta dokumenten
- **Källcitation** - Varje påstående backas upp med **[Källa: X]** och sidnummer
- **Interaktiv källvisning** - Visa PDF:er direkt på angiven sida (lokalt)
- **Negativsökning** - Transparenta svar när information saknas

### 📝 Skapa Ansökan
- **Projektparametrar** - Ange namn, kommun, storlek, marktyp och naturvärden
- **Tvåstegsprocess**:
  1. **Lokalisering & Markval** - Motiverar platsval och intrång på jordbruksmark
  2. **Miljöpåverkan & Skyddsåtgärder** - Analyserar konsekvenser och åtgärder
- **Automatisk källförteckning** - Referenser till alla använda dokument
- **Export till Markdown** - Ladda ner utkastet för vidare bearbetning

### 🔐 Säkerhet
- **SHA-256 hashning** av lösenord
- **Session-baserad autentisering** med Streamlit
- **Secrets management** - API-nycklar lagras säkert
- **Miljödetektering** - Automatisk konfiguration för lokal/moln-miljö

### 💬 Användarvänlighet
- **Chattgränssnitt** inspirerat av ChatGPT
- **Dual-column layout** - Chatt till vänster, källor till höger
- **Responsiv design** med professionell styling
- **Historik** - Bevara konversation inom session
- **Popover-funktionalitet** - Snabb insyn i dokument och metadata

---

## 🏗️ Arkitektur

```
┌─────────────────────────────────────────────────────────────────┐
│                         SOLARIS SYSTEM                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ANVÄNDARGRÄNSSNITT                         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐     │
│  │  Inloggning  │→ │ Sök & Analys │  │  Skapa Ansökan     │     │
│  └──────────────┘  └──────────────┘  └────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RAG-PIPELINE                            │
│                                                                 │
│  1. QUERY PROCESSING                                            │
│     ↓                                                           │
│  2. EMBEDDING (HuggingFace all-mpnet-base-v2)                   │
│     ↓                                                           │
│  3. VECTOR SEARCH (ChromaDB)                                    │
│     ↓                                                           │
│  4. RETRIEVAL (Top-K documents)                                 │
│     ↓                                                           │
│  5. CONTEXT ENRICHMENT                                          │
│     ↓                                                           │
│  6. LLM GENERATION (Google Gemini 2.0 Flash)                    │
│     ↓                                                           │
│  7. RESPONSE + SOURCES                                          │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                               │
│                                                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │  Vector Database │  │   Raw PDFs       │  │   Metadata   │   │
│  │   (ChromaDB)     │  │  (01_raw/)       │  │  (embedded)  │   │
│  │     ~2GB         │  │     ~16GB        │  │              │   │
│  └──────────────────┘  └──────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Dataflöde

1. **Användaren ställer en fråga** → "Hur motiverar man byggnation på jordbruksmark?"
2. **Frågan embeddingas** → Konverteras till 768-dimensionell vektor
3. **Vektorsökning** → ChromaDB hittar de 10 mest semantiskt liknande dokumenten
4. **Kontextbyggnad** → Dokument formateras med metadata (fil, sida)
5. **LLM-prompting** → Gemini får kontext + instruktioner + fråga
6. **Svarsgenerering** → LLM skapar strukturerat svar med källhänvisningar
7. **Källvisning** → Användaren kan klicka på källor och läsa originaldokument

---

## 🚀 Installation

### Förutsättningar

- Python 3.10 eller högre
- Git
- Google API-nyckel (för Gemini)
- Google Drive-konto (för vektordatabas i molnet)

### Lokal Installation

#### 1. Klona repository
```bash
git clone https://github.com/ditt-username/solaris-app.git
cd solaris-app
```

#### 2. Skapa virtuell miljö
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

#### 3. Installera dependencies
```bash
pip install -r requirements.txt
```

#### 4. Konfigurera miljövariabler
Skapa `.env` i projektets rot:
```bash
GOOGLE_API_KEY=din_google_api_nyckel_här
```

#### 5. Konfigurera secrets
Skapa `.streamlit/secrets.toml`:
```toml
GOOGLE_API_KEY = "din_google_api_nyckel_här"

[users]
admin = "8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918"
företag = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
```

**Generera egna lösenord:**
```bash
python -c "import hashlib; print(hashlib.sha256('ditt_lösenord'.encode()).hexdigest())"
```

#### 6. Förbered data (lokalt)
Placera din vektordatabas i:
```
data/03_vector_db/green_power_sweden_db/
```

Placera PDFs i:
```
data/01_raw/
```

#### 7. Kör appen
```bash
streamlit run 06_solaris_app.py
```

Appen öppnas på `http://localhost:8501`

---

### Deployment till Streamlit Cloud

#### Steg 1: Förbered vektordatabas

1. **Zippa din vektordatabas:**
```bash
cd data/03_vector_db
# Högerklicka → Komprimera (Windows) eller:
zip -r green_power_sweden_db.zip green_power_sweden_db/
```

2. **Ladda upp till Google Drive:**
   - Ladda upp ZIP-filen
   - Högerklicka → Dela → "Vem som helst med länken"
   - Kopiera länken, t.ex.:
     ```
     https://drive.google.com/file/d/1ABC123XYZ456/view?usp=sharing
     ```

3. **Extrahera fil-ID:**
   ```
   Fil-ID = 1ABC123XYZ456
   ```

4. **Uppdatera `download_vectordb.py`:**
   ```python
   file_id = "1ABC123XYZ456"  # Ditt faktiska ID här
   ```

#### Steg 2: Pusha till GitHub

```bash
# Initiera Git (om inte redan gjort)
git init
git add .
git commit -m "Initial commit: Solaris app"

# Skapa repository på GitHub (Private!)
# Sedan:
git remote add origin https://github.com/ditt-username/solaris-app.git
git branch -M main
git push -u origin main
```

#### Steg 3: Deploy på Streamlit Cloud

1. Gå till [share.streamlit.io](https://share.streamlit.io)
2. Logga in med GitHub
3. Klicka "New app"
4. Välj:
   - **Repository:** `ditt-username/solaris-app`
   - **Branch:** `main`
   - **Main file:** `06_solaris_app.py`
   - **App URL:** `greenpower-solaris` (eller valfritt)

5. **Konfigurera Secrets** (före deployment):
   - Klicka "Advanced settings"
   - Gå till "Secrets"
   - Kopiera innehållet från din `.streamlit/secrets.toml`
   - Klistra in

6. Klicka **"Deploy"**

#### Steg 4: Vänta och testa

- **Första deployment:** ~5-10 minuter (inkl. nedladdning av vektordatabas)
- **URL:** `https://greenpower-solaris.streamlit.app`
- **Logga in** med dina användaruppgifter

---

## 📖 Användning

### Inloggning
1. Öppna appen
2. Ange användarnamn och lösenord
3. Klicka "Logga in"

### Sök & Analys

#### Ställ en fråga
```
Ex: "Vilka skyddsåtgärder krävs vid dikespassage?"
Ex: "Hur motiverar man byggnation på jordbruksmark?"
Ex: "Vad säger lagen om ekologiska kompensationsåtgärder?"
```

#### Interagera med källor
- **[Källa: X]** i chatten → Motsvarar dokument X i källistan
- **"📄 Visa källa"** → Öppnar PDF på citerad sida (lokalt)
- **"📂 Visa sökväg"** → Visar dokumentets fullständiga sökväg
- **"📝 Läs avsnitt"** → Visar den exakta texten som citerats

#### Tips för bästa resultat
- Var specifik i dina frågor
- Använd facktermer (MKB, Natura 2000, kompensationsåtgärder)
- Ställ följdfrågor för att fördjupa
- Kontrollera alltid källor innan du använder information

### Skapa Ansökan

#### 1. Fyll i projektinformation
- **Projektnamn:** T.ex. "Solpark Ekbacken"
- **Kommun & Län:** T.ex. "Kalmar kommun, Kalmar län"
- **Storlek/Effekt:** T.ex. "45 hektar, ca 30 MW"
- **Marktyp:** Beskriv markens karaktär och nuvarande användning
- **Naturvärden:** Ange skyddade områden, artförekomster, vattendrag etc.

#### 2. Generera utkast
- Klicka "✨ Generera Utkast"
- Vänta medan systemet:
  1. Analyserar markval och lokalisering
  2. Tar fram miljöpåverkan och skyddsåtgärder

#### 3. Granska och ladda ner
- **Läs igenom** det genererade utkastet
- **Kontrollera källor** i referenslistorna
- **Ladda ner** som Markdown-fil
- **Redigera** i valfri texteditor (Word, Notion, etc.)

#### 4. Tips
- Ju mer detaljerad input, desto bättre resultat
- Använd facktermer för bäst matchning mot historiska dokument
- Genererade utkast är **startpunkter** - granska alltid juridiskt

---

## ⚙️ Konfiguration

### Environment Variables (.env)
```bash
GOOGLE_API_KEY=din_nyckel_här
```

### Streamlit Secrets (.streamlit/secrets.toml)
```toml
GOOGLE_API_KEY = "din_nyckel_här"

[users]
användare1 = "hashad_lösenord"
användare2 = "hashad_lösenord"
```

### RAG-parametrar (i koden)
```python
# Antal dokument att hämta
k = 10  

# LLM-temperatur (kreativitet)
temperature = 0.3

# Embedding-modell
model_name = "sentence-transformers/all-mpnet-base-v2"

# LLM-modell
model = "gemini-2.0-flash-exp"
```

---

## 📁 Projektstruktur

```
green_power_sweden/
│
├── .streamlit/
│   ├── config.toml              # Streamlit-konfiguration
│   └── secrets.toml             # API-nycklar & användare (EJ i Git)
│
├── assets/
│   └── gps-logo.svg             # Logotyp för sidebar
│
├── data/
│   ├── 01_raw/                  # Rådata & PDFs (16GB, EJ i Git)
│   ├── 02_processed/            # Bearbetade CSV:er (I Git)
│   │   └── pdf_analysis_report.csv
│   └── 03_vector_db/            # Lokal vektordatabas (2GB, EJ i Git)
│       └── green_power_sweden_db/
│
├── notebooks/                   # Jupyter notebooks för analys
│   ├── 01_data_prep.ipynb
│   ├── 02_pdf_ocr_analysis.ipynb
│   ├── 03_text_extraction.ipynb
│   ├── 04_chunking_and_embedding.ipynb
│   └── 05_rag_application.ipynb
│
├── .env                         # Environment variables (EJ i Git)
├── .gitignore                   # Git-ignoring
├── download_vectordb.py         # Laddar ner databas från Google Drive
├── requirements.txt             # Python dependencies
├── 06_solaris_app.py           # Huvudapplikation
└── README.md                    # Denna fil
```

---

## 🛠️ Teknisk Stack

### Frontend
- **Streamlit** 1.29+ - Snabb prototyping och UI
- **streamlit-pdf-viewer** - PDF-rendering i browsern

### Backend & AI
- **LangChain** - RAG orchestration
- **LangChain-Chroma** - Vector store integration
- **LangChain-HuggingFace** - Embedding provider
- **LangChain-Google-GenAI** - LLM provider

### Data & Storage
- **ChromaDB** - Vector database
- **Sentence-Transformers** - Embedding model (all-mpnet-base-v2)
- **Google Drive** - Cloud storage för vektordatabas
- **gdown** - Nedladdning från Google Drive

### LLM & Embeddings
- **Google Gemini 2.0 Flash** - Text generation
- **HuggingFace all-mpnet-base-v2** - Sentence embeddings (768 dim)

### Utilities
- **pandas** - Data processing
- **python-dotenv** - Environment management
- **hashlib** - Password hashing

---

## 🔒 Säkerhet

### Lösenordshantering
- **SHA-256 hashing** - Inga lösenord i klartext
- **Salting** - Inte implementerat (använd bcrypt för produktion)
- **Session-baserad auth** - Ingen JWT/OAuth

### API-nycklar
- **Aldrig** i kod
- **Secrets management** via Streamlit Secrets
- **Environment variables** för lokal utveckling

### Data Privacy
- **Privat GitHub-repo** - Kod ej publik
- **No-logging** - Konversationer sparas ej
- **Session-isolering** - Användare ser inte varandras data

### Rekommendationer för produktion
För **känslig data** eller **många användare**, uppgradera till:
- [ ] **bcrypt** med salt för lösenord
- [ ] **OAuth 2.0** för autentisering
- [ ] **HTTPS** för all kommunikation (Streamlit Cloud har detta)
- [ ] **Rate limiting** för att förhindra abuse
- [ ] **Audit logging** för att spåra användning

---

## 🐛 Felsökning

### Vanliga problem

#### "Database not found"
**Symptom:** Appen kan inte hitta vektordatabasen

**Lösningar:**
```bash
# Lokalt: Kontrollera sökvägen
ls data/03_vector_db/green_power_sweden_db/

# Molnet: Verifiera Google Drive-länk
python download_vectordb.py  # Testa standalone
```

#### "API key missing"
**Symptom:** Felmeddelande om saknad API-nyckel

**Lösningar:**
```bash
# Lokalt: Kontrollera .env
cat .env  # Ska innehålla GOOGLE_API_KEY

# Molnet: Kontrollera secrets
# Streamlit Cloud → Settings → Secrets → Verifiera GOOGLE_API_KEY
```

#### "Authentication failed"
**Symptom:** Kan inte logga in trots korrekt lösenord

**Lösningar:**
```python
# Generera nytt hash
import hashlib
print(hashlib.sha256('ditt_lösenord'.encode()).hexdigest())

# Uppdatera i secrets.toml
```

#### "Out of memory" (Streamlit Cloud)
**Symptom:** Appen kraschar i molnet

**Lösningar:**
```python
# Minska RAG retrieval i 06_solaris_app.py
k = 5  # Istället för 10

# Optimera embedding-modell
model_name = "sentence-transformers/all-MiniLM-L6-v2"  # Mindre modell
```

#### "PDF viewer not working"
**Symptom:** PDFs visas ej i molnversionen

**Förklaring:** Detta är förväntat beteende - PDFs (16GB) kan inte laddas upp till Streamlit Cloud. Appen visar istället informativa meddelanden med dokumentnamn och sida.

**Alternativ:**
- Ladda upp viktiga PDFs separat till Google Drive
- Lägg till direktlänkar i källkortet
- Användare klickar vidare till Google Drive

---

## 🧑‍💻 Utveckling

### Lokal utvecklingsmiljö

```bash
# Aktivera virtuell miljö
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

# Installera i editable mode
pip install -e .

# Kör i development mode
streamlit run 06_solaris_app.py --server.runOnSave true
```

### Lägga till nya funktioner

#### 1. Ny sidebar-sida
```python
# I main() funktionen
if st.button("🆕 Ny Sida"):
    st.session_state.current_page = "Ny Sida"
    st.rerun()

# Skapa funktion
def show_new_page():
    st.title("Ny Sida")
    # Din kod här
```

#### 2. Ny RAG-funktion
```python
def custom_rag_query(question, system_prompt, k=10):
    # Anpassa retrieval
    # Anpassa prompting
    # Return response, docs
    pass
```

#### 3. Uppdatera embedding-modell
```python
embedding_model = HuggingFaceEmbeddings(
    model_name="intfloat/multilingual-e5-large",  # Exempel
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)
```

### Testa ändringar

```bash
# Lokalt
streamlit run 06_solaris_app.py

# Pusha till GitHub för auto-deploy (om aktiverat)
git add .
git commit -m "Beskrivning av ändring"
git push origin main
```

---

## 📊 Prestanda

### Lokal körning
- **Initial laddning:** ~10-20 sekunder (ladda modeller)
- **Första sökning:** ~3-5 sekunder
- **Efterföljande sökningar:** ~1-2 sekunder (cachad modell)
- **Ansökningsgenerering:** ~30-60 sekunder (två RAG-anrop)

### Molnkörning (Streamlit Cloud)
- **Initial deployment:** ~5-10 minuter (första gången)
- **Första laddning per session:** ~2-3 minuter (ladda ner databas)
- **Efterföljande:** ~10-20 sekunder
- **Sökning:** ~2-4 sekunder
- **Ansökningsgenerering:** ~40-80 sekunder

### Optimeringsmöjligheter
- [ ] Cache embeddings i session state
- [ ] Lazy-load PDF viewer
- [ ] Streaming LLM responses
- [ ] Parallel RAG-queries i ansökningsgenerering
- [ ] Upgrade till större Streamlit Cloud tier (mer RAM/CPU)

---

## 📝 Licens

Detta projekt är **privat och proprietärt**. Ingen del av denna kod får användas, kopieras eller distribueras utan explicit tillstånd från ägaren.

---

## 🙏 Erkännanden

### Teknologier
- **Streamlit** - För fantastiskt UI-ramverk
- **LangChain** - För RAG-infrastruktur
- **Google Gemini** - För kraftfull LLM
- **HuggingFace** - För embeddings och modeller
- **ChromaDB** - För vector search

---

<div align="center">

**Byggd med ❤️ för hållbar energiutveckling**

⚡ *Powering the green transition, one solar park at a time* ☀️

</div>