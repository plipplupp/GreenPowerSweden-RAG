"""
02_pdf_ocr_analysis.py – PDF-analys (Text vs. OCR)

Konverterat från notebooks/02_pdf_ocr_analysis.ipynb.
Analyserar varje PDF-fil för att avgöra om den är textbaserad
eller om den kräver OCR (skannad bild).
Sparar resultaten i en CSV-rapport.
Stödjer inkrementella uppdateringar – analyserar bara NYA filer.
"""

import pandas as pd
import pdfplumber
from pathlib import Path
from tqdm import tqdm

# Importera centrala sökvägar
from utils.paths import RAW_DATA_DIR, PROCESSED_DIR, ANALYSIS_REPORT_FILE, ensure_directories


# ============================================================
# ANALYSFUNKTION
# ============================================================

def analyze_pdf_type(file_path: Path) -> dict:
    """
    Analyserar en enskild PDF och returnerar dess typ.

    Heuristik:
      - > 50 tecken på sida 1 => text_based
      - <= 50 tecken på sida 1 => ocr_candidate
    """
    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                return {"status": "error_no_pages", "chars_page_1": 0, "total_pages": 0}

            first_page = pdf.pages[0]
            text = first_page.extract_text()
            char_count = len(text.strip()) if text else 0
            total_pages = len(pdf.pages)

            if char_count > 50:
                return {"status": "text_based", "chars_page_1": char_count, "total_pages": total_pages}
            else:
                return {"status": "ocr_candidate", "chars_page_1": char_count, "total_pages": total_pages}

    except Exception as e:
        return {"status": f"error_{type(e).__name__}", "chars_page_1": 0, "total_pages": 0}


# ============================================================
# HUVUDPROCESS
# ============================================================

def main():
    print("=" * 60)
    print("STEG 2: PDF-ANALYS (Text vs. OCR)")
    print("=" * 60)

    ensure_directories()

    # 1. Ladda befintlig rapport (om den finns)
    try:
        df_existing = pd.read_csv(ANALYSIS_REPORT_FILE)
        seen_files = set(df_existing['full_path'].apply(lambda x: str(Path(x))))
        print(f"Hittade en befintlig rapport med {len(seen_files)} analyserade filer.")
    except FileNotFoundError:
        print("Ingen befintlig rapport hittades. Startar en ny analys.")
        df_existing = pd.DataFrame(columns=["full_path", "status", "chars_page_1", "total_pages", "filename"])
        seen_files = set()

    # 2. Hitta ALLA PDF-filer på disk
    print(f"Söker efter ALLA PDF-filer i: {RAW_DATA_DIR}...")
    all_pdf_files = list(RAW_DATA_DIR.rglob("*.pdf"))
    print(f"Hittade totalt {len(all_pdf_files)} PDF-filer på disken.")

    # 3. Filtrera ut NYA filer
    files_to_analyze = [
        f for f in all_pdf_files
        if str(f) not in seen_files
    ]

    print(f"\n--- Analys-sammanfattning ---")
    print(f"Totalt antal filer på disk: {len(all_pdf_files)}")
    print(f"Filer redan analyserade:   {len(seen_files)}")
    print(f"NYA filer att analysera:    {len(files_to_analyze)}")

    # 4. Rensa bort borttagna filer från rapporten
    existing_paths_on_disk = set(str(p) for p in all_pdf_files)
    original_count = len(df_existing)
    df_existing = df_existing[df_existing['full_path'].apply(lambda x: str(Path(x)) in existing_paths_on_disk)]
    removed_count = original_count - len(df_existing)
    if removed_count > 0:
        print(f"Rensade bort {removed_count} borttagna filer från rapporten.")

    # 5. Analysera NYA filer
    new_analysis_results = []

    if files_to_analyze:
        print(f"\nStartar analys av {len(files_to_analyze)} nya filer...")
        for file in tqdm(files_to_analyze, desc="Analyserar NYA PDF-filer"):
            result = analyze_pdf_type(file)
            result["full_path"] = str(file)
            result["filename"] = file.name
            new_analysis_results.append(result)
        print("Analys av nya filer klar.")
    else:
        print("Inga nya filer att analysera. Allt är uppdaterat.")

    # 6. Kombinera och spara
    df_new = pd.DataFrame(new_analysis_results)
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)

    print(f"\n--- Sammanfattning av TOTAL PDF-analys ---")
    if not df_combined.empty:
        print(df_combined['status'].value_counts())

    df_combined.to_csv(ANALYSIS_REPORT_FILE, index=False, encoding='utf-8-sig')
    print(f"\nFullständig rapport sparad till:\n{ANALYSIS_REPORT_FILE}")

    print("\n✅ PDF-analys klar!")


if __name__ == "__main__":
    main()
