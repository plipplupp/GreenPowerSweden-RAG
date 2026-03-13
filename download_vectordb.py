"""
Laddar ner vektordatabasen från Hugging Face Datasets vid deployment
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import snapshot_download

def get_hf_token():
    """Hämta HF_TOKEN från secrets eller environment"""
    try:
        import streamlit as st
        if 'HF_TOKEN' in st.secrets:
            return st.secrets['HF_TOKEN']
    except:
        pass
    return os.environ.get('HF_TOKEN')

def download_and_extract_vectordb():
    """
    Ladda ner vektordatabasen från Hugging Face Dataset.
    """
    repo_id = "greenpowersweden/solveig-db"
    output_dir = Path("vector_db_bgem3")
    
    # Kolla om databasen redan finns och är komplett
    if output_dir.exists() and (output_dir / "chroma.sqlite3").exists():
        print("✅ Vektordatabasen finns redan!")
        return True
    
    token = get_hf_token()
    if not token:
        print("⚠️ HF_TOKEN saknas. Kan inte ladda ner privat dataset.")
        return False

    try:
        print(f"📥 Laddar ner vektordatabas från Hugging Face ({repo_id})...")
        
        # Ladda ner mappen 'db' från datasetet
        downloaded_path = snapshot_download(
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
            allow_patterns="db/*"
        )
        
        source_db_path = Path(downloaded_path) / "db"
        
        if not source_db_path.exists():
            print(f"❌ Kunde inte hitta 'db'-mappen i nerladdat material: {downloaded_path}")
            return False
            
        print(f"✅ Nedladdning klar! Kopierar till {output_dir}...")
        
        # Kopiera innehållet till projektmappen
        if output_dir.exists():
            shutil.rmtree(output_dir)
            
        shutil.copytree(source_db_path, output_dir)
        
        print(f"✅ Vektordatabasen är redo!")
        return True
        
    except Exception as e:
        print(f"❌ Fel vid nedladdning: {e}")
        return False

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