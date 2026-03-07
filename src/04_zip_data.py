"""
zip_data.py – Zippa extraherade textfiler för Colab-uppladdning

Skapar en ZIP-fil av alla JSON-filer i extracted_text/-mappen
som sedan kan laddas upp till Google Drive för chunking & embedding i Colab.
"""

import zipfile
from pathlib import Path
from tqdm import tqdm

from utils.paths import EXTRACTED_TEXT_DIR, ZIP_OUTPUT_FILE, ensure_directories


def create_zip(source_dir: Path, output_file: Path):
    """Zippar alla JSON-filer i source_dir till output_file."""
    json_files = list(source_dir.glob("*.json"))

    if not json_files:
        print(f"Inga JSON-filer hittades i {source_dir}. Inget att zippa.")
        return

    print(f"Zippar {len(json_files)} JSON-filer till {output_file}...")

    with zipfile.ZipFile(output_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in tqdm(json_files, desc="Zippar filer"):
            # Spara med bara filnamnet (platt struktur i ZIP:en)
            zf.write(file_path, arcname=file_path.name)

    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"\n✅ ZIP-fil skapad: {output_file} ({size_mb:.1f} MB)")
    print("Ladda upp denna fil till Google Drive för att använda i Colab.")


def main():
    print("=" * 60)
    print("ZIPPAR DATA FÖR COLAB")
    print("=" * 60)

    ensure_directories()
    create_zip(EXTRACTED_TEXT_DIR, ZIP_OUTPUT_FILE)


if __name__ == "__main__":
    main()
