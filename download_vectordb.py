"""
Laddar ner och packar upp vektordatabasen från Google Drive vid deployment
"""
import os
import gdown
import zipfile
import shutil
from pathlib import Path

def download_and_extract_vectordb():
    """
    Ladda ner och packa upp vektordatabasen från Google Drive.
    Hanterar automatiskt om ZIP:en har en extra mapp inuti.
    """
    
    # Google Drive fil-ID
    file_id = "1EbU2XJ1TyzlHTW_989hRg3IpS2-eDQ3v"
    
    # Konfiguration
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    output_zip = "vector_db_bgem3.zip"
    output_dir = "vector_db_bgem3"
    
    # Kolla om databasen redan finns
    if Path(output_dir).exists() and Path(output_dir, "chroma.sqlite3").exists():
        print("✅ Vektordatabasen finns redan!")
        return True
    
    try:
        print("📥 Laddar ner vektordatabas från Google Drive...")
        print(f"   URL: {url}")
        
        # Ladda ner med gdown
        gdown.download(url, output_zip, quiet=False, fuzzy=True)
        
        if not Path(output_zip).exists():
            print("❌ Nedladdning misslyckades!")
            return False
        
        print(f"✅ Nedladdning klar! Filstorlek: {os.path.getsize(output_zip) / (1024**2):.1f} MB")
        
        print("📦 Packar upp databas...")
        
        # Packa upp till temporär mapp
        temp_extract = "temp_extract"
        with zipfile.ZipFile(output_zip, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        
        # Hitta var chroma.sqlite3 faktiskt ligger
        sqlite_file = None
        for root, dirs, files in os.walk(temp_extract):
            if "chroma.sqlite3" in files:
                sqlite_file = Path(root)
                break
        
        if not sqlite_file:
            print("❌ Kunde inte hitta chroma.sqlite3 i ZIP-filen!")
            shutil.rmtree(temp_extract, ignore_errors=True)
            os.remove(output_zip)
            return False
        
        # Flytta innehållet till rätt plats
        print(f"📁 Hittat databas i: {sqlite_file}")
        
        if Path(output_dir).exists():
            shutil.rmtree(output_dir)
        
        # Flytta hela mappen
        shutil.move(str(sqlite_file), output_dir)
        
        # Rensa temporära filer
        shutil.rmtree(temp_extract, ignore_errors=True)
        os.remove(output_zip)
        print("🗑️ Rensade temporära filer")
        
        # Verifiera
        if not Path(output_dir, "chroma.sqlite3").exists():
            print("❌ Verifiering misslyckades - chroma.sqlite3 saknas!")
            return False
        
        # Räkna filer
        db_files = list(Path(output_dir).rglob("*"))
        print(f"✅ Vektordatabasen är redo! ({len(db_files)} filer)")
        return True
        
    except Exception as e:
        print(f"❌ Fel vid nedladdning/uppackning: {e}")
        # Rensa
        if Path(output_zip).exists():
            os.remove(output_zip)
        if Path("temp_extract").exists():
            shutil.rmtree("temp_extract", ignore_errors=True)
        return False

def get_database_info():
    """Returnera information om databasen"""
    db_path = Path("vector_db_bgem3")
    
    if not db_path.exists():
        return {
            "exists": False,
            "message": "Databas saknas - behöver laddas ner"
        }
    
    # Räkna filer och storlek
    files = list(db_path.rglob("*"))
    total_size = sum(f.stat().st_size for f in files if f.is_file())
    
    return {
        "exists": True,
        "files": len(files),
        "size_mb": total_size / (1024**2),
        "path": str(db_path.absolute()),
        "has_sqlite": (db_path / "chroma.sqlite3").exists()
    }

if __name__ == "__main__":
    """
    Kan köras standalone för att testa nedladdning lokalt:
    python download_vectordb.py
    """
    import sys
    
    print("=" * 60)
    print("Solaris - Vektordatabas Nedladdning")
    print("=" * 60)
    
    # Kolla aktuell status
    info = get_database_info()
    
    if info["exists"]:
        print(f"\n✅ Databas finns redan!")
        print(f"   Plats: {info['path']}")
        print(f"   Filer: {info['files']}")
        print(f"   Storlek: {info['size_mb']:.1f} MB")
        print(f"   SQLite-fil: {'✅ JA' if info.get('has_sqlite') else '❌ NEJ'}")
        
        response = input("\nVill du ladda ner igen? (y/N): ")
        if response.lower() != 'y':
            print("Avbryter.")
            sys.exit(0)
    
    # Ladda ner
    success = download_and_extract_vectordb()
    
    if success:
        info = get_database_info()
        print(f"\n🎉 Klart!")
        print(f"   Plats: {info['path']}")
        print(f"   Filer: {info['files']}")
        print(f"   Storlek: {info['size_mb']:.1f} MB")
        print(f"   SQLite-fil: {'✅ JA' if info.get('has_sqlite') else '❌ NEJ'}")
    else:
        print("\n❌ Nedladdning misslyckades. Kontrollera:")
        print("   1. Att fil-ID är korrekt")
        print("   2. Att filen är delad med 'vem som helst med länken'")
        print("   3. Att du har internetanslutning")
        sys.exit(1)