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
        saved_user = controller.get("session_user")
        if saved_user and saved_user in load_users():
            st.session_state.update({"logged_in": True, "current_user": saved_user})
    if st.session_state.get("logged_in"):
        return True

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    # Define CSS variables based on theme
    if is_dark:
        bg_gradient = "linear-gradient(135deg, #090d16 0%, #0f172a 40%, #1e1b4b 100%)"
        card_bg = "rgba(31, 41, 55, 0.45)"
        card_border = "rgba(255, 255, 255, 0.08)"
        btn_border = "rgba(255, 255, 255, 0.15)"
        input_bg = "rgba(17, 24, 39, 0.6)"
        input_border = "rgba(255, 255, 255, 0.1)"
        input_text = "#f9fafb"
        text_primary = "#f9fafb"
        text_secondary = "#9ca3af"
        logo_gradient = "linear-gradient(135deg, #60a5fa 0%, #a5b4fc 100%)"
    else:
        bg_gradient = "linear-gradient(135deg, #eef2ff 0%, #f5f3ff 50%, #fdf2f8 100%)"
        card_bg = "rgba(255, 255, 255, 0.45)"
        card_border = "rgba(255, 255, 255, 0.4)"
        btn_border = "rgba(0, 0, 0, 0.12)"
        input_bg = "rgba(255, 255, 255, 0.6)"
        input_border = "rgba(0, 0, 0, 0.08)"
        input_text = "#111827"
        text_primary = "#111827"
        text_secondary = "#4b5563"
        logo_gradient = "linear-gradient(135deg, #1d4ed8 0%, #6366f1 100%)"

    # Fullscreen CSS injection & Scroll Lock (Compact Spacing Version)
    css = f"""
    <style>
    /* Lock scrolling only on screens with height >= 650px, allow scrolling on short viewports */
    @media (min-height: 650px) {{
        html {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
        body {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
        .stApp {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
        [data-testid="stAppViewContainer"] {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
        [data-testid="stMain"] {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
        section.main {{
            overflow: hidden !important;
            height: 100vh !important;
            max-height: 100vh !important;
        }}
    }}
    
    .stApp {{
        background: {bg_gradient} !important;
    }}
    [data-testid="stAppViewContainer"] {{
        background: transparent !important;
    }}
    section.main {{
        background: transparent !important;
    }}
    section.main > div {{
        background: transparent !important;
    }}
    header[data-testid="stHeader"] {{
        display: none !important;
    }}
    footer {{
        display: none !important;
    }}
    
    /* Collapse Streamlit default vertical spacing on login page */
    [data-testid="stElementContainer"] {{
        margin-bottom: 0.5rem !important;
    }}
    
    .main .block-container {{
        max-width: 1100px !important;
        padding: 0.75rem 2rem !important;
        margin: auto !important;
        display: flex;
        flex-direction: column;
        justify-content: center;
        min-height: 100vh;
        background: transparent !important;
    }}
    div[data-testid="stHorizontalBlock"] {{
        align-items: center !important;
        gap: 2.5rem !important;
    }}
    
    /* Force inner buttons row layout and prevent vertical stacking */
    div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] {{
        flex-direction: row !important;
        gap: 1rem !important;
        margin-top: 0.5rem !important;
    }}
    div[data-testid="stHorizontalBlock"] div[data-testid="stHorizontalBlock"] > div {{
        width: 50% !important;
        flex: 1 1 0% !important;
        min-width: 0 !important;
    }}
    
    /* Compact Glassmorphism Card */
    div[data-testid="stForm"] {{
        background-color: {card_bg} !important;
        backdrop-filter: blur(16px) saturate(180%) !important;
        -webkit-backdrop-filter: blur(16px) saturate(180%) !important;
        border: 1px solid {card_border} !important;
        border-radius: 20px !important;
        padding: 1.25rem 1.25rem !important;
        box-shadow: 0 20px 40px -15px rgba(0, 0, 0, {0.3 if is_dark else 0.06}) !important;
        margin-bottom: 0px !important;
    }}
    
    /* Reduce form widget margins */
    div[data-testid="stForm"] div.element-container {{
        margin-bottom: 0.25rem !important;
    }}
    
    div[data-testid="stForm"] .stTextInput input {{
        background-color: {input_bg} !important;
        color: {input_text} !important;
        border: 1px solid {input_border} !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.6rem !important;
        font-size: 13px !important;
    }}
    div[data-testid="stForm"] .stTextInput input:focus {{
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }}
    
    /* Form Label Styling */
    div[data-testid="stForm"] label {{
        font-size: 12px !important;
        font-weight: 600 !important;
        margin-bottom: 4px !important;
        color: {text_primary} !important;
    }}
    
    /* Submit button */
    div[data-testid="stFormSubmitButton"] button {{
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        font-size: 13px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
    }}
    div[data-testid="stFormSubmitButton"] button:hover {{
        background-color: #2563eb !important;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3) !important;
    }}
    
    /* Toggle & Theme buttons outside form */
    div[data-testid="stButton"] button,
    [data-testid="stButton"] button[data-testid="stBaseButton-secondary"] {{
        background-color: transparent !important;
        color: {text_secondary} !important;
        border: 1px solid {btn_border} !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 12px !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        margin-top: 0px !important;
        padding: 0.4rem 0.75rem !important;
    }}
    div[data-testid="stButton"] button:hover,
    [data-testid="stButton"] button[data-testid="stBaseButton-secondary"]:hover {{
        color: #3b82f6 !important;
        border-color: #3b82f6 !important;
        background-color: rgba(59, 130, 246, 0.05) !important;
    }}
    
    @media (max-width: 768px) {{
        div[data-testid="stHorizontalBlock"] {{
            gap: 2rem !important;
        }}
    }}

    /* Style the theme toggle switch wrapper to look like a premium card */
    div[class*="theme_toggle_switch"] label {{
        display: flex !important;
        flex-direction: row-reverse !important;
        justify-content: space-between !important;
        align-items: center !important;
        background-color: {'#1f2937' if is_dark else '#f3f4f6'} !important;
        border: 1px solid {'rgba(255,255,255,0.05)' if is_dark else 'rgba(0,0,0,0.04)'} !important;
        padding: 0px 12px !important;
        height: 38px !important;
        border-radius: 12px !important;
        width: 100% !important;
        margin: 0px 0 !important;
        box-sizing: border-box !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }}
    
    div[class*="theme_toggle_switch"] label:hover {{
        background-color: {'#374151' if is_dark else '#e5e7eb'} !important;
    }}

    /* Align and style the text label inside the toggle */
    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"] {{
        display: flex !important;
        align-items: center !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: {text_primary} !important;
    }}

    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"] p {{
        margin: 0 !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: {text_primary} !important;
        white-space: nowrap !important;
    }}

    /* Default/Dark Mode: Moon Icon on the left */
    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"]::before {{
        content: "" !important;
        display: inline-block !important;
        width: 16px !important;
        height: 16px !important;
        margin-right: 8px !important;
        background-color: currentColor !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
        flex-shrink: 0 !important;
    }}

    /* Light Mode: Sun Icon on the left (when switch is NOT checked) */
    div[class*="theme_toggle_switch"] label:not(:has(input:checked)) div[data-testid="stMarkdownContainer"]::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
    }}

    /* Style the Track background of the toggle */
    div[class*="theme_toggle_switch"] label > div:first-child {{
        background-color: #e2e8f0 !important;
        transition: background-color 0.2s ease !important;
    }}
    /* When active (Dark Mode is checked), track is light purple */
    div[class*="theme_toggle_switch"] label:has(input:checked) > div:first-child {{
        background-color: #c7d2fe !important;
    }}
    
    /* Style the Knob (Handle) of the toggle */
    div[class*="theme_toggle_switch"] label > div:first-child > div {{
        background-color: #1e293b !important;
        transition: transform 0.2s ease, background-color 0.2s ease !important;
    }}
    /* When checked, knob is dark slate */
    div[class*="theme_toggle_switch"] label:has(input:checked) > div:first-child > div {{
        background-color: #0f172a !important;
    }}
    
    /* Draw white moon icon outline inside the toggle knob in both states */
    div[class*="theme_toggle_switch"] label > div:first-child > div::after {{
        content: "" !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        width: 10px !important;
        height: 10px !important;
        background-color: #ffffff !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

    col1, col2 = st.columns([1.1, 0.9], gap="large")

    with col1:
        st.markdown(f"""
        <div style="padding-top: 0.5rem;">
            <div style="font-size: 32px; font-weight: 800; font-family: system-ui, -apple-system, sans-serif; margin-bottom: 12px; letter-spacing: -0.5px; background: {logo_gradient}; -webkit-background-clip: text; -webkit-text-fill-color: transparent; width: fit-content;">
                UX Analytics
            </div>
            <h1 style="font-size: 32px; font-weight: 700; line-height: 1.25; color: {text_primary}; margin-bottom: 12px; font-family: system-ui, -apple-system, sans-serif; letter-spacing: -0.5px;">
                Dashboard Hasil Penelitian UX Analytics
            </h1>
            <p style="font-size: 14px; color: {text_secondary}; line-height: 1.5; font-family: system-ui, -apple-system, sans-serif; font-weight: 400; max-width: 480px;">
                Analisis preferensi dan kenyamanan pengguna antara tampilan Light Mode dan Dark Mode berdasarkan data kuesioner UEQ dan metrik performa secara real-time.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        if st.session_state["auth_mode"] == "login":
            with st.form("login_form"):
                st.markdown(f"""
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: {text_primary}; margin-bottom: 4px; font-family: system-ui, -apple-system, sans-serif;">
                        Selamat Datang
                    </div>
                    <div style="font-size: 13px; color: {text_secondary}; font-weight: 400; font-family: system-ui, -apple-system, sans-serif;">
                        Silakan masuk untuk mengakses dashboard
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                user = st.text_input("Username", placeholder="Masukkan username").strip().lower()
                pw = st.text_input("Password", type="password", placeholder="Masukkan password")
                
                if st.form_submit_button("Masuk", use_container_width=True):
                    ok, msg = login_user(user, pw)
                    if ok:
                        st.session_state.update({"logged_in": True, "current_user": user})
                        controller.set("session_user", user)
                        st.rerun()
                    else:
                        st.error(msg)
        else:
            with st.form("reg_form"):
                st.markdown(f"""
                <div style="margin-bottom: 16px;">
                    <div style="font-size: 24px; font-weight: 700; letter-spacing: -0.5px; color: {text_primary}; margin-bottom: 4px; font-family: system-ui, -apple-system, sans-serif;">
                        Daftar Akun Baru
                    </div>
                    <div style="font-size: 13px; color: {text_secondary}; font-weight: 400; font-family: system-ui, -apple-system, sans-serif;">
                        Silakan isi data di bawah untuk mendaftar
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                u = st.text_input("Username", placeholder="Pilih username minimal 3 karakter").strip().lower()
                p = st.text_input("Password", type="password", placeholder="Minimal 6 karakter")
                cp = st.text_input("Konfirmasi Password", type="password", placeholder="Ulangi password")
                
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

        # Place secondary buttons side-by-side to save height
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.session_state["auth_mode"] == "login":
                if st.button("Belum punya akun? Daftar", use_container_width=True, key="btn_toggle_reg"):
                    st.session_state["auth_mode"] = "register"
                    st.rerun()
            else:
                if st.button("Sudah punya akun? Masuk", use_container_width=True, key="btn_toggle_login"):
                    st.session_state["auth_mode"] = "login"
                    st.rerun()
        with col_btn2:
            toggle_label = "Dark mode" if is_dark else "Light mode"
            is_dark_toggle = st.toggle(toggle_label, value=is_dark, key="login_theme_toggle_switch")
            if is_dark_toggle != is_dark:
                st.session_state["app_theme"] = "dark" if is_dark_toggle else "light"
                st.query_params["theme"] = "dark" if is_dark_toggle else "light"
                st.rerun()

    st.markdown(f"""
    <div style="text-align: center; margin-top: 24px; font-size: 11px; color: {text_secondary}; letter-spacing: 0.5px; text-transform: uppercase; font-weight: 600; font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;">
        Universitas Islam Indonesia
    </div>
    """, unsafe_allow_html=True)

    return False
