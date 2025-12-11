"""
Laddar ner och packar upp vektordatabasen från Google Drive vid deployment
"""
import os
import gdown
import zipfile
from pathlib import Path
import streamlit as st

def download_and_extract_vectordb():
    """
    Ladda ner och packa upp vektordatabasen från Google Drive.
    Körs automatiskt vid första körningen i molnet.
    """
    
    # VIKTIGT: Byt ut detta mot din Google Drive fil-ID
    # Hitta ID:t i din delningslänk: https://drive.google.com/file/d/FILE_ID_HÄR/view
    # Detta är min länk: https://drive.google.com/file/d/1EbU2XJ1TyzlHTW_989hRg3IpS2-eDQ3v/view?usp=drive_link
    file_id = "1EbU2XJ1TyzlHTW_989hRg3IpS2-eDQ3v"
    
    # Konfiguration
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    output_zip = "vector_db.zip"
    output_dir = "vector_db"
    
    # Kolla om databasen redan finns
    if Path(output_dir).exists():
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
        with zipfile.ZipFile(output_zip, 'r') as zip_ref:
            zip_ref.extractall(".")
        
        # Ta bort ZIP-filen för att spara utrymme
        os.remove(output_zip)
        print("🗑️ Rensade temporära filer")
        
        # Verifiera att databasen är korrekt
        if not Path(output_dir).exists():
            print("❌ Uppackning misslyckades - mappen saknas!")
            return False
        
        # Räkna filer för verifiering
        db_files = list(Path(output_dir).rglob("*"))
        print(f"✅ Vektordatabasen är redo! ({len(db_files)} filer)")
        return True
        
    except Exception as e:
        print(f"❌ Fel vid nedladdning/uppackning: {e}")
        # Rensa eventuella ofullständiga nedladdningar
        if Path(output_zip).exists():
            os.remove(output_zip)
        return False

def get_database_info():
    """Returnera information om databasen"""
    db_path = Path("vector_db")
    
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
        "path": str(db_path.absolute())
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
    else:
        print("\n❌ Nedladdning misslyckades. Kontrollera:")
        print("   1. Att fil-ID är korrekt")
        print("   2. Att filen är delad med 'vem som helst med länken'")
        print("   3. Att du har internetanslutning")
        sys.exit(1)