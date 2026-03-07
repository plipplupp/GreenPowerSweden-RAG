"""
03_text_extraction.py – Textextrahering (PARALLELL VERSION)

Konverterat från notebooks/03_text_extraction.ipynb.
Extraherar text från alla filer (PDF, XLSX, DOCX, HTML, EML, TXT)
och sparar som JSON-filer med unika hash-baserade namn.

Denna version använder Multiprocessing för att köra på alla processorkärnor samtidigt.
"""

import os
import json
import hashlib
import pandas as pd
import pdfplumber
import docx
import sys
from bs4 import BeautifulSoup
from pathlib import Path
from tqdm import tqdm
from email.parser import BytesParser
from email import policy
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import cpu_count

# Lägg till src-mappen i sys.path för att säkerställa att utils kan importeras i workers
sys.path.append(str(Path(__file__).resolve().parent))

# OCR-specifika importer
try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_ENABLED = True
    POPPLER_PATH = None 
except ImportError:
    OCR_ENABLED = False

# Importera centrala sökvägar
from utils.paths import (
    RAW_DATA_DIR, PROCESSED_DIR, ANALYSIS_REPORT_FILE,
    EXTRACTED_TEXT_DIR, ensure_directories
)

# ============================================================
# HJÄLPFUNKTIONER
# ============================================================

def get_unique_filename(original_path: Path, base_raw_dir: Path) -> str:
    """Skapar ett unikt men kort filnamn baserat på en hash av sökvägen."""
    try:
        relative_path = str(original_path.relative_to(base_raw_dir))
    except ValueError:
        relative_path = str(original_path)
    
    path_hash = hashlib.md5(relative_path.encode('utf-8')).hexdigest()
    short_name = original_path.name[:50]
    return f"{path_hash}_{short_name}.json"


def save_json(original_path: Path, pages_data: list, output_dir: Path, base_raw_dir: Path) -> str:
    """Sparar extraherad data och metadata som JSON."""
    try:
        output_filename = get_unique_filename(original_path, base_raw_dir)
        output_path = output_dir / output_filename

        try:
            relative_path = original_path.relative_to(base_raw_dir)
        except ValueError:
            relative_path = original_path.name

        data = {
            "filename": original_path.name,
            "full_path": str(relative_path),
            "pages": pages_data
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return "success"
    except Exception as e:
        return f"error_saving: {e}"

# ============================================================
# EXTRAHERINGSFUNKTIONER
# ============================================================

def extract_text_from_text_pdf(file_path: Path) -> list:
    pages_data = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                pages_data.append({"page_number": i + 1, "text": text})
    return pages_data

def extract_text_from_ocr_pdf(file_path: Path) -> list:
    if not OCR_ENABLED: return []
    pages_data = []
    images = convert_from_path(file_path, poppler_path=POPPLER_PATH)
    for i, img in enumerate(images):
        text = pytesseract.image_to_string(img, lang='swe')
        if text:
            pages_data.append({"page_number": i + 1, "text": text})
    return pages_data

def extract_text_from_xlsx(file_path: Path) -> list:
    text = ""
    xls = pd.ExcelFile(file_path)
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)
        text += f"--- Flik: {sheet_name} ---\n{df.to_string(index=False, header=False)}\n\n"
    return [{"page_number": 1, "text": text}]

def extract_text_from_docx(file_path: Path) -> list:
    doc = docx.Document(file_path)
    text = "\n".join([p.text for p in doc.paragraphs])
    return [{"page_number": 1, "text": text}]

def extract_text_from_html(file_path: Path) -> list:
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = BeautifulSoup(f, 'html.parser').get_text(separator="\n", strip=True)
    return [{"page_number": 1, "text": text}]

def extract_text_from_eml(file_path: Path) -> list:
    with open(file_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)
    text = ""
    body = msg.get_body(preferencelist=('plain', 'html'))
    if body: text = body.get_content()
    return [{"page_number": 1, "text": text}]

def extract_text_from_txt(file_path: Path) -> list:
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        text = f.read()
    return [{"page_number": 1, "text": text}]

# ============================================================
# WORKER-FUNKTIONER FÖR PARALLELLISERING
# ============================================================

def process_single_file(task):
    """Worker-funktion som körs i en egen process."""
    file_path, status, file_type = task
    
    try:
        pages_data = []
        extract_status = "success"

        if file_type == 'pdf':
            if status == 'text_based':
                pages_data = extract_text_from_text_pdf(file_path)
            elif status == 'ocr_candidate':
                pages_data = extract_text_from_ocr_pdf(file_path)
                extract_status = "success_ocr"
            else:
                return file_path.name, f"skipped_{status}"
        else:
            # Övriga filtyper
            ext = file_path.suffix.lower()
            if ext == '.xlsx': pages_data = extract_text_from_xlsx(file_path)
            elif ext == '.docx': pages_data = extract_text_from_docx(file_path)
            elif ext == '.html': pages_data = extract_text_from_html(file_path)
            elif ext == '.eml': pages_data = extract_text_from_eml(file_path)
            elif ext == '.txt': pages_data = extract_text_from_txt(file_path)

        if not pages_data:
            return file_path.name, "empty_or_error"

        save_status = save_json(file_path, pages_data, EXTRACTED_TEXT_DIR, RAW_DATA_DIR)
        return file_path.name, extract_status if save_status == "success" else save_status

    except Exception as e:
        return file_path.name, f"error: {str(e)[:100]}"

# ============================================================
# HUVUDPROCESS
# ============================================================

def main():
    print("=" * 60)
    print("STEG 3: TEXTEXTRAHERING (PARALLELL)")
    print("=" * 60)

    ensure_directories()
    num_cores = cpu_count()
    print(f"Använder {num_cores} processorkärnor.")

    # 1. Förbered uppgifter (Tasks)
    tasks = []

    # PDF-filer från rapporten
    try:
        df_analysis = pd.read_csv(ANALYSIS_REPORT_FILE)
        for _, row in df_analysis.iterrows():
            file_path = Path(row['full_path'])
            output_filename = get_unique_filename(file_path, RAW_DATA_DIR)
            if not (EXTRACTED_TEXT_DIR / output_filename).exists():
                tasks.append((file_path, row['status'], 'pdf'))
    except FileNotFoundError:
        print("Varning: Ingen PDF-analysrapport hittades.")

    # Övriga filer
    file_types = ['.xlsx', '.docx', '.html', '.eml', '.txt']
    for ext in file_types:
        for file_path in RAW_DATA_DIR.rglob(f'*{ext}'):
            output_filename = get_unique_filename(file_path, RAW_DATA_DIR)
            if not (EXTRACTED_TEXT_DIR / output_filename).exists():
                tasks.append((file_path, None, 'other'))

    if not tasks:
        print("Inga nya filer att bearbeta. Allt är uppdaterat.")
        return

    print(f"Startar bearbetning av {len(tasks)} filer...")

    # 2. Kör parallellt
    results = []
    with ProcessPoolExecutor(max_workers=num_cores) as executor:
        futures = {executor.submit(process_single_file, t): t for t in tasks}
        
        for future in tqdm(as_completed(futures), total=len(futures), desc="Extraherar text"):
            results.append(future.result())

    # 3. Summering
    df_res = pd.DataFrame(results, columns=['filename', 'status'])
    print("\n--- Resultat ---")
    print(df_res['status'].value_counts())
    
    total_json = len(list(EXTRACTED_TEXT_DIR.glob('*.json')))
    print(f"\nTotala antalet JSON-filer: {total_json}")
    print("\n✅ Textextrahering klar!")

if __name__ == "__main__":
    main()
