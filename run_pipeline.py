"""
run_pipeline.py – Orkestreringsskript

Kör hela den lokala bearbetningskedjan i rätt ordning:
  1. Dataförberedelse (städning, deduplicering)
  2. PDF-analys (text vs. OCR)
  3. Textextrahering (alla filtyper -> JSON)
  4. Zippa data för Colab-uppladdning

Användning:
    uv run python run_pipeline.py           # Kör alla steg
    uv run python run_pipeline.py --step 2  # Kör bara steg 2
"""

import sys
import time
import subprocess
from pathlib import Path


# Alla steg i ordning
STEPS = [
    {"num": 1, "name": "Dataförberedelse",   "script": "src/01_data_prep.py"},
    {"num": 2, "name": "PDF-analys",          "script": "src/02_pdf_ocr_analysis.py"},
    {"num": 3, "name": "Textextrahering",     "script": "src/03_text_extraction.py"},
    {"num": 4, "name": "Zippa för Colab",     "script": "src/04_zip_data.py"},
]


def run_step(step: dict, project_root: Path, total_steps: int):
    """Kör ett enskilt steg som en subprocess med live-output."""
    script_path = project_root / step["script"]

    print(f"\n" + "="*60)
    print(f"  [{step['num']}/{total_steps}] {step['name']}")
    print(f"  Kör: {step['script']}")
    print(f"="*60)

    start = time.time()

    # Kör med PYTHONUNBUFFERED=1 och stream:a output direkt
    env = {**__import__('os').environ, 'PYTHONUNBUFFERED': '1'}
    process = subprocess.Popen(
        [sys.executable, '-u', str(script_path)],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
    )

    # Streama varje rad direkt till terminalen
    for line in process.stdout:
        print(line, end='', flush=True)

    process.wait()
    elapsed = time.time() - start

    if process.returncode != 0:
        print(f"\n❌ STEG {step['num']} misslyckades! (avslutskod: {process.returncode})")
        return False

    print(f"\n⏱️  Steg {step['num']} klart på {elapsed:.0f} sekunder.")
    return True, elapsed


def main():
    project_root = Path(__file__).resolve().parent

    # Kolla om ett specifikt steg begärdes
    target_step = None
    if "--step" in sys.argv:
        idx = sys.argv.index("--step")
        if idx + 1 < len(sys.argv):
            target_step = int(sys.argv[idx + 1])

    print("╔" + "═" * 58 + "╗")
    print("║          GREEN POWER SWEDEN – DATAPIPELINE              ║")
    print("╚" + "═" * 58 + "╝")

    if target_step:
        steps_to_run = [s for s in STEPS if s["num"] == target_step]
        if not steps_to_run:
            print(f"FEL: Steg {target_step} finns inte. Tillgängliga steg: 1-{len(STEPS)}")
            sys.exit(1)
    else:
        steps_to_run = STEPS

    total_start = time.time()
    success_count = 0
    step_times = []

    for i, step in enumerate(steps_to_run):
        result = run_step(step, project_root, len(steps_to_run))
        if result is False:
            print(f"\nPipelinen avbröts vid steg {step['num']}.")
            sys.exit(1)
        ok, elapsed = result
        step_times.append(elapsed)
        success_count += 1

        # Uppskatta återstående tid baserat på genomsnittlig steg-tid
        remaining_steps = len(steps_to_run) - (i + 1)
        if remaining_steps > 0 and step_times:
            avg_time = sum(step_times) / len(step_times)
            eta_seconds = avg_time * remaining_steps
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            print(f"  📊 Återstående steg: {remaining_steps} | Uppskattad tid kvar: ~{eta_min}m {eta_sec}s")

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 60)
    print(f"✅ ALLA {success_count} STEG KLARA! (totalt {total_elapsed:.1f} sekunder)")
    print("=" * 60)
    print("\nNÄSTA STEG:")
    print("  1. Ladda upp ZIP-filen till Google Drive")
    print("  2. Öppna notebooks/04_chunking_and_embedding.ipynb i Colab")
    print("  3. Kör igenom notebooken för att skapa vektordatabasen")
    print("  4. Ladda ner den nya vector_db.zip")
    print("  5. Packa upp i vector_db/-mappen lokalt")
    print("  6. Starta Streamlit-appen")


if __name__ == "__main__":
    main()
