import os
import shutil
import json
import torch
from pathlib import Path
from tqdm import tqdm
import chromadb
import gc
from time import sleep

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Importera projektets gemensamma paths
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from src.utils.paths import PROJECT_ROOT, EXTRACTED_TEXT_DIR

def run_local_embedding():
    # Sökvägsinställningar
    DB_PERSIST_DIR = PROJECT_ROOT / 'vector_db_bgem3'
    UNZIP_DIR = EXTRACTED_TEXT_DIR

    # True = Radera och bygg om från scratch
    # False = Inkrementell
    FULL_REBUILD = False
    
    # 1. Kolla enhet (GPU - M1/M2/M3)
    if torch.backends.mps.is_available():
        DEVICE = 'mps'
        print(f"✅ Använder Apple Silicon GPU (MPS) - Super för din M1 Max!")
    elif torch.cuda.is_available():
        DEVICE = 'cuda'
        print(f"✅ Använder Nvidia GPU (CUDA)")
    else:
        DEVICE = 'cpu'
        print(f"⚠️ Ingen GPU hittades, använder CPU (kommer gå extremt långsamt).")

    print('Läge: FULL REBUILD' if FULL_REBUILD else 'Läge: INKREMENTELL')
    print(f'Mål-databas: {DB_PERSIST_DIR}')

    # 2. Hantera databasen
    if FULL_REBUILD:
        if DB_PERSIST_DIR.exists():
            print('Raderar gammal databas för full ombyggnad...')
            try:
                shutil.rmtree(DB_PERSIST_DIR)
            except Exception as e:
                print(f"Kunde inte radera, försök manuellt: {e}")
        DB_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        existing_sources = set()
        print('Startar full ombyggnad.')
    else:
        DB_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        try:
            client = chromadb.PersistentClient(path=str(DB_PERSIST_DIR))
            collection = client.get_collection('langchain')
            
            existing_sources = set()
            total_count = collection.count()
            batch_size = 5000
            print(f'Hittade befintlig databas med {total_count} chunks. Läser historik...')
            
            for i in range(0, total_count, batch_size):
                batch = collection.get(limit=batch_size, offset=i, include=['metadatas'])
                for m in batch['metadatas']:
                    if m:
                        key = str(m.get('source', '')) + '__page_' + str(m.get('page', ''))
                        existing_sources.add(key)
                        
            print(f'Historik inläst! Unika sidor redan i databasen: {len(existing_sources)}')
        except Exception as e:
            existing_sources = set()
            print(f'Kunde inte läsa historik (kan vara tom). Fel: {e}')

    # 3. Ladda dokument
    documents = []
    skipped = 0
    all_files = list(UNZIP_DIR.rglob('*.json'))
    print(f'Hittade {len(all_files)} JSON-filer lokalt i {UNZIP_DIR}.')
    
    if not all_files:
        print("❌ Inga JSON-filer hittades. Har du kört text_extraction-steget nyligen?")
        return
        
    for file_path in tqdm(all_files, desc='Laddar dokument', unit='fil'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            filename = data.get('filename', file_path.name)
            full_path = data.get('full_path', 'Okänd sökväg')
            for page in data.get('pages', []):
                page_text = page.get('text', '')
                page_num = page.get('page_number', 1)
                if not page_text.strip():
                    continue
                source_key = filename + '__page_' + str(page_num)
                if source_key in existing_sources:
                    skipped += 1
                    continue
                metadata = {'source': filename, 'full_path': full_path, 'page': page_num}
                documents.append(Document(page_content=page_text, metadata=metadata))
        except Exception as e:
            print(f'❌ Kunde inte läsa {file_path.name}: {e}')

    print(f'Nya sidor att lägga in: {len(documents)}')
    print(f'Hoppades över (redan i DB): {skipped}')

    # 4. Chunking
    if not documents:
        print('Inga nya dokument. Databasen är uppdaterad!')
        all_chunks = []
    else:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            separators=['\n\n', '\n', ' ', '']
        )
        print('Dela upp dokumenten i chunks...')
        all_chunks = text_splitter.split_documents(documents)
        print(f'Dokument (sidor): {len(documents)}')
        print(f'Chunks skapade:   {len(all_chunks)}')

    # 5. Embedding-modell 
    if all_chunks:
        model_name = 'BAAI/bge-m3'
        print(f'Laddar embedding-modell ({model_name}) på M1 Max ({DEVICE})...')
        embedding_model = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={'device': DEVICE},
            encode_kwargs={'normalize_embeddings': False, 'batch_size': 32} 
        )
        print('✅ Modell laddad.')
    else:
        print('Inga chunks att embedda.')
        return

    # 6. Bygg databasen
    if all_chunks:
        print(f'Bygger databas med {len(all_chunks)} nya chunks...')
        db = Chroma(
            persist_directory=str(DB_PERSIST_DIR),
            embedding_function=embedding_model
        )
        
        # Batch size 64 verkar vara "sweet spot" för BGE-M3 + MPS utan att cachen fylls direkt
        batch_size = 64
        
        for i in tqdm(range(0, len(all_chunks), batch_size), desc='Skapar embeddings', unit='batch'):
            batch = all_chunks[i:i + batch_size]
            try:
                db.add_documents(batch)
            except Exception as e:
                print(f"❌ Fel vid batch {i}: {e}")
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                gc.collect()
                sleep(1) # Ge datorn en liten minipaus
                continue
            
            # Tömmer cachen var 10:e batch för att Macen ska kunna garbage-collecta
            if (i // batch_size) % 10 == 0: 
                if torch.backends.mps.is_available():
                    torch.mps.empty_cache()
                gc.collect()

        print(f'🎉 DATABAS KLAR! Totalt: {db._collection.count()} chunks sparade lokalt på din Mac.')

if __name__ == '__main__':
    run_local_embedding()
