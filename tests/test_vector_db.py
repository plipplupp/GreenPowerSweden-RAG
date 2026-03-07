
import sys
from pathlib import Path

# Lägg till projektets rot i sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

import torch
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from src.utils.paths import VECTOR_DB_DIR

def test_db_connection():
    print(f"--- Testar anslutning till Vektordatabas ---")
    print(f"Sökväg: {VECTOR_DB_DIR}")
    
    if not VECTOR_DB_DIR.exists():
        print(f"❌ Fel: Hittade inte mappen {VECTOR_DB_DIR}")
        return

    # Detektera enhet
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"Använder enhet: {device}")

    try:
        print("Laddar embedding-modell (BAAI/bge-m3)...")
        embedding_model = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={'device': device}
        )
        
        print("Ansluter till Chroma...")
        db = Chroma(
            persist_directory=str(VECTOR_DB_DIR),
            embedding_function=embedding_model
        )
        
        count = db._collection.count()
        print(f"✅ Success! Hittade {count} chunks i databasen.")
        
        # Testa en enkel sökning
        print("\nTestar en testsökning: 'solceller på jordbruksmark'")
        results = db.similarity_search("solceller på jordbruksmark", k=1)
        if results:
            print(f"✅ Sökning fungerade! Första resultatet från: {results[0].metadata.get('source', 'Okänd')}")
        else:
            print("⚠️ Sökningen gav inga resultat (men anslutningen fungerade).")
            
    except Exception as e:
        print(f"❌ Ett fel uppstod: {e}")

if __name__ == "__main__":
    test_db_connection()
