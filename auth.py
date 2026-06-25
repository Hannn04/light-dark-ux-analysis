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
    if "app_theme" not in st.session_state:
        q_theme = st.query_params.get("theme", "light")
        st.session_state["app_theme"] = q_theme
    
    theme = st.session_state["app_theme"]
    if st.query_params.get("theme") != theme:
        st.query_params["theme"] = theme
        
    is_dark = (theme == "dark")

    if not st.session_state.get("logged_in"):
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
        btn_border = "rgba(255, 255, 255, 0.15)"
        input_bg = "#111827"
        input_border = "rgba(255, 255, 255, 0.1)"
        input_text = "#f9fafb"
        text_primary = "#f9fafb"
        text_secondary = "#94a3b8"
        logo_gradient = "linear-gradient(135deg, #3b82f6 0%, #60a5fa 100%)"
        text_title_color = "#f9fafb"
        toggle_bg = "#111827"
        toggle_border = "rgba(255, 255, 255, 0.1)"
    else:
        bg_gradient = "linear-gradient(135deg, #f8fafc 0%, #eff6ff 100%)"
        card_bg = "#ffffff"
        card_border = "rgba(0, 0, 0, 0.03)"
        btn_border = "rgba(0, 0, 0, 0.08)"
        input_bg = "#ffffff"
        input_border = "#cbd5e1"
        input_text = "#0f172a"
        text_primary = "#0f172a"
        text_secondary = "#64748b"
        logo_gradient = "linear-gradient(135deg, #1d4ed8 0%, #3b82f6 100%)"
        text_title_color = "#0f172a"
        toggle_bg = "#ffffff"
        toggle_border = "#cbd5e1"

    # Fullscreen CSS injection & Scroll Lock (Premium Design Match)
    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Force Inter font globally on absolutely all elements */
    * {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }}

    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main, section.main > div {{
        background: {bg_gradient} !important;
        overflow-y: auto !important;
        min-height: 100vh !important;
        padding: 0 !important;
        margin: 0 !important;
    }}
    
    header[data-testid="stHeader"] {{
        display: none !important;
    }}
    footer {{
        display: none !important;
    }}
    
    [data-testid="stElementContainer"] {{
        margin-bottom: 0px !important;
    }}
    
    .main .block-container {{
        max-width: 1100px !important;
        padding: 1.5rem 2rem !important;
        margin: auto !important;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 100vh !important;
        background: transparent !important;
        box-sizing: border-box !important;
    }}
    
    div[data-testid="stHorizontalBlock"] {{
        align-items: center !important;
        gap: 3rem !important;
    }}

    /* Force the nested sub-columns row under the card to never stack vertically */
    div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] {{
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        justify-content: space-between !important;
        align-items: center !important;
        gap: 12px !important;
        margin-top: 12px !important;
        width: 100% !important;
    }}

    div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] > div {{
        width: auto !important;
        min-width: 0 !important;
        flex: 1 1 auto !important;
    }}
    
    /* Compact White Card styling */
    div[data-testid="stForm"] {{
        background-color: {card_bg} !important;
        border: 1px solid {card_border} !important;
        border-radius: 32px !important;
        padding: 32px 40px !important;
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, {0.2 if is_dark else 0.03}) !important;
        margin-bottom: 0px !important;
        overflow: visible !important;
    }}
    
    div[data-testid="stForm"] div.element-container,
    div[data-testid="stForm"] div[data-testid="element-container"],
    div[data-testid="stForm"] div[data-testid="stVerticalBlock"],
    div[data-testid="stForm"] div[data-testid="stVerticalBlock"] > div {{
        margin-bottom: 0px !important;
        overflow: visible !important;
        height: auto !important;
    }}
    
    div[data-testid="stForm"] div.stTextInput,
    div[data-testid="stForm"] div.stTextInput > div,
    div[data-testid="stForm"] div[data-testid*="Input"],
    div[data-testid="stForm"] div[data-testid*="Input"] > div {{
        background-color: transparent !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        overflow: visible !important;
        height: auto !important;
    }}

    /* Force height on immediate widget containers to match the 50px input container */
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
    }}

    /* Style actual input containers to avoid dark mode white patches - supporting all Streamlit input types and widget links */
    div[data-testid="stForm"] [data-baseweb="input"] > div,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div,
    div[data-testid="stForm"] div.stTextInput > div > div,
    div[data-testid="stForm"] div[data-testid*="Input"] > div > div {{
        background-color: {input_bg} !important;
        border-radius: 14px !important;
        border: 1px solid {input_border} !important;
        height: 50px !important;
        min-height: 50px !important;
        max-height: 50px !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
        display: flex !important;
        align-items: center !important;
        overflow: visible !important;
        box-sizing: border-box !important;
    }}

    div[data-testid="stForm"] [data-baseweb="input"] > div:focus-within,
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div:focus-within,
    div[data-testid="stForm"] div.stTextInput > div > div:focus-within,
    div[data-testid="stForm"] div[data-testid*="Input"] > div > div:focus-within {{
        border-color: #1d4ed8 !important;
        box-shadow: 0 0 0 2px rgba(29, 78, 216, 0.1) !important;
    }}

    /* Make all nested child elements inside the input wrapper completely transparent to avoid white patches, except the input itself */
    div[data-testid="stForm"] [data-baseweb="input"] > div :not(input),
    div[data-testid="stForm"] [data-testid="stInputWidgetLink"] > div :not(input),
    div[data-testid="stForm"] div.stTextInput > div > div :not(input),
    div[data-testid="stForm"] div[data-testid*="Input"] > div > div :not(input) {{
        background-color: transparent !important;
        background: transparent !important;
        box-shadow: none !important;
    }}

    /* Style actual input elements inside wrappers */
    div[data-testid="stForm"] input[type="text"] {{
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23cbd5e1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'/><circle cx='12' cy='7' r='4'/></svg>") !important;
        background-repeat: no-repeat !important;
        background-position: 16px center !important;
        background-size: 18px !important;
        padding-left: 46px !important;
        border: none !important;
        height: 100% !important;
        font-size: 14px !important;
        color: {input_text} !important;
        background-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }}

    div[data-testid="stForm"] input[type="password"] {{
        background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23cbd5e1' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='3' y='11' width='18' height='11' rx='2' ry='2'/><path d='M7 11V7a5 5 0 0 1 10 0v4'/></svg>") !important;
        background-repeat: no-repeat !important;
        background-position: 16px center !important;
        background-size: 18px !important;
        padding-left: 46px !important;
        border: none !important;
        height: 100% !important;
        font-size: 14px !important;
        color: {input_text} !important;
        background-color: transparent !important;
        outline: none !important;
        box-shadow: none !important;
    }}

    /* Set text secondary color specifically for input visibility button and force transparency */
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
    
    /* Submit button */
    div[data-testid="stFormSubmitButton"] button {{
        background-color: #1d4ed8 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
        padding: 0px 24px !important;
        height: 50px !important;
        font-size: 15px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        box-shadow: 0 8px 16px -4px rgba(29, 78, 216, 0.3) !important;
    }}
    div[data-testid="stFormSubmitButton"] button:hover {{
        background-color: #1e40af !important;
        box-shadow: 0 10px 20px -4px rgba(29, 78, 216, 0.4) !important;
    }}

    /* Under-card text link toggle container and button styling using Streamlit testid */
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button {{
        background-color: transparent !important;
        border: none !important;
        color: #1d4ed8 !important;
        font-size: 11px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px !important;
        text-transform: uppercase !important;
        padding: 0 !important;
        width: auto !important;
        cursor: pointer !important;
        box-shadow: none !important;
        height: auto !important;
        display: inline-block !important;
        margin-top: 16px !important;
        white-space: nowrap !important;
    }}
    
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] button:hover {{
        color: #1e40af !important;
        background-color: transparent !important;
        text-decoration: underline !important;
    }}

    /* Premium pill-shaped theme toggle switch matching the mockup using Streamlit testid */
    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label {{
        display: flex !important;
        flex-direction: row-reverse !important;
        justify-content: space-between !important;
        align-items: center !important;
        background-color: {toggle_bg} !important;
        border: 1px solid {toggle_border} !important;
        padding: 0px 14px !important;
        height: 38px !important;
        border-radius: 30px !important;
        width: 100% !important;
        max-width: 135px !important;
        margin-top: 16px !important;
        float: right !important;
        box-sizing: border-box !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }}
    
    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label:hover {{
        border-color: #3b82f6 !important;
    }}

    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label div[data-testid="stMarkdownContainer"] {{
        display: flex !important;
        align-items: center !important;
    }}

    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label div[data-testid="stMarkdownContainer"] p {{
        font-size: 10px !important;
        font-weight: 800 !important;
        letter-spacing: 0.8px !important;
        text-transform: uppercase !important;
        color: {text_secondary} !important;
        margin: 0 !important;
        white-space: nowrap !important;
    }}

    /* Sun icon before toggle label text */
    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label div[data-testid="stMarkdownContainer"]::before {{
        content: "" !important;
        display: inline-block !important;
        width: 14px !important;
        height: 14px !important;
        margin-right: 6px !important;
        background-color: currentColor !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
        flex-shrink: 0 !important;
    }}

    /* Track styles */
    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label > div:first-child {{
        background-color: #cbd5e1 !important;
    }}
    div[data-testid="stHorizontalBlock"] div[data-testid="stCheckbox"] label:has(input:checked) > div:first-child {{
        background-color: #1d4ed8 !important;
    }}

    /* Media query for mobile & tablet responsiveness */
    @media (max-width: 1199px) {{
        html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main, section.main > div {{
            overflow-y: auto !important;
            height: auto !important;
            max-height: none !important;
        }}

        .main .block-container {{
            height: auto !important;
            min-height: 100vh !important;
            max-height: none !important;
            padding: 2rem 1.5rem !important;
            justify-content: flex-start !important;
        }}

        /* Stack main columns vertically */
        div[data-testid="stHorizontalBlock"] {{
            flex-direction: column !important;
            gap: 2rem !important;
            align-items: stretch !important;
        }}

        div[data-testid="stHorizontalBlock"] > div {{
            width: 100% !important;
            max-width: 100% !important;
            min-width: 100% !important;
        }}

        /* Center content of the title column */
        div[data-testid="stHorizontalBlock"] > div:first-child {{
            text-align: center !important;
        }}
        
        div[data-testid="stHorizontalBlock"] > div:first-child div[style*="display: flex"] {{
            justify-content: center !important;
        }}

        div[data-testid="stHorizontalBlock"] > div:first-child p {{
            margin: auto !important;
        }}

        /* Responsive typography */
        h1 {{
            font-size: 32px !important;
            text-align: center !important;
        }}

        /* Compact card padding on mobile */
        div[data-testid="stForm"] {{
            padding: 24px 20px !important;
            border-radius: 24px !important;
        }}
    }}

    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    col1, col2 = st.columns([1.1, 0.9], gap="large")

    with col1:
        st.markdown(
            f'<div style="padding-top: 0.5rem;">'
            f'<div style="display: flex; align-items: center; gap: 8px; margin-bottom: 24px;">'
            f'<div style="background-color: #1d4ed8; color: white; border-radius: 8px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; font-weight: bold; box-shadow: 0 4px 12px rgba(29, 78, 216, 0.3);">'
            f'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'
            f'</div>'
            f'<div style="font-size: 11px; font-weight: 800; color: #1d4ed8; letter-spacing: 1.5px; text-transform: uppercase; display: flex; align-items: center; gap: 8px;">'
            f'UX Analytics <span style="display: inline-block; width: 24px; height: 1px; background-color: rgba(29, 78, 216, 0.3);"></span>'
            f'</div>'
            f'</div>'
            f'<h1 style="font-size: 48px; font-weight: 800; line-height: 1.1; color: {text_title_color}; margin-bottom: 16px; letter-spacing: -2px;">'
            f'Dashboard Hasil<br>'
            f'<span style="color: #1d4ed8;">Penelitian</span> UX<br>'
            f'Analytics'
            f'</h1>'
            f'<p style="font-size: 14px; color: {text_secondary}; line-height: 1.5; font-weight: 400; max-width: 480px; margin-bottom: 0;">'
            f'Platform analitik canggih untuk mengolah dan memvisualisasikan data pengalaman pengguna antara Light Mode dan Dark Mode dengan presisi tinggi.'
            f'</p>'
            f'</div>',
            unsafe_allow_html=True
        )

    with col2:
        if st.session_state["auth_mode"] == "login":
            with st.form("login_form"):
                st.markdown(
                    f'<div style="margin-bottom: 24px;">'
                    f'<div style="font-size: 34px; font-weight: 800; letter-spacing: -1px; color: {text_primary}; margin-bottom: 6px;">'
                    f'Selamat Datang'
                    f'</div>'
                    f'<div style="font-size: 13px; color: {text_secondary}; font-weight: 400; line-height: 1.4;">'
                    f'Silakan masuk untuk mengakses dashboard eksklusif Anda'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                st.markdown(f'<div style="font-size: 11px; font-weight: 800; color: {text_secondary}; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 8px;">USERNAME</div>', unsafe_allow_html=True)
                user = st.text_input("Username", placeholder="Masukkan username", label_visibility="collapsed").strip().lower()
                
                st.markdown(f'<div style="font-size: 11px; font-weight: 800; color: {text_secondary}; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 14px; margin-bottom: 8px;">PASSWORD</div>', unsafe_allow_html=True)
                pw = st.text_input("Password", type="password", placeholder="Masukkan password", label_visibility="collapsed")
                
                st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
                if st.form_submit_button("Masuk ➔", use_container_width=True):
                    ok, msg = login_user(user, pw)
                    if ok:
                        st.session_state.update({"logged_in": True, "current_user": user})
                        controller.set("session_user", user)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            with st.form("reg_form"):
                st.markdown(
                    f'<div style="margin-bottom: 24px;">'
                    f'<div style="font-size: 34px; font-weight: 800; letter-spacing: -1px; color: {text_primary}; margin-bottom: 6px;">'
                    f'Daftar Akun Baru'
                    f'</div>'
                    f'<div style="font-size: 13px; color: {text_secondary}; font-weight: 400; line-height: 1.4;">'
                    f'Silakan isi data di bawah untuk mendaftar'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )
                
                st.markdown(f'<div style="font-size: 11px; font-weight: 800; color: {text_secondary}; letter-spacing: 0.8px; text-transform: uppercase; margin-bottom: 8px;">USERNAME</div>', unsafe_allow_html=True)
                u = st.text_input("Username", placeholder="Pilih username minimal 3 karakter", label_visibility="collapsed").strip().lower()
                
                st.markdown(f'<div style="font-size: 11px; font-weight: 800; color: {text_secondary}; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 16px; margin-bottom: 8px;">PASSWORD</div>', unsafe_allow_html=True)
                p = st.text_input("Password", type="password", placeholder="Minimal 6 karakter", label_visibility="collapsed")
                
                st.markdown(f'<div style="font-size: 11px; font-weight: 800; color: {text_secondary}; letter-spacing: 0.8px; text-transform: uppercase; margin-top: 16px; margin-bottom: 8px;">KONFIRMASI PASSWORD</div>', unsafe_allow_html=True)
                cp = st.text_input("Konfirmasi Password", type="password", placeholder="Ulangi password", label_visibility="collapsed")
                
                st.markdown('<div style="margin-top: 24px;"></div>', unsafe_allow_html=True)
                if st.form_submit_button("Daftar ➔", use_container_width=True):
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

        # Place secondary buttons side-by-side to save height
        col_btn1, col_btn2 = st.columns([1.2, 0.8])
        with col_btn1:
            st.markdown('<div class="toggle-link-container">', unsafe_allow_html=True)
            if st.session_state["auth_mode"] == "login":
                if st.button("BELUM PUNYA AKUN? DAFTAR SEKARANG", use_container_width=False, key="btn_toggle_reg"):
                    st.session_state["auth_mode"] = "register"
                    st.rerun()
            else:
                if st.button("SUDAH PUNYA AKUN? MASUK", use_container_width=False, key="btn_toggle_login"):
                    st.session_state["auth_mode"] = "login"
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        with col_btn2:
            toggle_label = "Dark mode" if is_dark else "Light mode"
            is_dark_toggle = st.toggle(toggle_label, value=is_dark, key="login_theme_toggle_switch")
            if is_dark_toggle != is_dark:
                st.session_state["app_theme"] = "dark" if is_dark_toggle else "light"
                st.query_params["theme"] = "dark" if is_dark_toggle else "light"
                st.rerun()

    st.markdown(
        f'<div style="text-align: center; margin-top: 32px; font-size: 11px; color: {text_secondary}; letter-spacing: 2px; text-transform: uppercase; font-weight: 600;">'
        f'Universitas Islam Indonesia'
        f'</div>',
        unsafe_allow_html=True
    )

    return False

