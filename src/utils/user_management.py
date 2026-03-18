"""
Delad modul för användarhantering.
Används av både app.py (inbyggd admin) och admin.py (fristående bootstrap-verktyg).
"""

import bcrypt
import json
import hashlib
import re
import random
from pathlib import Path
from datetime import datetime

# Sökvägar
PROJECT_ROOT = Path(__file__).parent.parent.parent
USERS_FILE = PROJECT_ROOT / "data" / "users.json"
SECRETS_FILE = PROJECT_ROOT / ".streamlit" / "secrets.toml"

HF_REPO_ID = "greenpowersweden/solveig-db"

def get_hf_token():
    """Försök hämta HF_TOKEN eller HF_WRITE_TOKEN."""
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            if 'HF_WRITE_TOKEN' in st.secrets: return st.secrets['HF_WRITE_TOKEN']
            if 'HF_TOKEN' in st.secrets: return st.secrets['HF_TOKEN']
    except Exception:
        pass
    
    import os
    token = os.environ.get('HF_WRITE_TOKEN') or os.environ.get('HF_TOKEN')
    
    # Fallback to toml if local
    if not token and SECRETS_FILE.exists():
        try:
            import toml
            secrets = toml.load(SECRETS_FILE)
            token = secrets.get("HF_WRITE_TOKEN") or secrets.get("HF_TOKEN")
        except:
            pass
    return token

def sync_users_from_hf():
    """Laddar ner senaste users.json från HF-datasetet om tillgängligt."""
    token = get_hf_token()
    if not token:
        return False, "Kunde inte hitta HF_TOKEN för att synkronisera."
    
    try:
        from huggingface_hub import hf_hub_download
        import shutil
        cached_path = hf_hub_download(
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            filename="users.json",
            token=token,
            force_download=True
        )
        
        USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached_path, USERS_FILE)
        
        return True, "Användare har synkroniserats från molnet."
    except Exception as e:
        return False, f"Misslyckades att hämta från molnet: {e}"

def sync_users_to_hf():
    """Laddar upp lokal users.json till HF-datasetet."""
    if not USERS_FILE.exists():
        return False, "Ingen lokal users.json att ladda upp."
        
    token = get_hf_token()
    if not token:
        return False, "Kunde inte hitta HF_TOKEN för att synkronisera."
        
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        api.upload_file(
            path_or_fileobj=str(USERS_FILE),
            path_in_repo="users.json",
            repo_id=HF_REPO_ID,
            repo_type="dataset",
            token=token,
            commit_message="Auto-sync users.json"
        )
        return True, "Användare har laddats upp till molnet."
    except Exception as e:
        return False, f"Misslyckades att ladda upp till molnet: {e}"



# ==========================================
# LÖSENORDSGENERATOR – Sol/Energi-tema
# ==========================================

# Ordlistor med sol- och energirelaterade begrepp
SOLAR_WORDS_SV = [
    "Sol", "Ljus", "Energi", "Kraft", "Panel", "Effekt", "Watt", "Volt",
    "Stråle", "Glöd", "Värme", "Flöde", "Puls", "Gnista", "Ström",
    "Modul", "Nät", "Turbin", "Vind", "Grön", "Solpark", "Solcell",
]

SOLAR_WORDS_EN = [
    "Sun", "Light", "Beam", "Power", "Solar", "Glow", "Ray", "Spark",
    "Flux", "Watt", "Volt", "Grid", "Wind", "Green", "Bright", "Shine",
    "Blaze", "Flash", "Surge", "Peak", "Dawn", "Nova", "Pulse", "Radiant",
]

SPECIAL_CHARS = ["!", "#", "&", "@", "%", "?", "*", "+"]


def generate_solar_password() -> str:
    """Generera ett lösenord med sol/energi-tema.
    
    Format: Ord1 + specialtecken + Ord2 + siffror
    Exempel: Solar#Kraft42!, Sun&Effekt99
    """
    # Välj ett ord från varje lista
    word1 = random.choice(SOLAR_WORDS_EN + SOLAR_WORDS_SV)
    word2 = random.choice(SOLAR_WORDS_EN + SOLAR_WORDS_SV)
    
    # Se till att inte samma ord
    while word2 == word1:
        word2 = random.choice(SOLAR_WORDS_EN + SOLAR_WORDS_SV)
    
    special = random.choice(SPECIAL_CHARS)
    number = random.randint(10, 99)
    ending_special = random.choice(SPECIAL_CHARS)
    
    return f"{word1}{special}{word2}{number}{ending_special}"


def generate_multiple_passwords(count: int = 5) -> list[str]:
    """Generera flera unika lösenordsförslag."""
    passwords = set()
    attempts = 0
    while len(passwords) < count and attempts < 50:
        pw = generate_solar_password()
        # Kontrollera att det uppfyller kraven
        valid, _ = validate_password(pw)
        if valid:
            passwords.add(pw)
        attempts += 1
    return list(passwords)


# ==========================================
# HASHNING OCH VERIFIERING
# ==========================================

def hash_password_sha256(password: str) -> str:
    """Hash ett lösenord med SHA-256 (legacy/fallback)."""
    return hashlib.sha256(password.encode()).hexdigest()


def hash_password_bcrypt(password: str) -> str:
    """Hasha ett lösenord med bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password_bcrypt(password: str, hashed: str) -> bool:
    """Verifiera ett lösenord mot en bcrypt-hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def verify_password_smart(password: str, hashed_password: str) -> bool:
    """Verifiera ett lösenord – stöder både bcrypt och SHA-256 hashar."""
    if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
        return verify_password_bcrypt(password, hashed_password)
    else:
        return hash_password_sha256(password) == hashed_password


# ==========================================
# LÖSENORDSVALIDERING
# ==========================================

def validate_password(password: str) -> tuple[bool, str]:
    """Validera lösenordsstyrka. Returnerar (ok, meddelande)."""
    if len(password) < 8:
        return False, "Lösenordet måste vara minst 8 tecken."
    if not any(c.isupper() for c in password):
        return False, "Lösenordet måste innehålla minst en versal (A-Z)."
    if not any(c.islower() for c in password):
        return False, "Lösenordet måste innehålla minst en gemen (a-z)."
    if not any(c.isdigit() for c in password):
        return False, "Lösenordet måste innehålla minst en siffra (0-9)."
    return True, "Lösenordet uppfyller kraven."


def password_strength(password: str) -> tuple[str, str, float]:
    """Returnera (styrka_text, css_färg, progress_value)."""
    score = 0
    if len(password) >= 8:
        score += 1
    if len(password) >= 12:
        score += 1
    if any(c.isupper() for c in password):
        score += 1
    if any(c.islower() for c in password):
        score += 1
    if any(c.isdigit() for c in password):
        score += 1
    if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in password):
        score += 1
    
    if score <= 2:
        return "Svagt", "#ef4444", score / 6
    elif score <= 4:
        return "Medel", "#f59e0b", score / 6
    else:
        return "Starkt", "#10b981", score / 6


# ==========================================
# ANVÄNDARHANTERING (CRUD)
# ==========================================

def load_users() -> dict:
    """Ladda användare från JSON-filen."""
    if USERS_FILE.exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict):
    """Spara användare till JSON-filen."""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def get_user_role(username: str) -> str:
    """Hämta en användares roll. Returnerar 'user' som default."""
    users = load_users()
    if username in users:
        return users[username].get("role", "user")
    return "user"


def is_admin(username: str) -> bool:
    """Kontrollera om en användare har admin-rollen."""
    return get_user_role(username) == "admin"


def create_user(username: str, password: str, role: str = "user", 
                created_by: str = "admin") -> tuple[bool, str]:
    """Skapa en ny användare. Returnerar (ok, meddelande)."""
    users = load_users()
    username_clean = username.strip().lower()
    
    # Validera användarnamn
    if not username_clean:
        return False, "Användarnamn får inte vara tomt."
    if not all(c.isalnum() or c in "._-@" for c in username_clean):
        return False, "Användarnamnet får bara innehålla bokstäver, siffror, punkt, bindestreck, understreck och @."
    if username_clean in {u.lower() for u in users}:
        return False, f"Användaren '{username_clean}' finns redan."
    
    # Validera lösenord
    valid, msg = validate_password(password)
    if not valid:
        return False, msg
    
    # Skapa
    hashed = hash_password_bcrypt(password)
    users[username_clean] = {
        "password_hash": hashed,
        "role": role,
        "created_at": datetime.now().isoformat(),
        "created_by": created_by
    }
    
    save_users(users)
    update_secrets_file(users)
    ok, sync_msg = sync_users_to_hf()
    if not ok:
        return True, f"Användare skapades lokalt, men kunde INTE laddas upp till molnet: {sync_msg}"
    return True, f"Användare '{username_clean}' skapades och molnsynkroniserades!"


def reset_user_password(username: str, new_password: str) -> tuple[bool, str]:
    """Återställ en användares lösenord. Returnerar (ok, meddelande)."""
    users = load_users()
    if username not in users:
        return False, f"Användaren '{username}' finns inte."
    
    valid, msg = validate_password(new_password)
    if not valid:
        return False, msg
    
    users[username]["password_hash"] = hash_password_bcrypt(new_password)
    users[username]["updated_at"] = datetime.now().isoformat()
    save_users(users)
    update_secrets_file(users)
    ok, sync_msg = sync_users_to_hf()
    if not ok:
        return True, f"Lösenord uppdaterades lokalt, men kunde INTE laddas upp till molnet: {sync_msg}"
    return True, f"Lösenord uppdaterat för '{username}' och molnsynkroniserades."


def delete_user(username: str) -> tuple[bool, str]:
    """Ta bort en användare. Returnerar (ok, meddelande)."""
    users = load_users()
    if username not in users:
        return False, f"Användaren '{username}' finns inte."
    
    del users[username]
    save_users(users)
    update_secrets_file(users)
    ok, sync_msg = sync_users_to_hf()
    if not ok:
        return True, f"Användaren togs bort lokalt, men kunde INTE laddas upp till molnet: {sync_msg}"
    return True, f"Användare '{username}' borttagen och molnsynkroniserades."


# ==========================================
# SECRETS.TOML HANTERING
# ==========================================

def generate_secrets_toml_snippet(users: dict) -> str:
    """Generera en [users]-sektion för secrets.toml."""
    lines = ["[users]"]
    for username, info in users.items():
        hashed = info["password_hash"]
        lines.append(f'"{username}" = "{hashed}"')
    return "\n".join(lines)


def update_secrets_file(users: dict):
    """Uppdatera [users]-sektionen i secrets.toml utan att röra övriga inställningar."""
    # På Hugging Face Spaces är filesystemet read-only.
    # Vi hoppar över detta steg där och litar på users.json synkroniseringen.
    import os
    if os.environ.get("SPACE_ID") or os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud":
        return
        
    try:
        SECRETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Läs befintlig fil
        existing_content = ""
        if SECRETS_FILE.exists():
            with open(SECRETS_FILE, "r", encoding="utf-8") as f:
                existing_content = f.read()
        
        # Ta bort befintlig [users]-sektion (om den finns)
        pattern = r'\[users\].*?(?=\n\[|\Z)'
        cleaned = re.sub(pattern, '', existing_content, flags=re.DOTALL).strip()
        
        # Bygg ny [users]-sektion
        users_section = "\n[users]\n"
        for username, info in users.items():
            hashed = info["password_hash"]
            users_section += f'"{username}" = "{hashed}"\n'
        
        # Kombinera
        new_content = cleaned + "\n\n" + users_section.strip() + "\n"
        
        with open(SECRETS_FILE, "w", encoding="utf-8") as f:
            f.write(new_content.strip() + "\n")
    except (OSError, PermissionError):
        # Om vi ändå råkar på read-only miljö, ignorera felet
        pass


# ==========================================
# CREDENTIALS FÖR INLOGGNING
# ==========================================

def get_user_credentials_from_file() -> dict:
    """Hämta användaruppgifter från users.json.
    Returnerar dict med {username: password_hash}.
    """
    users = {}
    if USERS_FILE.exists():
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users_data = json.load(f)
            for uname, info in users_data.items():
                users[uname.lower()] = info["password_hash"]
        except Exception:
            pass
    return users
