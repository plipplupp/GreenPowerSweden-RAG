# Uppdateringsguide: Green Power Sweden

Denna guide beskriver hur du uppdaterar databasen när ny data kommer in (ca var 6:e månad eller en gång per år).

## Förutsättningar

- Python 3.11+ installerat
- `uv` installerat
- Google Colab-konto (för chunking & embedding)
- Google Drive-åtkomst

---

## Steg 1: Lägg till ny data

Kopiera den nya datamappen till:

```
data/01_raw/
```

Den nya mappen bör läggas *bredvid* de befintliga mapparna. **Ta inte bort** gammal data om den ska finnas kvar i databasen.

## Steg 2: Kör den lokala pipelinen

Kör hela pipelinen med ett kommando:

```bash
uv run python run_pipeline.py
```

**Vad händer:**
1. **Dataförberedelse** – ZIP-filer packas upp, dubbletter tas bort, ej stödda filer flyttas.
2. **PDF-analys** – Nya PDF:er analyseras (text vs. OCR). Redan analyserade filer hoppas över.
3. **Textextrahering** – Text extraheras från alla nya filer och sparas som JSON. Redan extraherade filer hoppas över.
4. **Zippa** – Alla JSON-filer zippas till `data/02_processed/all_json_files.zip`.

> **Tips:** Om du bara vill köra ett enskilt steg, använd `--step N`, t.ex:
> ```bash
> uv run python run_pipeline.py --step 2
> ```

## Steg 3: Ladda upp till Google Drive

Ladda upp filen `data/02_processed/all_json_files.zip` till din Google Drive-mapp:

```
Google Drive / Green_Power_Sweden / all_json_files.zip
```

## Steg 4: Kör chunking & embedding i Colab

1. Öppna `notebooks/04_chunking_and_embedding.ipynb` i Google Colab.
2. Se till att GPU-runtime är aktiverad (valfritt men rekommenderat).
3. Kör igenom alla celler.
4. Vänta tills databasen är byggd (10-30 minuter beroende på datamängd).

## Steg 5: Ladda ner vektordatabasen

1. Vektordatabasen sparas automatiskt som `vector_db.zip` på Google Drive.
2. Ladda ner `vector_db.zip` till din dator.

## Steg 6: Uppdatera lokal vektordatabas

Packa upp `vector_db.zip` i projektets `vector_db/`-mapp:

```bash
# Ta bort gammal databas
rm -rf vector_db/*

# Packa upp den nya
unzip vector_db.zip -d vector_db/
```

## Steg 7: Starta Streamlit-appen

```bash
uv run streamlit run 06_solaris_app.py
```

---

## Sammanfattning av filflödet

```
data/01_raw/          ← Ny data läggs här
        │
        ▼
  [run_pipeline.py]   ← Kör lokalt
        │
        ▼
data/02_processed/
  ├── pdf_analysis_report.csv
  ├── extracted_text/  ← JSON-filer
  └── all_json_files.zip
        │
        ▼
  [Google Colab]       ← Chunking & embedding
        │
        ▼
  vector_db.zip        ← Ladda ner
        │
        ▼
  vector_db/           ← Packa upp lokalt
        │
        ▼
  [Streamlit-appen]    ← Klar att använda!
```

---

## Tidsuppskattning

| Steg | Uppskattad tid |
|------|---------------|
| Lokal pipeline (steg 1-4) | 15-60 min (beroende på antal nya filer) |
| Uppladdning till Drive | 5-15 min |
| Colab chunking & embedding | 10-30 min |
| Nedladdning + uppackning | 5-10 min |
| **Totalt** | **~1-2 timmar** |
