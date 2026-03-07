"""
Centraliserad sökvägshantering för GreenPowerSweden-projektet.

Alla sökvägar definieras relativt till projektets rot-mapp,
vilket gör det enkelt att flytta projektet mellan datorer.
"""

from pathlib import Path

# ============================================================
# PROJEKTROTEN – Beräknas automatiskt (2 nivåer upp från denna fil)
# src/utils/paths.py -> src/utils -> src -> PROJEKT_ROOT
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ============================================================
# DATA-MAPPAR
# ============================================================
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "01_raw"
UNSUPPORTED_DIR = DATA_DIR / "01_raw_unsupported"
PROCESSED_DIR = DATA_DIR / "02_processed"

# ============================================================
# OUTPUT-FILER OCH MAPPAR (under 02_processed)
# ============================================================
ANALYSIS_REPORT_FILE = PROCESSED_DIR / "pdf_analysis_report.csv"
EXTRACTED_TEXT_DIR = PROCESSED_DIR / "extracted_text"

# ============================================================
# VEKTOR-DATABAS
# ============================================================
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db_bgem3"

# ============================================================
# ZIP-FIL FÖR COLAB-UPPLADDNING
# ============================================================
ZIP_OUTPUT_FILE = PROCESSED_DIR / "all_json_files.zip"


def ensure_directories():
    """Skapar alla nödvändiga mappar om de inte redan finns."""
    for d in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DIR, EXTRACTED_TEXT_DIR,
              UNSUPPORTED_DIR, VECTOR_DB_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def print_paths():
    """Skriver ut alla definierade sökvägar (för felsökning)."""
    print("=" * 60)
    print("PROJEKTETS SÖKVÄGAR")
    print("=" * 60)
    print(f"  Projektrot:        {PROJECT_ROOT}")
    print(f"  Rå data:           {RAW_DATA_DIR}")
    print(f"  Ej stödda filer:   {UNSUPPORTED_DIR}")
    print(f"  Bearbetad data:    {PROCESSED_DIR}")
    print(f"  Analysrapport:     {ANALYSIS_REPORT_FILE}")
    print(f"  Extraherad text:   {EXTRACTED_TEXT_DIR}")
    print(f"  Vektordatabas:     {VECTOR_DB_DIR}")
    print(f"  ZIP för Colab:     {ZIP_OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    print_paths()
    ensure_directories()
    print("\nAlla mappar är skapade/verifierade.")
