import os
import hashlib
import datetime
import shutil
import requests
import streamlit as st
from streamlit_cookies_controller import CookieController

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}


def get_cookie_controller():
    return CookieController()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def load_users() -> dict:
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/users?select=*",
            headers=HEADERS
        )
        return {
            row["username"]: {"password": row["password"], "created_at": row["created_at"]}
            for row in res.json()
        }
    except Exception:
        return {}


def save_user(username: str, password_hash: str):
    requests.post(
        f"{SUPABASE_URL}/rest/v1/users",
        headers={**HEADERS, "Prefer": "resolution=merge-duplicates"},
        json={
            "username": username,
            "password": password_hash,
            "created_at": str(datetime.datetime.now())
        }
    )


def delete_user_from_db(username: str):
    requests.delete(
        f"{SUPABASE_URL}/rest/v1/users?username=eq.{username}",
        headers=HEADERS
    )


def register_user(username: str, password: str):
    users = load_users()
    username = username.strip().lower()
    if not username:
        return False, "Username tidak boleh kosong."
    if len(username) < 3:
        return False, "Username minimal 3 karakter."
    if len(password) < 6:
        return False, "Password minimal 6 karakter."
    if username in users:
        return False, "Username sudah terdaftar. Pilih username lain."
    save_user(username, hash_password(password))
    return True, "Akun berhasil dibuat! Silakan login."


def login_user(username: str, password: str):
    users = load_users()
    username = username.strip().lower()
    if username not in users:
        return False, "Username tidak ditemukan."
    if users[username]["password"] != hash_password(password):
        return False, "Password salah."
    return True, "Login berhasil!"


def change_password(username: str, old_password: str, new_password: str):
    users = load_users()
    username = username.strip().lower()
    if username not in users:
        return False, "Akun tidak ditemukan."
    if users[username]["password"] != hash_password(old_password):
        return False, "Password lama salah."
    if len(new_password) < 6:
        return False, "Password baru minimal 6 karakter."
    save_user(username, hash_password(new_password))
    return True, "Password berhasil diubah!"


def delete_account(username: str, password: str):
    users = load_users()
    username = username.strip().lower()
    if username not in users:
        return False, "Akun tidak ditemukan."
    if users[username]["password"] != hash_password(password):
        return False, "Password salah. Akun tidak dihapus."
    delete_user_from_db(username)
    return True, "Akun berhasil dihapus."


def logout():
    controller = get_cookie_controller()
    controller.remove("session_user")
    for key in ["logged_in", "current_user", "last_user", "app_list", "confirm_reset"]:
        st.session_state.pop(key, None)
    st.rerun()


def render_settings_page():
    current_user = st.session_state.get("current_user", "")

    st.markdown(f"""
    <div style="font-size:24px;font-weight:700;color:#1e293b;margin-bottom:4px;">
        Pengaturan Akun
    </div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:24px;">
        Login sebagai <b style="color:#6366f1;">{current_user}</b>
    </div>
    """, unsafe_allow_html=True)

    tab_pw, tab_del = st.tabs(["Ganti Password", "Hapus Akun"])

    with tab_pw:
        st.markdown("#### Ganti Password")
        with st.form("form_change_password"):
            old_pw = st.text_input("Password Lama", type="password", placeholder="Masukkan password lama")
            new_pw = st.text_input("Password Baru", type="password", placeholder="Minimal 6 karakter")
            confirm_pw = st.text_input("Konfirmasi Password Baru", type="password", placeholder="Ulangi password baru")
            submitted = st.form_submit_button("Simpan Password Baru", use_container_width=True, type="primary")
        if submitted:
            if not old_pw or not new_pw or not confirm_pw:
                st.error("Semua field wajib diisi.")
            elif new_pw != confirm_pw:
                st.error("Password baru dan konfirmasi tidak cocok.")
            else:
                ok, msg = change_password(current_user, old_pw, new_pw)
                st.success(msg) if ok else st.error(msg)

    with tab_del:
        st.markdown("#### Hapus Akun")
        st.warning("Tindakan ini **permanen** dan tidak bisa dibatalkan.")
        with st.form("form_delete_account"):
            confirm_pw_del = st.text_input("Konfirmasi Password", type="password", placeholder="Masukkan password untuk konfirmasi")
            hapus = st.form_submit_button("Hapus Akun Saya", use_container_width=True, type="primary")
        if hapus:
            if not confirm_pw_del:
                st.error("Password wajib diisi.")
            else:
                ok, msg = delete_account(current_user, confirm_pw_del)
                if ok:
                    st.success(msg)
                    controller = get_cookie_controller()
                    controller.remove("session_user")
                    for key in ["logged_in", "current_user", "last_user", "app_list", "confirm_reset"]:
                        st.session_state.pop(key, None)
                    st.rerun()
                else:
                    st.error(msg)


def render_auth_page():
    controller = get_cookie_controller()

    # ── Inisialisasi tema (diambil dari session_state) ──────────────────────
    if "app_theme" not in st.session_state:
        st.session_state["app_theme"] = "light"

    theme = st.session_state["app_theme"]
    is_dark = (theme == "dark")

    if not st.session_state.get("logged_in"):
        try:
            saved_user = controller.get("session_user")
            if saved_user:
                users = load_users()
                if saved_user in users:
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = saved_user
                    st.session_state["show_logout_confirm"] = False
        except Exception:
            pass

    if st.session_state.get("logged_in"):
        return True

    # ── Color Scheme ────────────────────────────────────────────────────────
    if is_dark:
        page_bg     = "#0f172a"
        card_bg     = "#1e293b"
        card_border = "rgba(99,102,241,0.15)"
        card_shadow = "0 20px 60px rgba(0,0,0,0.5)"
        text_main   = "#f1f5f9"
        text_soft   = "#64748b"
        input_bg    = "#0f172a"
        input_bdr   = "#334155"
        input_focus = "rgba(99,102,241,0.3)"
        toggle_bg   = "rgba(167,139,250,0.1)"
        toggle_clr  = "#a78bfa"
        toggle_bdr  = "rgba(167,139,250,0.3)"
        sep_clr     = "rgba(255,255,255,0.05)"
        label_clr   = "#64748b"
        placeholder = "#475569"
        alert_fix   = '[data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #f1f5f9 !important; }'
    else:
        page_bg     = "#f8fafc"
        card_bg     = "#ffffff"
        card_border = "rgba(0,0,0,0.06)"
        card_shadow = "0 4px 6px -1px rgba(0,0,0,0.05), 0 20px 50px rgba(99,102,241,0.08)"
        text_main   = "#0f172a"
        text_soft   = "#94a3b8"
        input_bg    = "#f8fafc"
        input_bdr   = "#e2e8f0"
        input_focus = "rgba(99,102,241,0.15)"
        toggle_bg   = "rgba(99,102,241,0.06)"
        toggle_clr  = "#6366f1"
        toggle_bdr  = "rgba(99,102,241,0.2)"
        sep_clr     = "rgba(0,0,0,0.06)"
        label_clr   = "#94a3b8"
        placeholder = "#cbd5e1"
        alert_fix   = ""

    dark_input_override = f"""
        [data-baseweb="input"] > div,
        [data-baseweb="textarea"] > div {{
            background-color: {input_bg} !important;
            color: {text_main} !important;
            border-color: {input_bdr} !important;
        }}
        input[type="text"], input[type="password"] {{
            background-color: transparent !important;
            color: {text_main} !important;
            border: none !important;
        }}
        input::placeholder {{ color: {placeholder} !important; }}
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] span {{ color: {text_main} !important; }}
        .stApp p, .stApp label,
        [data-testid="stMarkdownContainer"] p,
        [data-testid="stWidgetLabel"] {{ color: {text_main} !important; }}
        {alert_fix}
    """ if is_dark else f"""
        input::placeholder {{ color: {placeholder} !important; }}
        [data-testid="stCheckbox"] label {{ color: {text_soft} !important; }}
    """

    # ── Toggle button variables ──────────────────────────────────────────────
    if is_dark:
        toggle_btn_bg     = "#1e293b"
        toggle_btn_border = "#334155"
        toggle_btn_color  = "#60a5fa"
        toggle_btn_hover_bg = "#0f172a"
        toggle_btn_hover_border = "#475569"
    else:
        toggle_btn_bg     = "#ffffff"
        toggle_btn_border = "#d1d5db"
        toggle_btn_color  = "#0c66e4"
        toggle_btn_hover_bg = "#f8fafc"
        toggle_btn_hover_border = "#9ca3af"

    accent = "rgba(99,102,241,0.06)" if is_dark else "rgba(99,102,241,0.08)"

    # ── Merged Layout: CSS + Accent Blobs + Brand Header ─────────────────────
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    /* Hide Streamlit chrome */
    header[data-testid="stHeader"]  {{ display: none !important; }}
    [data-testid="stToolbar"]       {{ display: none !important; }}
    [data-testid="stDecoration"]    {{ display: none !important; }}
    footer {{ display: none !important; }}
    #MainMenu {{ display: none !important; }}

    * {{ font-family: 'Inter', -apple-system, sans-serif !important; }}

    /* Clean layout and scrolling behavior */
    html, body {{
        overflow-y: auto !important;
        min-height: 100vh !important;
    }}

    /* Page background */
    .stApp {{
        background-color: {page_bg} !important;
        min-height: 100vh !important;
        overflow-y: auto !important;
    }}
    section.main, section.main > div {{
        background: transparent !important;
        overflow: visible !important;
    }}
    [data-testid="stMainBlockContainer"] {{
        overflow: visible !important;
    }}

    /* Login card */
    .block-container {{
        max-width: 400px !important;
        margin: 0 auto !important;
        margin-top: 4vh !important;
        margin-bottom: 4vh !important;
        padding: 24px 28px 28px 28px !important;
        background: {card_bg} !important;
        border-radius: 18px !important;
        box-shadow: {card_shadow} !important;
        border: 1px solid {card_border} !important;
    }}

    /* Collapse Streamlit element vertical gaps */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlock"] > div {{
        gap: 0 !important;
        margin-bottom: 0 !important;
    }}

    /* Remove inner form card */
    div[data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        border-radius: 0 !important;
    }}
    [data-testid="stForm"] {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
    }}

    /* Inputs */
    [data-baseweb="input"] > div {{
        background: {input_bg} !important;
        border: 1px solid {input_bdr} !important;
        border-radius: 10px !important;
        transition: border-color 0.15s, box-shadow 0.15s !important;
        outline: none !important;
    }}
    [data-baseweb="input"] > div:focus-within {{
        border-color: #6366f1 !important;
        box-shadow: none !important;
        outline: none !important;
    }}
    [data-baseweb="input"] input {{
        background: transparent !important;
        color: {text_main} !important;
        font-size: 14px !important;
        font-weight: 400 !important;
        padding: 9px 12px !important;
        border: none !important;
        outline: none !important;
        box-shadow: none !important;
    }}
    [data-baseweb="input"] > div * {{
        background-color: transparent !important;
    }}
    [data-baseweb="input"] button {{
        border: none !important;
        color: inherit !important;
    }}
    input:focus, input:focus-visible {{
        outline: none !important;
        box-shadow: none !important;
    }}
    /* Hide 'Press Enter to submit' hint */
    [data-testid="InputInstructions"] {{ display: none !important; }}

    /* Labels */
    [data-testid="stWidgetLabel"] p,
    [data-testid="stWidgetLabel"] span,
    label {{
        color: {label_clr} !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.8px !important;
    }}

    /* Overrides for checkbox labels to prevent uppercase and make them look clean */
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] span,
    [data-testid="stCheckbox"] p {{
        text-transform: none !important;
        letter-spacing: normal !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        color: {text_main} !important;
    }}

    /* Tabs */
    [data-baseweb="tab-list"] {{
        background: transparent !important;
        border-bottom: 1px solid {sep_clr} !important;
        margin-bottom: 6px !important;
        margin-top: 0px !important;
    }}
    [data-baseweb="tab"] {{
        color: {text_soft} !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        padding: 6px 0 !important;
        margin-right: 18px !important;
        background: transparent !important;
        transition: color 0.15s !important;
    }}
    [aria-selected="true"][data-baseweb="tab"] {{
        color: {text_main} !important;
        border-bottom: 2px solid #6366f1 !important;
        margin-bottom: -1px !important;
    }}
    [data-baseweb="tab-panel"] {{ background: transparent !important; padding: 0 !important; }}

    /* Primary button */
    [data-testid="stBaseButton-primary"] {{
        background: #6366f1 !important;
        border: none !important;
        border-radius: 10px !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        letter-spacing: 0.2px !important;
        box-shadow: 0 1px 3px rgba(99,102,241,0.3) !important;
        transition: all 0.15s ease !important;
        color: white !important;
        margin-top: 4px !important;
    }}
    [data-testid="stBaseButton-primary"]:hover {{
        background: #4f46e5 !important;
        box-shadow: 0 4px 12px rgba(99,102,241,0.4) !important;
        transform: translateY(-1px) !important;
    }}

    /* Toggle — premium rounded button */
    [data-testid="stBaseButton-secondary"] {{
        background-color: {toggle_btn_bg} !important;
        border: 1px solid {toggle_btn_border} !important;
        border-radius: 10px !important;
        color: {toggle_btn_color} !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        padding: 4px 12px !important;
        width: 100% !important;
        height: 38px !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05) !important;
        transition: all 0.15s ease !important;
        cursor: pointer !important;
    }}
    [data-testid="stBaseButton-secondary"]::before {{
        display: none !important;
    }}
    [data-testid="stBaseButton-secondary"]:hover {{
        background-color: {toggle_btn_hover_bg} !important;
        border-color: {toggle_btn_hover_border} !important;
        transform: translateY(-1px) !important;
    }}

    /* Alerts */
    .stAlert, [data-testid="stAlert"] {{ border-radius: 10px !important; font-size: 13px !important; }}

    /* Column padding */
    div[data-testid="column"] {{ padding: 0 2px !important; }}

    /* Collapse horizontal block gap and vertical spacing */
    [data-testid="stHorizontalBlock"] {{
        gap: 0 !important;
        margin-top: 4px !important;
        margin-bottom: 4px !important;
    }}

    /* Scrollbar */
    ::-webkit-scrollbar {{ width: 4px; }}
    ::-webkit-scrollbar-thumb {{ background: rgba(99,102,241,0.25); border-radius: 4px; }}

    {dark_input_override}
    </style>

    <!-- Subtle accent dot decoration -->
    <div style="position:fixed;top:0;left:0;width:100vw;height:100vh;pointer-events:none;z-index:0;overflow:hidden;">
        <div style="position:absolute;width:600px;height:600px;background:radial-gradient(circle,{accent} 0%,transparent 70%);top:-200px;right:-200px;"></div>
        <div style="position:absolute;width:500px;height:500px;background:radial-gradient(circle,{accent} 0%,transparent 70%);bottom:-200px;left:-200px;"></div>
    </div>

    <!-- Brand + Heading -->
    <div style="margin-bottom:12px; margin-top:-8px;">
        <span style="font-size:10px; font-weight:700; color:#6366f1;
                     text-transform:uppercase; letter-spacing:1.0px;">
            UX Analytics
        </span>
        <h1 style="font-size:18px; font-weight:700; color:{text_main};
                   margin:4px 0 2px 0; letter-spacing:-0.3px; line-height:1.2;">
            Selamat datang
        </h1>
        <p style="font-size:11px; color:{text_soft}; margin:0; line-height:1.3;">
            Masuk untuk melanjutkan ke dashboard penelitian.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── Tabs + Form ─────────────────────────────────────────────────────────
    tab_login, tab_register = st.tabs(["Masuk", "Daftar"])

    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            username = st.text_input("Username", placeholder="username Anda")
            password = st.text_input("Password", type="password", placeholder="password")
            remember_me = st.checkbox("Ingat saya selama 24 jam")
            submitted = st.form_submit_button(
                "Masuk",
                use_container_width=True, type="primary"
            )
        if submitted:
            if not username or not password:
                st.error("Username dan password wajib diisi.")
            else:
                ok, msg = login_user(username, password)
                if ok:
                    user = username.strip().lower()
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = user
                    st.session_state["show_logout_confirm"] = False
                    if remember_me:
                        controller.set("session_user", user, max_age=24 * 60 * 60)
                    else:
                        controller.set("session_user", user)
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

    with tab_register:
        with st.form("form_register", clear_on_submit=True):
            new_username = st.text_input("Username", placeholder="minimal 3 karakter", key="reg_user")
            new_password = st.text_input("Password", type="password",
                                         placeholder="minimal 6 karakter", key="reg_pass")
            confirm_password = st.text_input("Konfirmasi Password", type="password",
                                             placeholder="ulangi password", key="reg_confirm")
            reg_submitted = st.form_submit_button(
                "Buat Akun",
                use_container_width=True, type="primary"
            )
        if reg_submitted:
            if not new_username or not new_password or not confirm_password:
                st.error("Semua field wajib diisi.")
            elif new_password != confirm_password:
                st.error("Password dan konfirmasi password tidak cocok.")
            else:
                ok, msg = register_user(new_username, new_password)
                st.success(msg) if ok else st.error(msg)

    # ── Footer + Toggle ─────────────────────────────────────────────────────────
    mode_label = "Gelap" if is_dark else "Terang"
    st.markdown(f"""
    <div style="margin-top:8px; padding-top:6px; border-top:1px solid {sep_clr}; text-align: center; width: 100%;">
        <p style="font-size:10px; color:{text_soft}; margin:0 0 2px 0; font-weight:600; text-transform:uppercase; letter-spacing:0.8px;">
            Ganti Tampilan
        </p>
        <p style="font-size:10px; color:{text_soft}; margin:0 0 6px 0;">
            Tampilan aktif saat ini: <strong style="color:{text_main};">{mode_label}</strong>
        </p>
    </div>
    """, unsafe_allow_html=True)

    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        btn_label = "☀️ Light Mode" if is_dark else "🌙 Dark Mode"
        if st.button(btn_label, key="login_theme_toggle", use_container_width=True,
                     help="Klik untuk ganti mode tampilan"):
            st.session_state["app_theme"] = "light" if is_dark else "dark"
            st.rerun()

    st.markdown(f"""
    <div style="text-align: center; margin-top: 16px;">
        <p style="font-size:10px; color:{text_soft}; margin:0; opacity:0.6; font-weight:500;">
            Universitas Islam Indonesia
        </p>
    </div>
    """, unsafe_allow_html=True)

    return False