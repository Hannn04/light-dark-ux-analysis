import os
import hashlib
import datetime
import shutil
import requests
import streamlit as st
from streamlit_cookies_controller import CookieController
from textwrap import dedent

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}


def get_cookie_controller():
    if "cookie_controller" not in st.session_state:
        st.session_state["cookie_controller"] = CookieController()
    return st.session_state["cookie_controller"]


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
    keys = list(st.session_state.keys())
    for k in keys:
        if k not in ["cookie_controller", "app_theme"]:
            st.session_state.pop(k, None)
    st.session_state["logged_out"] = True
    st.query_params.clear()
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
    if "app_theme" not in st.session_state:
        q_theme = st.query_params.get("theme", "light")
        st.session_state["app_theme"] = q_theme
    
    theme = st.session_state["app_theme"]
    if st.query_params.get("theme") != theme:
        st.query_params["theme"] = theme
        
    is_dark = (theme == "dark")

    if not st.session_state.get("logged_in") and not st.session_state.get("logged_out"):
        saved_user = controller.get("session_user") if st.query_params.get("force_auth") != "true" else None
        if saved_user and saved_user in load_users():
            st.session_state.update({"logged_in": True, "current_user": saved_user})
    if st.session_state.get("logged_in") and st.query_params.get("force_auth") != "true":
        return True

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    # Define CSS variables based on theme
    if is_dark:
        bg_gradient = "linear-gradient(135deg, #0f172a 0%, #1e293b 100%)"
        card_bg = "#1e293b"
        card_border = "rgba(255, 255, 255, 0.08)"
        toggle_bg = "#111827"
        input_bg = "#111827"
        input_border = "rgba(255, 255, 255, 0.1)"
        input_text = "#f9fafb"
        text_primary = "#f9fafb"
        text_secondary = "#94a3b8"
        text_active = "#818cf8"  # Higher contrast light purple for dark mode active tab
    else:
        bg_gradient = "linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)"
        card_bg = "#ffffff"
        card_border = "#e2e8f0"
        toggle_bg = "#ffffff"
        input_bg = "#f8fafc"
        input_border = "#cbd5e1"
        input_text = "#0f172a"
        text_primary = "#0f172a"
        text_secondary = "#64748b"
        text_active = "#4f46e5"  # Rich purple for light mode active tab

    # Fullscreen CSS injection & Scroll Lock (Premium Design Match)
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

    /* Force Plus Jakarta Sans font globally on absolutely all elements */
    * {{
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {{
        background: {bg_gradient} !important;
        min-height: 100vh !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important; /* Top align to allow scrolling */
        align-items: center !important;
        padding: 0 !important;
        margin: 0 !important;
        width: 100% !important;
    }}
    
    header, footer {{
        display: none !important;
    }}
    
    /* Hide sidebar and sidebar collapse button completely on login screen */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}

    /* Reset margins/paddings that Streamlit calculates for the sidebar */
    [data-testid="stMainViewContainer"] {{
        margin-left: 0px !important;
        padding-left: 0px !important;
        width: 100% !important;
    }}

    [data-testid="stElementContainer"] {{
        margin-bottom: 0px !important;
    }}
    
    /* Center Card styling directly on block-container with top spacing */
    [data-testid="stMain"] .block-container {{
        width: 100% !important;
        max-width: 420px !important;
        margin-top: 60px !important;
        margin-bottom: 60px !important;
        margin-left: auto !important;
        margin-right: auto !important;
        background-color: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 24px !important;
        padding: 40px 36px !important;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, {0.15 if is_dark else 0.05}), 0 10px 10px -5px rgba(0, 0, 0, {0.1 if is_dark else 0.03}) !important;
        box-sizing: border-box !important;
        position: relative !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        align-items: stretch !important; /* Stretch card children */
        min-height: auto !important;
        height: auto !important;
    }}

    /* Reset default st.form inside the login card */
    div[data-testid="stForm"] {{
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
    }}

    /* Theme toggle styling using marker */
    .theme-toggle-marker {{
        display: none !important;
    }}

    /* Style the column wrapper to position the theme toggle absolute in the card top-right */
    div[data-testid="stColumn"]:has(.theme-toggle-marker) {{
        position: absolute !important;
        top: 36px !important;
        right: 36px !important;
        width: auto !important;
        min-width: 0 !important;
        z-index: 999 !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    /* Style the checkbox label as a premium text toggle button */
    div[data-testid="stColumn"]:has(.theme-toggle-marker) div[data-testid="stCheckbox"] label {{
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 8px 16px !important;
        border-radius: 30px !important;
        border: 1px solid {card_border} !important;
        background-color: {toggle_bg} !important;
        cursor: pointer !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-sizing: border-box !important;
        width: auto !important;
        height: auto !important;
    }}
    
    /* Modern Switch Hover style */
    div[data-testid="stColumn"]:has(.theme-toggle-marker) div[data-testid="stCheckbox"] label:hover {{
        border-color: #4f46e5 !important;
        background-color: {toggle_bg} !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.1) !important;
    }}

    /* Hide the checkbox checkmark box (which is the first child of the label) */
    div[data-testid="stColumn"]:has(.theme-toggle-marker) div[data-testid="stCheckbox"] label > :first-child {{
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
    }}

    /* Style the markdown container holding the text */
    div[data-testid="stColumn"]:has(.theme-toggle-marker) div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] {{
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    div[data-testid="stColumn"]:has(.theme-toggle-marker) div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {{
        font-size: 10px !important;
        font-weight: 700 !important;
        text-transform: uppercase !important;
        color: {text_secondary} !important;
        margin: 0 !important;
        line-height: 1 !important;
        letter-spacing: 1px !important;
        white-space: nowrap !important; /* Prevent text wrapping */
    }}

    /* Tab markers and wrapper styling */
    .auth-tab {{
        display: none !important;
    }}

    /* Flat Tab Row Container - Sleek & Minimalist */
    div[data-testid="stHorizontalBlock"]:has(.auth-tab) {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0px !important;
        padding: 0 !important;
        gap: 0px !important;
        margin-bottom: 24px !important;
        border-bottom: 1px solid {card_border} !important;
    }}

    /* Remove column spacing */
    div[data-testid="stHorizontalBlock"]:has(.auth-tab) div[data-testid="stColumn"] {{
        padding: 0 !important;
        margin: 0 !important;
    }}

    /* Base tab button style inside flat row */
    div[data-testid="stHorizontalBlock"]:has(.auth-tab) div[data-testid="stButton"] button {{
        border: none !important;
        box-shadow: none !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        height: 40px !important;
        width: 100% !important;
        transition: all 0.2s ease !important;
        margin: 0 !important;
        text-transform: none !important;
        letter-spacing: 0.5px !important;
        background-color: transparent !important;
        border-radius: 0px !important;
        border-bottom: 2px solid transparent !important;
    }}

    /* Active Tab Button Style - flat bottom line */
    div[data-testid="stColumn"]:has(.active-tab) div[data-testid="stButton"] button {{
        color: {text_active} !important;
        font-weight: 700 !important;
        border-bottom: 2px solid {text_active} !important;
    }}

    /* Inactive Tab Button Style - transparent line */
    div[data-testid="stColumn"]:has(.inactive-tab) div[data-testid="stButton"] button {{
        color: {text_secondary} !important;
        border-bottom: 2px solid transparent !important;
    }}
    div[data-testid="stColumn"]:has(.inactive-tab) div[data-testid="stButton"] button:hover {{
        color: {text_primary} !important;
        border-bottom: 2px solid {card_border} !important;
    }}

    /* Form wrappers */
    div[data-testid="stForm"] div.element-container,
    div[data-testid="stForm"] div[data-testid="element-container"],
    div[data-testid="stForm"] div[data-testid="stVerticalBlock"],
    div[data-testid="stForm"] div[data-testid="stVerticalBlock"] > div {{
        margin-bottom: 0px !important;
        overflow: visible !important;
        height: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
        box-sizing: border-box !important;
    }}
    
    div[data-testid="stForm"] div.stTextInput,
    div[data-testid="stForm"] div.stTextInput > div,
    div[data-testid="stForm"] div[data-testid*="Input"],
    div[data-testid="stForm"] div[data-testid*="Input"] > div,
    div[data-testid="stForm"] [data-testid*="password"],
    div[data-testid="stForm"] [data-testid*="Password"],
    div[data-testid="stForm"] [data-testid*="password"] > div,
    div[data-testid="stForm"] [data-testid*="Password"] > div,
    div[data-testid="stForm"] [data-testid*="text"],
    div[data-testid="stForm"] [data-testid*="Text"],
    div[data-testid="stForm"] [data-baseweb="input"],
    div[data-testid="stForm"] [data-baseweb="input"] > div,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"],
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        overflow: visible !important;
        height: auto !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* Force height on immediate widget containers */
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"],
    div[data-testid="stForm"] [data-baseweb="input"] {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        overflow: visible !important;
        height: 50px !important;
        min-height: 50px !important;
        max-height: 50px !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* Style actual input containers */
    div[data-testid="stForm"] [data-baseweb="input"] > div,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div,
    div[data-testid="stForm"] div.stTextInput > div > div,
    div[data-testid="stForm"] div[data-testid*="Input"] > div > div,
    div[data-testid="stForm"] [data-testid*="password"] > div > div,
    div[data-testid="stForm"] [data-testid*="Password"] > div > div {{
        background-color: {input_bg} !important;
        border-radius: 8px !important;
        border: 1px solid {input_border} !important;
        height: 50px !important;
        min-height: 50px !important;
        max-height: 50px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: none !important;
        display: flex !important;
        align-items: center !important;
        overflow: visible !important;
        box-sizing: border-box !important;
        width: 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
    }}

    /* Modern input hover & focus ring */
    div[data-testid="stForm"] [data-baseweb="input"] > div:hover,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div:hover {{
        border-color: #a5b4fc !important;
    }}
    div[data-testid="stForm"] [data-baseweb="input"] > div:focus-within,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div:focus-within {{
        border-color: #4f46e5 !important;
        box-shadow: 0 0 0 4px rgba(79, 70, 229, 0.15) !important;
    }}

    /* Make all nested child elements inside the input wrapper transparent, except the input itself */
    div[data-testid="stForm"] [data-baseweb="input"] > div :not(input),
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div :not(input),
    div[data-testid="stForm"] div.stTextInput > div > div :not(input),
    div[data-testid="stForm"] div[data-testid*="Input"] > div > div :not(input) {{
        background-color: transparent !important;
        background: transparent !important;
        box-shadow: none !important;
    }}

    /* Plain style actual input elements inside wrappers */
    div[data-testid="stForm"] input[type="text"],
    div[data-testid="stForm"] input[type="password"] {{
        background-image: none !important;
        padding-left: 16px !important;
        padding-right: 16px !important;
        border: none !important;
        height: 100% !important;
        font-size: 14px !important;
        color: {input_text} !important;
        background-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }}

    /* Visibility show/hide password buttons color */
    div[data-testid="stForm"] div.stTextInput button,
    div[data-testid="stForm"] div[data-testid*="Input"] button,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] button,
    div[data-testid="stForm"] [data-baseweb="input"] button,
    div[data-testid="stForm"] div.stTextInput button svg,
    div[data-testid="stForm"] div[data-testid*="Input"] button svg,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] button svg,
    div[data-testid="stForm"] [data-baseweb="input"] button svg {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: {text_secondary} !important;
        fill: currentColor !important;
    }}
    
    div[data-testid="stForm"] input::placeholder {{
        color: #cbd5e1 !important;
    }}

    /* Style the normal form checkboxes (e.g. remember_me) */
    div[data-testid="stForm"] div[data-testid="stCheckbox"] label {{
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        width: auto !important;
        height: auto !important;
        border: none !important;
        background-color: transparent !important;
        padding: 4px 0px !important;
        margin: 16px 0px !important;
        cursor: pointer !important;
    }}
    div[data-testid="stForm"] div[data-testid="stCheckbox"] label > :not([data-testid="stMarkdownContainer"]) {{
        display: flex !important;
        opacity: 1 !important;
        visibility: visible !important;
    }}
    div[data-testid="stForm"] div[data-testid="stCheckbox"] [data-testid="stMarkdownContainer"] p {{
        font-size: 10px !important;
        font-weight: 700 !important;
        letter-spacing: 0.8px !important;
        text-transform: uppercase !important;
        color: {text_secondary} !important;
        transition: color 0.2s ease !important;
    }}
    
    /* Micro-animation hover checkbox text */
    div[data-testid="stForm"] div[data-testid="stCheckbox"] label:hover [data-testid="stMarkdownContainer"] p {{
        color: {text_primary} !important;
    }}
    
    /* Submit button - Solid Purple Background with Modern Hover Translation & Shadow */
    div[data-testid="stFormSubmitButton"] button {{
        background-color: #4f46e5 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        padding: 0px 24px !important;
        height: 50px !important;
        font-size: 15px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        width: 100% !important;
        box-shadow: 0 8px 16px -4px rgba(79, 70, 229, 0.3) !important;
    }}
    div[data-testid="stFormSubmitButton"] button:hover {{
        background-color: #4338ca !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 10px 20px -2px rgba(79, 70, 229, 0.35) !important;
    }}
    div[data-testid="stFormSubmitButton"] button:active {{
        transform: translateY(1px) !important;
        box-shadow: 0 4px 8px -2px rgba(79, 70, 229, 0.3) !important;
    }}

    /* Responsive adjustments */
    @media (max-width: 480px) {{
        [data-testid="stMain"] .block-container {{
            padding: 24px 20px !important;
            border-radius: 16px !important;
            margin-top: 20px !important;
            margin-bottom: 20px !important;
        }}
        div[data-testid="stColumn"]:has(.theme-toggle-marker) {{
            top: 24px !important;
            right: 20px !important;
        }}
    }}

    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    # Main Card Container
    with st.container():
        st.markdown('<div class="login-card-marker"></div>', unsafe_allow_html=True)
        
        # Row 1: Logo & Theme Toggle
        col_logo, col_toggle = st.columns([2, 1])
        with col_logo:
            st.markdown(
                f'<div style="display: flex; align-items: center; padding-top: 12px;">'
                f'<span style="font-size: 14px; font-weight: 800; color: #4f46e5; letter-spacing: 1.5px; text-transform: uppercase;">UX</span>'
                f'<span style="font-size: 14px; font-weight: 400; color: {text_secondary}; letter-spacing: 1.5px; text-transform: uppercase; margin-left: 4px;">Analytics</span>'
                f'</div>',
                unsafe_allow_html=True
            )
        with col_toggle:
            st.markdown('<div class="theme-toggle-marker"></div>', unsafe_allow_html=True)
            is_dark_toggle = st.checkbox(
                label="LIGHT MODE" if is_dark else "DARK MODE",
                value=is_dark,
                key="theme_toggle_checkbox"
            )
            if is_dark_toggle != is_dark:
                st.session_state["app_theme"] = "dark" if is_dark_toggle else "light"
                st.query_params["theme"] = "dark" if is_dark_toggle else "light"
                st.rerun()

        # Spacer
        st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)

        # Row 2: Welcome Text - Explicitly stating the dashboard context
        if st.session_state["auth_mode"] == "login":
            st.markdown(
                f'<div style="margin-bottom: 28px;">'
                f'<div style="font-size: 24px; font-weight: 700; color: {text_primary}; letter-spacing: -0.5px; margin-bottom: 6px;">Selamat Datang</div>'
                f'<div style="font-size: 12px; font-weight: 600; color: #4f46e5; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 12px;">Penelitian Light Mode vs Dark Mode</div>'
                f'<div style="font-size: 13px; color: {text_secondary}; line-height: 1.5; font-weight: 400;">Silakan masuk untuk mengakses hasil analisis data dan perbandingan pengalaman pengguna (UX).</div>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'<div style="margin-bottom: 28px;">'
                f'<div style="font-size: 24px; font-weight: 700; color: {text_primary}; letter-spacing: -0.5px; margin-bottom: 6px;">Daftar Akun</div>'
                f'<div style="font-size: 12px; font-weight: 600; color: #4f46e5; letter-spacing: 0.5px; text-transform: uppercase; margin-bottom: 12px;">Penelitian Light Mode vs Dark Mode</div>'
                f'<div style="font-size: 13px; color: {text_secondary}; line-height: 1.5; font-weight: 400;">Lengkapi formulir untuk membuat akun baru dan mengakses dashboard analitik.</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Row 3: Tabs "Masuk" & "Daftar"
        is_login = (st.session_state["auth_mode"] == "login")
        col_tab1, col_tab2 = st.columns([1, 1], gap="small")
        with col_tab1:
            st.markdown(f'<div class="auth-tab {"active-tab" if is_login else "inactive-tab"}"></div>', unsafe_allow_html=True)
            if st.button("Masuk", key="tab_login_btn", use_container_width=True):
                st.session_state["auth_mode"] = "login"
                st.rerun()
        with col_tab2:
            st.markdown(f'<div class="auth-tab {"inactive-tab" if is_login else "active-tab"}"></div>', unsafe_allow_html=True)
            if st.button("Daftar", key="tab_register_btn", use_container_width=True):
                st.session_state["auth_mode"] = "register"
                st.rerun()

        # Row 4: Forms
        if st.session_state["auth_mode"] == "login":
            with st.form("login_form"):
                st.markdown(f'<div style="font-size: 11px; font-weight: 600; color: {text_secondary}; letter-spacing: 0.5px; margin-bottom: 6px; text-transform: uppercase;">Username</div>', unsafe_allow_html=True)
                user = st.text_input("Username", placeholder="Masukkan username", label_visibility="collapsed").strip().lower()
                st.markdown(f'<div style="font-size: 11px; font-weight: 600; color: {text_secondary}; letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 6px; text-transform: uppercase;">Password</div>', unsafe_allow_html=True)
                pw = st.text_input("Password", type="password", placeholder="Masukkan password", label_visibility="collapsed")
                remember_me = st.checkbox("INGAT SAYA", value=True)
                if st.form_submit_button("Masuk", use_container_width=True):
                    ok, msg = login_user(user, pw)
                    if ok:
                        st.session_state.update({"logged_in": True, "current_user": user})
                        st.session_state.pop("logged_out", None)
                        if remember_me:
                            controller.set("session_user", user)
                        else:
                            controller.remove("session_user")
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            with st.form("reg_form"):
                st.markdown(f'<div style="font-size: 11px; font-weight: 600; color: {text_secondary}; letter-spacing: 0.5px; margin-bottom: 6px; text-transform: uppercase;">Username</div>', unsafe_allow_html=True)
                u = st.text_input("Username", placeholder="Pilih username", label_visibility="collapsed").strip().lower()
                st.markdown(f'<div style="font-size: 11px; font-weight: 600; color: {text_secondary}; letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 6px; text-transform: uppercase;">Password</div>', unsafe_allow_html=True)
                p = st.text_input("Password", type="password", placeholder="Minimal 6 karakter", label_visibility="collapsed")
                st.markdown(f'<div style="font-size: 11px; font-weight: 600; color: {text_secondary}; letter-spacing: 0.5px; margin-top: 16px; margin-bottom: 6px; text-transform: uppercase;">Konfirmasi Password</div>', unsafe_allow_html=True)
                cp = st.text_input("Konfirmasi Password", type="password", placeholder="Ulangi password", label_visibility="collapsed")
                if st.form_submit_button("Daftar", use_container_width=True):
                    if p != cp:
                        st.error("Password tidak cocok")
                    else:
                        ok, msg = register_user(u, p)
                        if ok:
                            st.success(msg)
                            st.session_state["auth_mode"] = "login"
                            st.rerun()
                        else:
                            st.error(msg)

    st.markdown(
        f'<div style="text-align: center; margin-top: 32px; font-size: 11px; color: {text_secondary};">'
        f'Universitas Islam Indonesia'
        f'</div>',
        unsafe_allow_html=True
    )

    return False
