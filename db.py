import pandas as pd
import streamlit as st
import requests

# ==========================================
# KONFIGURASI SUPABASE & HEADER KONEKSI
# ==========================================
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

ITEMS = [f"I{i}" for i in range(1, 27)]
PREF_COLS = [
    "R1","R2","R3","R4",
    "ES1","ES2","ES3","ES4",
    "U1","U2","U3","U4",
    "B1","B2","B3","B4",
    "E1","E2","E3","E4",
    "ED1","ED2","ED3","ED4",
]

# ==========================================
# MANAJEMEN DAFTAR APLIKASI (RESEARCH OBJECT)
# ==========================================
def load_app_list(username):
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/app_list?select=app_name&username=eq.{username}",
            headers=HEADERS
        )
        res.raise_for_status()
        return [row["app_name"] for row in res.json()]
    except Exception:
        return []

def save_app_list(username, app_list):
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/app_list?username=eq.{username}",
            headers=HEADERS
        )
        res.raise_for_status()
        if app_list:
            rows = [{"username": username, "app_name": name} for name in app_list]
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/app_list",
                headers=HEADERS,
                json=rows
            )
            res.raise_for_status()
    except Exception as e:
        st.error(f"Gagal simpan app list: {e}")

# ==========================================
# OPERASI DATA TIME ON TASK & ERROR RATE
# ==========================================
def load_data(table, username, app):
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        data = res.json()
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df = df.drop(columns=["id", "username", "app"], errors="ignore")
        rename_map = {}
        for c in df.columns:
            if c.lower() == "responden":
                rename_map[c] = "Responden"
            elif c.lower() == "light_t1": rename_map[c] = "Light_T1"
            elif c.lower() == "light_t2": rename_map[c] = "Light_T2"
            elif c.lower() == "light_t3": rename_map[c] = "Light_T3"
            elif c.lower() == "dark_t1":  rename_map[c] = "Dark_T1"
            elif c.lower() == "dark_t2":  rename_map[c] = "Dark_T2"
            elif c.lower() == "dark_t3":  rename_map[c] = "Dark_T3"
            else:
                rename_map[c] = c
        df = df.rename(columns=rename_map)
        return df
    except Exception:
        return pd.DataFrame()

def save_data(table, username, app, df):
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        df_copy = df.copy()
        cols_keep = ["Responden","Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]
        df_copy = df_copy[[c for c in cols_keep if c in df_copy.columns]]
        df_copy.columns = [c.lower() for c in df_copy.columns]
        df_copy["username"] = username
        df_copy["app"] = app
        records = df_copy.to_dict(orient="records")
        if records:
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=HEADERS,
                json=records
            )
            res.raise_for_status()
        return True
    except Exception as e:
        st.exception(e)
        return False

# ==========================================
# OPERASI DATA UEQ (USER EXPERIENCE QUESTIONNAIRE)
# ==========================================
def load_ueq(table, username, app, n):
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        data = res.json()
        if not data:
            return pd.DataFrame(4, index=range(n), columns=ITEMS)
        df = pd.DataFrame(data)
        df = df.drop(columns=["id", "username", "app", "responden"], errors="ignore")
        rename_map = {}
        for c in df.columns:
            if c.lower().startswith("i") and c[1:].isdigit():
                rename_map[c] = f"I{c[1:]}"
        df = df.rename(columns=rename_map)
        for col in ITEMS:
            if col not in df.columns:
                df[col] = 4
        return df[ITEMS].apply(pd.to_numeric, errors="coerce").fillna(4)
    except Exception:
        return pd.DataFrame(4, index=range(n), columns=ITEMS)

def save_ueq(table, username, app, df):
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        df_copy = df.copy()
        df_copy.columns = [c.lower() for c in df_copy.columns]
        df_copy["username"] = username
        df_copy["app"] = app
        df_copy["responden"] = [f"R{i+1}" for i in range(len(df_copy))]
        records = df_copy.to_dict(orient="records")
        if records:
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=HEADERS,
                json=records
            )
            res.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Gagal simpan UEQ: {e}")
        return False

# ==========================================
# OPERASI DATA PREFERENSI RESPONDEN
# ==========================================
def load_pref(table, username, app, n):
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=*&username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        data = res.json()
        if not data:
            df = pd.DataFrame(0, index=range(n), columns=["Responden"] + PREF_COLS)
            df["Responden"] = [f"R{i+1}" for i in range(n)]
            return df
        df = pd.DataFrame(data)
        df = df.drop(columns=["id", "username", "app"], errors="ignore")
        rename_map = {}
        for c in df.columns:
            cu = c.upper()
            if c.lower() == "responden":
                rename_map[c] = "Responden"
            elif cu in PREF_COLS:
                rename_map[c] = cu
        df = df.rename(columns=rename_map)
        if "Responden" not in df.columns:
            df.insert(0, "Responden", [f"R{i+1}" for i in range(len(df))])
        for col in PREF_COLS:
            if col not in df.columns:
                df[col] = 0
        return df[["Responden"] + PREF_COLS]
    except Exception:
        df = pd.DataFrame(0, index=range(n), columns=["Responden"] + PREF_COLS)
        df["Responden"] = [f"R{i+1}" for i in range(n)]
        return df

def save_pref(table, username, app, df):
    try:
        res = requests.delete(
            f"{SUPABASE_URL}/rest/v1/{table}?username=eq.{username}&app=eq.{app}",
            headers=HEADERS
        )
        res.raise_for_status()
        df_copy = df.copy()
        df_copy.columns = [c.lower() for c in df_copy.columns]
        df_copy["username"] = username
        df_copy["app"] = app
        records = df_copy.to_dict(orient="records")
        if records:
            res = requests.post(
                f"{SUPABASE_URL}/rest/v1/{table}",
                headers=HEADERS,
                json=records
            )
            res.raise_for_status()
        return True
    except Exception as e:
        st.error(f"Gagal simpan preferensi: {e}")
        return False

def pref_exists(table, username, app):
    try:
        res = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select=username&username=eq.{username}&app=eq.{app}&limit=1",
            headers=HEADERS
        )
        res.raise_for_status()
        return len(res.json()) > 0
    except Exception:
        return False
