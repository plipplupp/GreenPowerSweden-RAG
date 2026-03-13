import os
from pathlib import Path
from huggingface_hub import HfApi, create_repo

def upload_db_to_hf():
    # Inställningar
    repo_id = "greenpowersweden/solveig-db"
    db_path = Path("/Users/gustav_jeansson/Documents/Data Science/GreenPowerSweden/vector_db_bgem3")
    
    # Hämta token från miljövariabel eller prompt
    token = os.environ.get("HF_TOKEN")
    if not token:
        print("HF_TOKEN saknas i miljövariabler.")
        token = input("Ange din Hugging Face Write Token: ").strip()
    
    api = HfApi()
    
    # Skapa repot om det inte finns
    try:
        create_repo(repo_id, repo_type="dataset", token=token, private=True)
        print(f"✅ Skapade privat dataset-repo: {repo_id}")
    except Exception as e:
        if "already exists" in str(e):
            print(f"ℹ️ Repo {repo_id} finns redan.")
        else:
            print(f"❌ Kunde inte hämta/skapa repo: {e}")
            return

    print(f"🚀 Startar uppladdning av vektordatabas (2.4 GB)...")
    
    try:
        api.upload_folder(
            folder_path=str(db_path),
            repo_id=repo_id,
            repo_type="dataset",
            token=token,
            path_in_repo="db"
        )
        print(f"\n✅ Klart! Vektordatabasen ligger nu på: https://huggingface.co/datasets/{repo_id}")
    except Exception as e:
        print(f"❌ Uppladdning misslyckades: {e}")

if __name__ == "__main__":
    upload_db_to_hf()
