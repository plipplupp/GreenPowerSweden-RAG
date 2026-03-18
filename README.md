---
title: Solveig
emoji: ☀️
colorFrom: blue
colorTo: green
sdk: streamlit
app_file: app.py
pinned: false
---

# ☀️ Solveig (tidigare Solaris) - AI-assistent för Solcellsparker

> **Din intelligenta AI-assistent för tillståndsprocesser och ansökningar inom solcellsparksutveckling**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://huggingface.co/spaces/greenpowersweden/solveig)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()

---

## 📋 Innehållsförteckning

- [Om Projektet](#-om-projektet)
- [Funktioner](#-funktioner)
- [Arkitektur](#-arkitektur)
- [Installation](#-installation)
  - [Lokal Installation](#lokal-installation)
  - [Deployment till Hugging Face](#deployment-till-hugging-face)
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

**Solveig** är en avancerad RAG-baserad (Retrieval-Augmented Generation) AI-chatbot utvecklad för att effektivisera arbetet med tillståndsansökningar och research inom solcellsparksutveckling. Systemet analyserar historiska dokument och genererar högkvalitativa utkast baserat på tidigare godkända ansökningar.

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
- **Interaktiv källvisning** - Visa PDF:er direkt på angiven sida (vi Hugging Face Datasets i molnet)
- **Negativsökning** - Transparenta svar när information saknas

### 📝 Skapa Ansökan
- **Projektparametrar** - Ange namn, kommun, storlek, marktyp och naturvärden
- **Tvåstegsprocess**:
  1. **Lokalisering & Markval** - Motiverar platsval och intrång på jordbruksmark
  2. **Miljöpåverkan & Skyddsåtgärder** - Analyserar konsekvenser och åtgärder
- **Automatisk källförteckning** - Referenser till alla använda dokument
- **Export till Markdown** - Ladda ner utkastet för vidare bearbetning

---

## 🏗️ Arkitektur

```
┌─────────────────────────────────────────────────────────────────┐
│                         SOLVEIG SYSTEM                          │
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
│  2. EMBEDDING (BAAI/bge-m3)                                     │
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
│  │   (ChromaDB)     │  │ (HF Dataset)     │  │  (embedded)  │   │
│  │     ~2GB         │  │     ~18GB        │  │              │   │
│  └──────────────────┘  └──────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

### Lokal Installation (via uv)

1. **Klona och synka:**
```bash
git clone https://github.com/plipplupp/GreenPowerSweden-RAG.git
cd GreenPowerSweden-RAG
uv sync
```

2. **Miljövariabler:**
Fyll i `.env` med `GOOGLE_API_KEY` och `ADMIN_PIN`.

3. **Kör appen:**
```bash
uv run streamlit run app.py
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
├── .github/workflows/
│   └── huggingface-sync.yml      # Automatisk synk till HF
│
├── assets/                      # Bilder och logotyper
├── data/
│   └── 01_raw/                  # Lokala PDFer (EJ i Git)
├── src/                         # Källkod (utils, pipeline etc.)
├── app.py                       # Huvudapplikation
├── admin.py                     # Adminverktyg för användare
└── README.md                    # Denna fil (Hugging Face Config + Info)
```

---

## 🛠️ Teknisk Stack

- **Frontend:** Streamlit 1.29+
- **RAG-ramverk:** LangChain
- **Vektordatabas:** ChromaDB
- **LLM:** Google Gemini 2.0 Flash
- **Embeddings:** BAAI `BAAI/bge-m3`
- **Data Hosting:** Hugging Face Datasets (för PDFer)

---

## 📝 Licens

Detta projekt är **privat och proprietärt**. Ingen del av denna kod får användas, kopieras eller distribueras utan explicit tillstånd från ägaren.

---

<div align="center">

**Byggd med ❤️ för hållbar energiutveckling**

⚡ *Powering the green transition, one solar park at a time* ☀️

</div>
