"""
Laddar ner vektordatabasen från Hugging Face Datasets vid deployment
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download

def get_hf_token():
    """Hämta HF_TOKEN från secrets eller environment"""
    # 1. Kolla Streamlit secrets (förstahandsval i molnet)
    try:
        import streamlit as st
        if 'HF_TOKEN' in st.secrets:
            return st.secrets['HF_TOKEN']
    except:
        pass
        
    # 2. Kolla miljövariabler ( fallback, viktigt för vissa miljöer)
    return os.environ.get('HF_TOKEN') or os.environ.get('HF_WRITE_TOKEN')

def download_and_extract_vectordb(st_container=None):
    """
    Ladda ner vektordatabasen från Hugging Face Dataset.
    """
    repo_id = "greenpowersweden/solveig-db"
    output_dir = Path("vector_db_bgem3")
    
    def log(msg, type="info"):
        print(msg)
        if st_container:
            if type == "error":
                st_container.error(msg)
            elif type == "success":
                st_container.success(msg)
            else:
                st_container.info(msg)

    # Kolla om databasen redan finns och är komplett
    if output_dir.exists() and (output_dir / "chroma.sqlite3").exists():
        log("✅ Vektordatabasen finns redan!", "success")
        return True, "Redan installerad"
    
    token = get_hf_token()
    if not token:
        msg = "⚠️ HF_TOKEN hittades inte i secrets eller env. Kan inte ladda ner privat dataset."
        log(msg, "error")
        return False, msg
    else:
        # Säkerhetsmaskad loggning för att verifiera att vi har rätt token
        masked_token = f"{token[:6]}...{token[-3:]}" if len(token) > 10 else "***"
        log(f"🔑 Använder token: {masked_token}")
    
    try:
        log(f"📥 Laddar ner vektordatabas från Hugging Face ({repo_id})...")
        
        # Ladda ner från datasetet
        try:
            downloaded_path = snapshot_download(
                repo_id=repo_id,
                repo_type="dataset",
                token=token
            )
        except Exception as e:
            msg = f"❌ Snapshot download misslyckades: {e}"
            log(msg, "error")
            return False, msg
            
        source_db_path = Path(downloaded_path) / "db"
        
        # Fallback: Om filerna ligger direkt i roten istället för 'db/'
        if not source_db_path.exists():
            if (Path(downloaded_path) / "chroma.sqlite3").exists():
                source_db_path = Path(downloaded_path)
            else:
                msg = f"❌ Kunde inte hitta databasfiler i {downloaded_path}"
                log(msg, "error")
                return False, msg
            
        log(f"✅ Nedladdning klar! Kopierar till {output_dir.absolute()}...")
        
        # Kopiera innehållet till projektmappen
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        shutil.copytree(source_db_path, output_dir)
        
        log(f"✅ Vektordatabasen är redo!", "success")
        return True, "Success"
        
    except Exception as e:
        msg = f"❌ Oväntat fel: {e}"
        log(msg, "error")
        return False, msg

def get_database_info():
    """Returnera information om databasen"""
    db_path = Path("vector_db_bgem3")
    
    if not db_path.exists():
        return {
            "exists": False,
            "message": "Databas saknas - behöver laddas ner"
        }
    
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
    download_and_extract_vectordb()