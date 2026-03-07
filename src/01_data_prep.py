"""
01_data_prep.py – Dataförberedelse

Konverterat från notebooks/01_data_prep.ipynb.
Hanterar:
  1. Filinventering (räknar filtyper)
  2. ZIP-uppackning
  3. Dubblettborttagning (SHA256)
  4. Borttagning av tomma mappar
  5. Flytt av filer som ej stöds (bilder, CAD, film, etc.)
"""

import os
import zipfile
import hashlib
import shutil
from pathlib import Path
from collections import Counter
from tqdm import tqdm

# Importera centrala sökvägar
from utils.paths import RAW_DATA_DIR, UNSUPPORTED_DIR, ensure_directories

# ============================================================
# KONFIGURATION
# ============================================================
# Landskapsnamn som ska skyddas (deras mappar raderas aldrig)
CORE_LANDSCAPE_NAMES = [
    'blekinge', 'dalarna', 'gotland', 'gävleborg', 'halland', 'jämtland',
    'jönköping', 'kalmar', 'kronoberg', 'norrbotten', 'skåne', 'stockholm',
    'södermanland', 'uppsala', 'värmland', 'västerbotten', 'västernorrland',
    'västmanland', 'västra götaland', 'örebro', 'östergötland'
]

# Filändelser vi EJ kan bearbeta
UNSUPPORTED_EXTENSIONS = ['.jpg', '.heic', '.dwg', '.mov']


# ============================================================
# HJÄLPFUNKTIONER
# ============================================================

def run_file_inventory(directory: Path):
    """Söker igenom och räknar filtyper i en mapp."""
    print(f"\n--- Startar inventering av: {directory} ---")
    file_extensions = []
    for file_path in directory.rglob('*'):
        if file_path.is_file():
            extension = file_path.suffix.lower()
            file_extensions.append(extension if extension else "<ingen filändelse>")

    file_counts = Counter(file_extensions)
    total_files = 0

    if not file_counts:
        print("Mappen är tom eller innehåller inga filer.")
        return 0

    print("Resultat:")
    for ext, count in file_counts.most_common():
        print(f"{ext:<15} {count} filer")
        total_files += count
    print("-" * 30)
    print(f"{'TOTALT':<15} {total_files} filer")
    return total_files


def get_file_hash(file_path: Path) -> str:
    """Beräknar SHA256-hashen för en fil."""
    sha256 = hashlib.sha256()
    try:
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except IOError:
        return ""  # Vid läsfel


def unzip_files(target_dir: Path):
    """Packar upp alla ZIP-filer och raderar originalen."""
    zip_files = list(target_dir.rglob('*.zip'))
    print(f"\nHittade {len(zip_files)} ZIP-filer att bearbeta.")

    for zip_file_path in zip_files:
        print(f"\nBearbetar: {zip_file_path.name}...")
        extract_folder = zip_file_path.parent

        try:
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(extract_folder)
            print(f"  -> Uppackad till: {extract_folder}")
            os.remove(zip_file_path)
            print(f"  -> Original .zip-fil raderad.")
        except zipfile.BadZipFile:
            print(f"  -> FEL: Kunde inte öppna {zip_file_path.name}. Filen kan vara korrupt.")
        except Exception as e:
            print(f"  -> FEL: Ett okänt fel uppstod: {e}")

    print("\nZIP-bearbetning klar.")


def remove_duplicates(target_dir: Path, all_files: list) -> int:
    """Hittar och raderar dubblettfiler baserat på SHA256-hash."""
    seen_hashes = {}
    duplicate_count = 0

    candidates = [f for f in all_files if f.is_file() and f.suffix.lower() != '.zip']
    print(f"\nDubblettkontroll på {len(candidates)} filer (kan ta flera minuter)...")

    for file_path in tqdm(candidates, desc="Kontrollerar dubbletter", unit="fil"):
        file_hash = get_file_hash(file_path)
        if not file_hash:
            continue

        if file_hash in seen_hashes:
            duplicate_count += 1
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"  -> FEL: Kunde inte radera: {file_path.name}: {e}")
        else:
            seen_hashes[file_hash] = file_path

    print(f"\n--- Dubblettkontroll klar! ---")
    print(f"Unika filer behållna: {len(seen_hashes)} | Dubbletter raderade: {duplicate_count}")
    return duplicate_count


def is_protected_folder(folder_name: str, core_names: list[str]) -> bool:
    """Kollar om mappnamnet innehåller något av kärnsymbolerna."""
    folder_name_lower = folder_name.lower()
    for name in core_names:
        if name in folder_name_lower:
            return True
    return False


def remove_empty_folders(target_dir: Path):
    """Raderar tomma mappar, men hoppar över skyddade landskapsmappar."""
    removed_count = 0
    print("\nStartar rensning av tomma mappar...")

    for folder_path in sorted(target_dir.rglob('*'), reverse=True):
        if folder_path.is_dir():
            if is_protected_folder(folder_path.name, CORE_LANDSCAPE_NAMES):
                continue
            try:
                if not any(folder_path.iterdir()):
                    os.rmdir(folder_path)
                    removed_count += 1
            except OSError:
                pass

    print(f"Totalt antal tomma mappar rensade: {removed_count}")


def move_unsupported_files(target_dir: Path, unsupported_dir: Path):
    """Flyttar filer med filtyper som ej stöds till en separat mapp."""
    unsupported_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nMapp för filer som inte stöds: {unsupported_dir}")
    print(f"Genomsöker {target_dir} efter filer att flytta...")

    files_to_move = []
    for ext in UNSUPPORTED_EXTENSIONS:
        files_to_move.extend(target_dir.rglob(f'*{ext}'))

    if not files_to_move:
        print("Hittade inga filer med ej stödda filändelser.")
        return

    print(f"Hittade {len(files_to_move)} filer att flytta...")
    moved_count = 0
    failed_count = 0

    for file_path in files_to_move:
        try:
            destination_name = f"{file_path.stem}_{file_path.parent.name}{file_path.suffix}"
            destination_path = unsupported_dir / destination_name

            counter = 1
            while destination_path.exists():
                destination_name = f"{file_path.stem}_{file_path.parent.name}_{counter}{file_path.suffix}"
                destination_path = unsupported_dir / destination_name
                counter += 1

            shutil.move(file_path, destination_path)
            moved_count += 1
        except Exception as e:
            print(f"  -> FEL: Kunde inte flytta {file_path.name}. Fel: {e}")
            failed_count += 1

    print(f"\n--- Flytt klar! ---")
    print(f"Totalt antal filer flyttade: {moved_count}")
    if failed_count > 0:
        print(f"Totalt antal misslyckade flyttar: {failed_count}")


# ============================================================
# HUVUDPROCESS
# ============================================================

def main():
    print("=" * 60)
    print("STEG 1: DATAFÖRBEREDELSE")
    print("=" * 60)

    ensure_directories()

    if not RAW_DATA_DIR.exists():
        print(f"FEL: Mappen {RAW_DATA_DIR} finns inte.")
        print("Se till att rådata finns på rätt plats.")
        return

    # 1. Filinventering FÖRE + räkna filer
    print("\nRäknar filer...", end="", flush=True)
    all_raw_files = list(RAW_DATA_DIR.rglob('*'))
    num_files = sum(1 for f in all_raw_files if f.is_file())
    num_zips  = sum(1 for f in all_raw_files if f.suffix.lower() == '.zip' and f.is_file())
    print(f" {num_files} filer totalt ({num_zips} ZIP-filer)")

    # 2. Packa upp ZIP-filer
    if num_zips > 0:
        print("\n📦 Packar upp ZIP-filer...")
        unzip_files(RAW_DATA_DIR)
        # Uppdatera fillistan efter uppackning
        all_raw_files = list(RAW_DATA_DIR.rglob('*'))
    else:
        print("\nInga ZIP-filer att packa upp.")

    # 3. Ta bort dubbletter
    print()
    remove_duplicates(RAW_DATA_DIR, all_raw_files)

    # 4. Rensa tomma mappar
    remove_empty_folders(RAW_DATA_DIR)

    # 5. Flytta filer som ej stöds
    move_unsupported_files(RAW_DATA_DIR, UNSUPPORTED_DIR)

    # 6. Filinventering EFTER
    print("\n📋 Inventering EFTER städning:")
    run_file_inventory(RAW_DATA_DIR)

    print("\n✅ Dataförberedelse klar!")


if __name__ == "__main__":
    main()
