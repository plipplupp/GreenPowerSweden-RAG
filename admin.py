"""
🔧 Solveig Admin – Bootstrap-verktyg
======================================
Fristående adminverktyg för att skapa de FÖRSTA användarna i Solveig-appen.
I vardagen sköts användarhantering inifrån Solveig-appen (för admin-användare).

Kör med: streamlit run admin.py --server.port 8502
"""

import streamlit as st
import os
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Ladda miljövariabler från .env-fil
load_dotenv()

# Delad modul för användarhantering
from src.utils.user_management import (
    load_users, save_users, create_user, delete_user, reset_user_password,
    hash_password_bcrypt, verify_password_bcrypt, validate_password,
    password_strength, generate_multiple_passwords,
    generate_secrets_toml_snippet, update_secrets_file, USERS_FILE,
    sync_users_from_hf, sync_users_to_hf
)

# ==========================================
# KONFIGURATION
# ==========================================

st.set_page_config(
    page_title="Solveig Admin",
    page_icon="🔧",
    layout="centered",
    initial_sidebar_state="collapsed"
)

if "users_synced" not in st.session_state:
    try:
        from src.utils.user_management import sync_users_from_hf
        sync_users_from_hf()
    except:
        pass
    st.session_state.users_synced = True


# ==========================================
# CSS STYLING
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp { font-family: 'Inter', sans-serif; }
    
    .admin-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #2d5a8e 50%, #3a7bd5 100%);
        padding: 2.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
        box-shadow: 0 8px 32px rgba(30, 58, 95, 0.3);
    }
    .admin-header h1 {
        color: #ffffff !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: -0.5px;
    }
    .admin-header p {
        color: rgba(255, 255, 255, 0.85);
        font-size: 1rem;
        margin-top: 0.5rem;
        font-weight: 300;
    }
    
    .stat-card {
        background: #ffffff;
        border: 1px solid #e8ecf1;
        border-radius: 12px;
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .stat-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .stat-number {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a5f;
        line-height: 1;
    }
    .stat-label {
        font-size: 0.85rem;
        color: #6b7280;
        margin-top: 0.5rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .user-card {
        background: #ffffff;
        border: 1px solid #e8ecf1;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        transition: all 0.2s ease;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
    }
    .user-card:hover {
        border-color: #3a7bd5;
        box-shadow: 0 4px 12px rgba(58, 123, 213, 0.1);
    }
    .user-info {
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .user-avatar {
        width: 42px;
        height: 42px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3a7bd5, #1e3a5f);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 1.1rem;
    }
    .user-name { font-weight: 600; color: #1e3a5f; font-size: 1rem; }
    .user-role { font-size: 0.8rem; color: #6b7280; margin-top: 2px; }
    .user-meta { font-size: 0.78rem; color: #9ca3af; text-align: right; }
    
    .section-title {
        font-size: 1.15rem;
        font-weight: 600;
        color: #1e3a5f;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #e8ecf1;
    }
    
    .success-box {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        border: 1px solid #6ee7b7;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        color: #065f46;
        font-weight: 500;
        margin: 1rem 0;
    }
    .error-box {
        background: linear-gradient(135deg, #fee2e2, #fecaca);
        border: 1px solid #fca5a5;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        color: #991b1b;
        font-weight: 500;
        margin: 1rem 0;
    }
    .info-box {
        background: linear-gradient(135deg, #dbeafe, #bfdbfe);
        border: 1px solid #93c5fd;
        border-radius: 10px;
        padding: 1rem 1.25rem;
        color: #1e40af;
        font-weight: 500;
        margin: 1rem 0;
    }
    
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #a8e063, #56ab2f) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(86, 171, 47, 0.3) !important;
    }
    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 16px rgba(86, 171, 47, 0.4) !important;
        transform: translateY(-1px) !important;
    }
    
    .stTabs [data-baseweb="tab-list"] { gap: 0.5rem; }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }
    
    .stTextInput > div > div > input {
        border-radius: 8px !important;
        border: 1.5px solid #d1d5db !important;
        padding: 0.6rem 0.8rem !important;
        transition: border-color 0.2s ease !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #3a7bd5 !important;
        box-shadow: 0 0 0 3px rgba(58, 123, 213, 0.1) !important;
    }
    
    .admin-footer {
        text-align: center;
        padding: 2rem 0;
        color: #9ca3af;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# ADMIN-AUTENTISERING
# ==========================================

def check_admin_auth() -> bool:
    """Enkel admin-autentisering med PIN."""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    return st.session_state.admin_authenticated


def admin_login_page():
    """Visa admin-inloggning."""
    st.markdown("""
    <div class="admin-header">
        <h1>🔧 Solveig Admin</h1>
        <p>Bootstrap-verktyg för användarhantering</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="section-title">🔐 Admin-inloggning</div>', unsafe_allow_html=True)
        
        admin_pin = st.text_input(
            "Admin-PIN", 
            type="password", 
            placeholder="Ange admin-PIN...",
            help="Ändra PIN genom att sätta miljövariabeln ADMIN_PIN"
        )
        
        if st.button("Logga in", type="primary", use_container_width=True):
            ADMIN_PIN = os.environ.get("ADMIN_PIN")
            
            if not ADMIN_PIN:
                st.markdown('<div class="error-box">⚠️ ADMIN_PIN är inte konfigurerad i miljövariabler/secrects.</div>', unsafe_allow_html=True)
            elif admin_pin == ADMIN_PIN:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.markdown('<div class="error-box">❌ Fel PIN-kod</div>', unsafe_allow_html=True)
        
        st.markdown("")
        st.caption("💡 Ändra PIN genom att sätta miljövariabeln `ADMIN_PIN`.")
        st.markdown("")
        st.markdown("""
        <div class="info-box">
            ℹ️ Detta är ett <strong>bootstrap-verktyg</strong> för att skapa de första användarna. 
            I vardagen hanteras användare inifrån Solveig-appen av admin-användare.
        </div>
        """, unsafe_allow_html=True)


# ==========================================
# HUVUDSIDA
# ==========================================

def main():
    if not check_admin_auth():
        admin_login_page()
        return
    
    # Header
    st.markdown("""
    <div class="admin-header">
        <h1>🔧 Solveig Admin</h1>
        <p>Hantera användare och behörigheter</p>
    </div>
    """, unsafe_allow_html=True)
    
    col_sync1, col_sync2, col_sync3 = st.columns([1, 2, 1])
    with col_sync2:
        if st.button("☁️ Synka från molnet", type="primary", use_container_width=True):
            with st.spinner("Synkar..."):
                ok, msg = sync_users_from_hf()
                if ok:
                    st.success(f"✅ {msg}")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    users = load_users()
    
    # Statistik
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{len(users)}</div>
            <div class="stat-label">Registrerade användare</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        admin_count = sum(1 for u in users.values() if u.get("role") == "admin")
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{admin_count}</div>
            <div class="stat-label">Administratörer</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        user_count = len(users) - admin_count
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{user_count}</div>
            <div class="stat-label">Vanliga användare</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # Tabs
    tab_add, tab_users, tab_export = st.tabs([
        "➕ Lägg till användare", 
        "👥 Hantera användare",
        "📋 Exportera / Secrets"
    ])
    
    # ======================
    # TAB 1: Lägg till
    # ======================
    with tab_add:
        st.markdown("")
        st.markdown('<div class="section-title">Skapa ny användare</div>', unsafe_allow_html=True)
        
        col_form, col_preview = st.columns([3, 2], gap="large")
        
        # Trigger för att nollställa formulär
        if "form_trigger" not in st.session_state:
            st.session_state.form_trigger = 0
            
        with col_form:
            new_username = st.text_input(
                "Användarnamn",
                placeholder="t.ex. anna.svensson",
                help="Användarnamnet kan innehålla bokstäver, siffror, punkt och understreck.",
                key=f"admintool_new_username_{st.session_state.form_trigger}"
            )
            
            # Lösenordsgenerator
            st.markdown("**Lösenord**")
            if "generated_passwords" not in st.session_state:
                st.session_state.generated_passwords = []
            
            col_pw_input, col_pw_gen = st.columns([3, 1])
            with col_pw_input:
                new_password = st.text_input(
                    "Lösenord",
                    type="password",
                    placeholder="Minst 8 tecken...",
                    help="Lösenordet hashas med bcrypt innan det sparas.",
                    label_visibility="collapsed",
                    key=f"admintool_new_password_{st.session_state.form_trigger}"
                )
            with col_pw_gen:
                if st.button("☀️ Generera", use_container_width=True, key="gen_pw_btn"):
                    st.session_state.generated_passwords = generate_multiple_passwords(5)
            
            # Visa genererade lösenord
            if st.session_state.generated_passwords:
                st.markdown("**Förslag** *(klicka för att kopiera)*:")
                for i, pw in enumerate(st.session_state.generated_passwords):
                    st.code(pw, language=None)
                
                if st.button("🔄 Generera nya förslag", key="regen_pw_btn"):
                    st.session_state.generated_passwords = generate_multiple_passwords(5)
                    st.rerun()
            
            confirm_password = st.text_input(
                "Bekräfta lösenord",
                type="password",
                placeholder="Upprepa lösenordet...",
                key=f"admintool_confirm_password_{st.session_state.form_trigger}"
            )
            
            new_role = st.selectbox(
                "Roll",
                options=["user", "admin"],
                format_func=lambda x: "👤 Användare" if x == "user" else "🔧 Administratör",
                help="Administratörer har tillgång till admin-funktioner i Solveig.",
                key=f"admintool_role_{st.session_state.form_trigger}"
            )
        
        with col_preview:
            st.markdown("**Lösenordskrav:**")
            if new_password:
                strength_text, strength_color, strength_val = password_strength(new_password)
                
                checks = [
                    ("✅" if len(new_password) >= 8 else "❌", "Minst 8 tecken"),
                    ("✅" if any(c.isupper() for c in new_password) else "❌", "En versal (A-Z)"),
                    ("✅" if any(c.islower() for c in new_password) else "❌", "En gemen (a-z)"),
                    ("✅" if any(c.isdigit() for c in new_password) else "❌", "En siffra (0-9)"),
                    ("✅" if any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in new_password) else "➖", "Specialtecken (valfritt)"),
                ]
                
                for icon, text in checks:
                    st.markdown(f"{icon} {text}")
                
                st.markdown("")
                if strength_text == "Svagt":
                    st.markdown(f"**Styrka:** 🔴 {strength_text}")
                elif strength_text == "Medel":
                    st.markdown(f"**Styrka:** 🟡 {strength_text}")
                else:
                    st.markdown(f"**Styrka:** 🟢 {strength_text}")
                st.progress(strength_val)
            else:
                st.caption("Ange ett lösenord för att se kraven.")
        
        st.markdown("")
        
        if st.button("✅ Skapa användare", type="primary", use_container_width=True):
            if not new_password:
                st.markdown('<div class="error-box">❌ Lösenord får inte vara tomt.</div>', unsafe_allow_html=True)
            elif new_password != confirm_password:
                st.markdown('<div class="error-box">❌ Lösenorden matchar inte.</div>', unsafe_allow_html=True)
            else:
                ok, msg = create_user(new_username, new_password, new_role, created_by="admin-tool")
                if ok:
                    st.markdown(f'<div class="success-box">✅ {msg} Secrets.toml uppdaterades automatiskt!</div>', unsafe_allow_html=True)
                    st.balloons()
                    # Nollställ formulär genom att ändra nyckeln
                    st.session_state.form_trigger += 1
                    time.sleep(2.0)
                    st.rerun()
                else:
                    st.markdown(f'<div class="error-box">❌ {msg}</div>', unsafe_allow_html=True)
    
    # ======================
    # TAB 2: Hantera
    # ======================
    with tab_users:
        st.markdown("")
        st.markdown('<div class="section-title">Registrerade användare</div>', unsafe_allow_html=True)
        
        # Ladda om
        users = load_users()
        
        if not users:
            st.markdown("""
            <div class="info-box">
                ℹ️ Inga användare registrerade ännu. Gå till fliken "Lägg till användare" för att skapa den första.
            </div>
            """, unsafe_allow_html=True)
        else:
            for username, info in sorted(users.items()):
                initials = username[0].upper()
                role_label = "🔧 Admin" if info.get("role") == "admin" else "👤 Användare"
                created = info.get("created_at", "Okänt")
                if created != "Okänt":
                    try:
                        dt = datetime.fromisoformat(created)
                        created = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        pass
                
                st.markdown(f"""
                <div class="user-card">
                    <div class="user-info">
                        <div class="user-avatar">{initials}</div>
                        <div>
                            <div class="user-name">{username}</div>
                            <div class="user-role">{role_label}</div>
                        </div>
                    </div>
                    <div class="user-meta">
                        Skapad: {created}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("")
            st.divider()
            
            st.markdown('<div class="section-title">Åtgärder</div>', unsafe_allow_html=True)
            
            col_action1, col_action2 = st.columns(2, gap="medium")
            
            with col_action1:
                st.markdown("**🔄 Återställ lösenord**")
                reset_user = st.selectbox(
                    "Välj användare",
                    options=list(users.keys()),
                    key="reset_user_select"
                )
                
                col_reset_pw, col_reset_gen = st.columns([3, 1])
                with col_reset_pw:
                    new_pw = st.text_input(
                        "Nytt lösenord",
                        type="password",
                        key="reset_new_pw",
                        placeholder="Nytt lösenord..."
                    )
                with col_reset_gen:
                    st.markdown("")
                    if st.button("☀️", key="gen_reset_pw_btn", help="Generera lösenord"):
                        st.session_state.reset_pw_suggestions = generate_multiple_passwords(3)
                
                if st.session_state.get("reset_pw_suggestions"):
                    for pw in st.session_state.reset_pw_suggestions:
                        st.code(pw, language=None)
                
                confirm_pw = st.text_input(
                    "Bekräfta nytt lösenord",
                    type="password",
                    key="reset_confirm_pw",
                    placeholder="Bekräfta..."
                )
                
                if st.button("🔄 Uppdatera lösenord", use_container_width=True):
                    if not new_pw:
                        st.error("Ange ett nytt lösenord.")
                    elif new_pw != confirm_pw:
                        st.error("Lösenorden matchar inte.")
                    else:
                        ok, msg = reset_user_password(reset_user, new_pw)
                        if ok:
                            st.success(f"✅ {msg}")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
            
            with col_action2:
                st.markdown("**🗑️ Ta bort användare**")
                delete_user_sel = st.selectbox(
                    "Välj användare att ta bort",
                    options=list(users.keys()),
                    key="delete_user_select"
                )
                
                st.warning(f"⚠️ Att ta bort **{delete_user_sel}** kan inte ångras!")
                
                confirm_delete = st.text_input(
                    f"Skriv '{delete_user_sel}' för att bekräfta",
                    key="confirm_delete_input",
                    placeholder=f"Skriv {delete_user_sel}..."
                )
                
                if st.button("🗑️ Ta bort", type="secondary", use_container_width=True):
                    if confirm_delete == delete_user_sel:
                        ok, msg = delete_user(delete_user_sel)
                        if ok:
                            st.success(f"✅ {msg}")
                            st.rerun()
                        else:
                            st.error(f"❌ {msg}")
                    else:
                        st.error("Du måste skriva användarnamnet exakt för att bekräfta.")
    
    # ======================
    # TAB 3: Export / Secrets
    # ======================
    with tab_export:
        st.markdown("")
        st.markdown('<div class="section-title">☁️ Synka till Hugging Face</div>', unsafe_allow_html=True)
        
        users = load_users()
        
        if not users:
            st.info("Inga användare att synka. Skapa en användare först!")
        else:
            st.success("☁️ **Automatisk molnsynkning aktiverad:** Du behöver inte längre manuellt kopiera json-koder och klistra in dem på HuggingFace. Alla ändringar synkroniseras nu automatiskt till en säker databas på Hugging Face i bakgrunden! För att tvinga en manuell synkronisering kan du använda knapparna längst nere.")
            
            st.divider()
            st.markdown('<div class="section-title">📄 Lokal Backup & Secrets.toml</div>', unsafe_allow_html=True)
            
            st.markdown("`secrets.toml` **genereras automatiskt** lokalt när du sparar användare precis som innan.")
            
            st.markdown("")
            st.markdown("##### 📋 Aktuell `[users]`-sektion för lokal `secrets.toml`")
            
            snippet = generate_secrets_toml_snippet(users)
            st.code(snippet, language="toml")
            
            st.markdown("")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("##### 💾 Spara ner backup (JSON)")
                users_json_pretty = json.dumps(users, indent=2, ensure_ascii=False)
                st.download_button(
                    label="Ladda ner users.json",
                    data=users_json_pretty,
                    file_name="users_backup.json",
                    mime="application/json",
                    use_container_width=True
                )
            with col_b2:
                st.markdown("##### 🚀 Manuellt tvinga uppladdning")
                if st.button("Ladda upp till molnet", use_container_width=True):
                    with st.spinner("Laddar upp..."):
                        ok, msg = sync_users_to_hf()
                        if ok:
                            st.success(f"✅ {msg}")
                        else:
                            st.error(f"❌ {msg}")
    
    # Footer
    st.markdown("")
    st.divider()
    
    col_footer_left, col_footer_right = st.columns([4, 1])
    with col_footer_right:
        if st.button("🚪 Logga ut", use_container_width=True):
            st.session_state.admin_authenticated = False
            st.rerun()
    
    st.markdown("""
    <div class="admin-footer">
        Solveig Admin (Bootstrap) • GreenPowerSweden
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
