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

    st.markdown("""
    <style>
    .block-container { max-width: 480px !important; padding-top: 60px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; margin-bottom:28px;">
        <h1 style="font-size:28px; font-weight:800; color:#6366f1; margin:0;">UX Analytics</h1>
        <p style="font-size:11px; color:#94a3b8; text-transform:uppercase;
           letter-spacing:2px; font-weight:600; margin-top:6px;">
           Universitas Islam Indonesia
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Login", "Daftar Akun"])

    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            st.markdown("#### Masuk ke Akun Anda")
            username = st.text_input("Username", placeholder="Masukkan username")
            password = st.text_input("Password", type="password", placeholder="Masukkan password")
            remember_me = st.checkbox("Ingat saya selama 24 jam")
            submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
        if submitted:
            if not username or not password:
                st.error("Username dan password wajib diisi.")
            else:
                ok, msg = login_user(username, password)
                if ok:
                    user = username.strip().lower()
                    st.session_state["logged_in"] = True
                    st.session_state["current_user"] = user
                    st.session_state["show_logout_confirm"] = False  # tambahkan ini
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
            st.markdown("#### Buat Akun Baru")
            new_username = st.text_input("Username", placeholder="Minimal 3 karakter", key="reg_user")
            new_password = st.text_input("Password", type="password", placeholder="Minimal 6 karakter", key="reg_pass")
            confirm_password = st.text_input("Konfirmasi Password", type="password", placeholder="Ulangi password", key="reg_confirm")
            reg_submitted = st.form_submit_button("Daftar", use_container_width=True, type="primary")
        if reg_submitted:
            if not new_username or not new_password or not confirm_password:
                st.error("Semua field wajib diisi.")
            elif new_password != confirm_password:
                st.error("Password dan konfirmasi password tidak cocok.")
            else:
                ok, msg = register_user(new_username, new_password)
                st.success(msg) if ok else st.error(msg)

    return False