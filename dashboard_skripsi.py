import streamlit as st
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt
import os
import math
import plotly.graph_objects as go
import streamlit.components.v1 as components
from textwrap import dedent
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from scipy.stats import shapiro
from scipy.stats import wilcoxon, norm
from scipy.stats import rankdata
from auth import render_auth_page, logout, render_settings_page
import pingouin as pg
from scipy.stats import t as t_dist
import requests
from PIL import Image

from db import (
    load_app_list, save_app_list,
    load_data, save_data,
    load_ueq, save_ueq,
    load_pref, save_pref,
    pref_exists
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if "app_list" not in st.session_state:
    st.session_state.app_list = []
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False
if "show_logout_confirm" not in st.session_state:
    st.session_state.show_logout_confirm = False
if "show_reset_confirm" not in st.session_state:
    st.session_state.show_reset_confirm = False
if "menu" not in st.session_state:
    st.session_state["menu"] = "Home"

# ======================
# THEME DETECTION
# ======================
theme = st.get_option("theme.base")
if theme == "dark":
    plt.style.use("dark_background")
    bg_main    = "#020617"
    bg_card    = "#0f172a"
    bg_sidebar = "#020617"
    bg_insight = "#1e293b"
    text_main  = "#f1f5f9"
    text_soft  = "#94a3b8"
    border     = "#1e293b"
else:
    plt.style.use("default")
    bg_main    = "linear-gradient(135deg,#f8fafc,#eef2f7)"
    bg_card    = "#ffffff"
    bg_sidebar = "#f8fafc"
    bg_insight = "#f1f5f9"
    text_main  = "#111827"
    text_soft  = "#6b7280"
    border     = "#e5e7eb"

# ======================
# PAGE CONFIG
# ======================
try:
    icon = Image.open(os.path.join(BASE_DIR, "assets", "icon.png"))
    st.set_page_config(page_title="UX Research Dashboard", layout="wide", page_icon=icon)
except Exception:
    st.set_page_config(page_title="UX Research Dashboard", layout="wide", page_icon="📊")

# ======================
# SIDEBAR CSS — didefinisikan SEBELUM dipakai
# ======================
SIDEBAR_CSS = """
<style>
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #f0f0f0 !important;
    box-shadow: 4px 0 24px rgba(0,0,0,0.06) !important;
}
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }

/* Avatar card */
.sb-avatar-card {
    display: flex; align-items: center; gap: 12px;
    padding: 20px 20px 16px 20px;
    border-bottom: 1px solid #f3f4f6;
    margin-bottom: 4px;
}
.sb-avatar {
    width: 42px; height: 42px; border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; font-weight: 800; color: white; flex-shrink: 0;
    box-shadow: 0 2px 8px rgba(99,102,241,0.3);
}
.sb-user-info { display: flex; flex-direction: column; }
.sb-user-role {
    font-size: 9px; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 2px;
}
.sb-user-name { font-size: 14px; font-weight: 700; color: #111827; line-height: 1.2; }

/* Section label */
.sb-section-label {
    font-size: 9px !important; font-weight: 800 !important;
    color: #9ca3af !important; text-transform: uppercase !important;
    letter-spacing: 1.4px !important;
    padding: 12px 20px 4px 20px !important;
    margin: 0 !important; display: block;
}

/* Active App Card */
.sb-app-card {
    margin: 10px 12px; padding: 12px 14px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 12px; color: white;
}
.sb-app-card-label {
    font-size: 9px; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; opacity: 0.75; margin-bottom: 4px;
}
.sb-app-card-name { font-size: 14px; font-weight: 800; margin-bottom: 2px; }
.sb-app-card-meta { font-size: 10px; opacity: 0.7; }

/* Selectbox sidebar */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #f9fafb !important; border: 1px solid #e5e7eb !important;
    border-radius: 10px !important; font-size: 13px !important;
    font-weight: 600 !important; color: #374151 !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div:hover {
    border-color: #6366f1 !important;
}

/* Number input sidebar */
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {
    background: #f9fafb !important; border: 1px solid #e5e7eb !important;
    border-radius: 10px !important; font-size: 13px !important;
    font-weight: 600 !important; color: #374151 !important;
}

/* Expander sidebar */
[data-testid="stSidebar"] details {
    background: #f9fafb !important; border: 1px solid #e5e7eb !important;
    border-radius: 10px !important; margin: 4px 12px !important;
}
[data-testid="stSidebar"] details summary {
    font-size: 12px !important; font-weight: 600 !important;
    color: #374151 !important; padding: 8px 12px !important;
}

/* Tombol navigasi menu */
[data-testid="stSidebar"] .stButton > button {
    background: transparent !important;
    border: none !important;
    border-radius: 10px !important;
    text-align: left !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    padding: 9px 14px !important;
    margin: 1px 10px !important;
    width: calc(100% - 20px) !important;
    transition: background 0.15s ease, color 0.15s ease !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: #f5f3ff !important;
    color: #4f46e5 !important;
}

/* Tombol logout — merah */
[data-testid="stSidebar"] button[kind="primary"] {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; font-size: 11px !important;
    font-weight: 700 !important;
}

/* Tombol reset — merah muda */
[data-testid="stSidebar"] button[kind="secondary"] {
    background: #fff1f2 !important; color: #ef4444 !important;
    border: 1px solid #fecaca !important; border-radius: 10px !important;
    font-size: 11px !important; font-weight: 700 !important;
}

/* Label input sidebar */
[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
    font-size: 9px !important; font-weight: 700 !important;
    color: #9ca3af !important; text-transform: uppercase !important;
    letter-spacing: 1px !important;
}

/* Padding konten */
[data-testid="stSidebar"] .block-container { padding: 0 !important; }
section[data-testid="stSidebar"] .stSelectbox { padding: 0 12px; margin-bottom: 4px; }
section[data-testid="stSidebar"] .stNumberInput { padding: 0 12px; margin-bottom: 4px; }

/* Divider */
[data-testid="stSidebar"] hr {
    border-top: 1px solid #f3f4f6 !important;
    margin: 8px 16px !important;
}

section[data-testid="stSidebar"] > div:first-child {
    height: 100vh; display: flex; flex-direction: column;
}
</style>
"""

# ======================
# GLOBAL CSS (main area)
# ======================
st.markdown(f"""
<style>
.block-container {{ max-width: 1500px; padding-top: 70px; }}
* {{ transition: background 0.3s ease, color 0.3s ease; }}

.stDataFrame, .stTable {{ border-radius:12px; overflow:hidden; border:1px solid #e5e7eb; }}
.card {{
    background: {bg_card} !important; padding: 24px; border-radius: 20px;
    border: 1px solid {border} !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    transition: all 0.3s ease; height: 100%; color: {text_main} !important;
}}
.card:hover {{
    transform: translateY(-5px);
    box-shadow: 0 20px 25px -5px rgba(0,0,0,0.08);
    border-color: #6366f1;
}}
.metric-title {{ font-size:14px; font-weight:500; color:{text_soft}; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px; }}
.metric-value {{ font-size:26px; font-weight:800; color:{text_main} !important; line-height:1.2; }}
.val-light {{ color: #6366f1; font-weight: 800; }}
.val-dark  {{ color: #a78bfa; font-weight: 800; }}
.vs-divider {{ color: #94a3b8; font-size: 14px; font-weight: 400; margin: 0 4px; }}
.pref-card {{ background:{bg_card}; border:1px solid {border}; border-radius:15px; padding:20px; text-align:center; }}
.pref-label {{ font-size:12px; font-weight:600; color:{text_soft}; text-transform:uppercase; margin-bottom:10px; }}
.pref-value {{ font-size:20px; font-weight:700; color:{text_main}; }}
.p-card {{ background-color:{bg_card}; padding:20px; border-radius:15px; border:1px solid #e2e8f0; margin-bottom:20px; }}
h3 {{ font-size: 16px !important; }}
[data-testid="stMetricV2"] {{ background-color:{bg_card} !important; color:{text_main} !important; }}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{ background-color:{bg_card} !important; }}
.stAlert {{ background-color:{bg_insight} !important; color:{text_main} !important; }}
details {{ background:{bg_card} !important; border:1px solid {border} !important; border-radius:8px; }}
</style>
""", unsafe_allow_html=True)

# ======================
# FUNGSI HELPER
# ======================
def interpret_ueq(score):
    if score > 1.5:    return "Excellent"
    elif score > 0.8:  return "Good"
    elif score > 0:    return "Above Average"
    elif score > -0.8: return "Below Average"
    else:              return "Bad"

def wilcoxon_full_spss(light, dark):
    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    mask  = ~(light.isna() | dark.isna())
    light, dark = light[mask], dark[mask]
    diff = dark - light
    df   = pd.DataFrame({"diff": diff})
    df   = df[df["diff"] != 0]
    df["abs"]  = df["diff"].abs()
    df["rank"] = rankdata(df["abs"], method="average")
    negative = df[df["diff"] < 0]
    positive = df[df["diff"] > 0]
    n = len(df)
    ranks_table = pd.DataFrame({
        "": ["Negative Ranks","Positive Ranks","Ties","Total"],
        "N": [len(negative), len(positive), len(diff)-n, len(diff)],
        "Mean Rank": [
            round(negative["rank"].mean(),2) if len(negative)>0 else 0,
            round(positive["rank"].mean(),2) if len(positive)>0 else 0,
            "", ""
        ],
        "Sum of Ranks": [
            round(negative["rank"].sum(),2),
            round(positive["rank"].sum(),2),
            "", ""
        ]
    })
    W_pos = positive["rank"].sum()
    W_neg = negative["rank"].sum()
    W     = min(W_pos, W_neg)
    mean_T = n*(n+1)/4
    ties_count = df["abs"].value_counts()
    tie_sum    = np.sum(ties_count**3 - ties_count)
    var_T  = (n*(n+1)*(2*n+1) - 0.5*tie_sum)/24
    sd_T   = np.sqrt(var_T)
    res = wilcoxon(light, dark, zero_method='wilcox', correction=False,
                   alternative='two-sided', method='approx')
    correction = 0
    z_raw = (W - mean_T + correction) / sd_T
    z = -abs(z_raw) if W_neg <= W_pos else abs(z_raw)
    p = 2*(1 - norm.cdf(abs(z)))
    stats_table = pd.DataFrame({
        "": ["Z","Asymp. Sig (2-tailed)"],
        "Value": [round(z,3), round(p,3)]
    })
    return ranks_table, stats_table

def compute_wilcoxon_pair(light, dark, light_lbl, dark_lbl):
    ranks_table, stats_table = wilcoxon_full_spss(light, dark)
    z_val   = float(stats_table.iloc[0,1])
    p_val   = float(stats_table.iloc[1,1])
    neg_n   = int(ranks_table.iloc[0]["N"])
    pos_n   = int(ranks_table.iloc[1]["N"])
    ties_n  = int(ranks_table.iloc[2]["N"])
    total_n = int(ranks_table.iloc[3]["N"])
    neg_mean = ranks_table.iloc[0]["Mean Rank"]
    pos_mean = ranks_table.iloc[1]["Mean Rank"]
    neg_sum  = ranks_table.iloc[0]["Sum of Ranks"]
    pos_sum  = ranks_table.iloc[1]["Sum of Ranks"]
    def fmt(v, decimals=2):
        try: return f"{float(v):.{decimals}f}"
        except: return ""
    return {
        "var_name": f"{dark_lbl} - {light_lbl}",
        "light_lbl": light_lbl, "dark_lbl": dark_lbl,
        "neg_n": neg_n, "pos_n": pos_n, "ties_n": ties_n, "total_n": total_n,
        "neg_mean": fmt(neg_mean), "pos_mean": fmt(pos_mean),
        "neg_sum": fmt(neg_sum),   "pos_sum": fmt(pos_sum),
        "z_val": z_val, "p_val": p_val,
    }

def shapiro_and_ks(light, dark, label):
    from scipy.stats import kstest
    import warnings
    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    mask  = ~(light.isna() | dark.isna())
    diff  = (dark - light)[mask]
    if len(diff) < 3:
        return {"label":label,"n":int(mask.sum()),"ks_stat":np.nan,"ks_p":np.nan,
                "sw_stat":np.nan,"sw_p":np.nan,"normal":None}
    sw_stat, sw_p = shapiro(diff)
    diff_std = (diff - diff.mean()) / diff.std(ddof=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ks_stat, ks_p_raw = kstest(diff_std, 'norm')
    try:
        from statsmodels.stats.diagnostic import lilliefors as lf_test
        ks_stat, ks_p = lf_test(diff, dist='norm')
    except Exception:
        ks_stat, ks_p = ks_stat, ks_p_raw
    return {
        "label": label, "n": int(len(diff)),
        "ks_stat": round(float(ks_stat),3), "ks_p": round(float(ks_p),3),
        "sw_stat": round(float(sw_stat),3), "sw_p": round(float(sw_p),3),
        "normal": bool(sw_p >= 0.05),
    }

def render_normality_table(results):
    def _fmt_p(v):
        if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
        if v < 0.001: return "<,001"
        return f"{v:.3f}".replace(".",",")
    def _fmt_stat(v):
        if v is None or (isinstance(v,float) and np.isnan(v)): return "—"
        return f"{v:.3f}"
    rows_html = ""
    for r in results:
        sw_sig = (not (isinstance(r["sw_p"],float) and np.isnan(r["sw_p"]))) and r["sw_p"] < 0.05
        ks_sig = (not (isinstance(r["ks_p"],float) and np.isnan(r["ks_p"]))) and r["ks_p"] < 0.05
        p_sw_color = "#c0392b" if sw_sig else "inherit"
        p_ks_color = "#c0392b" if ks_sig else "inherit"
        rows_html += f"""
        <tr>
          <td style="border:1px solid #bbb;padding:6px 12px;font-weight:600;background:#f5f5f5;white-space:nowrap;">{r['label']}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;">{_fmt_stat(r['ks_stat'])}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;">{r['n']}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;color:{p_ks_color};font-weight:{'700' if ks_sig else '400'};">{_fmt_p(r['ks_p'])}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;">{_fmt_stat(r['sw_stat'])}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;">{r['n']}</td>
          <td style="border:1px solid #bbb;padding:6px 12px;text-align:center;color:{p_sw_color};font-weight:{'700' if sw_sig else '400'};">{_fmt_p(r['sw_p'])}</td>
        </tr>"""
    st.markdown(f"""
    <div style="margin:16px 0 4px 0;overflow-x:auto;">
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;min-width:600px;width:100%;">
        <thead>
          <tr>
            <th rowspan="2" style="border:1px solid #aaa;padding:7px 12px;background:#d9d9d9;text-align:left;font-weight:700;font-size:13px;">Tests of Normality</th>
            <th colspan="3" style="border:1px solid #aaa;padding:7px 12px;background:#d9d9d9;text-align:center;font-weight:600;font-size:12px;">Kolmogorov-Smirnov<sup>a</sup></th>
            <th colspan="3" style="border:1px solid #aaa;padding:7px 12px;background:#d9d9d9;text-align:center;font-weight:600;font-size:12px;">Shapiro-Wilk</th>
          </tr>
          <tr style="background:#ececec;">
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">Statistic</th>
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">df</th>
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">Sig.</th>
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">Statistic</th>
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">df</th>
            <th style="border:1px solid #aaa;padding:6px 12px;text-align:center;font-size:12px;">Sig.</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <div style="font-size:11px;color:#444;margin-top:4px;font-style:italic;">a. Lilliefors Significance Correction</div>
    </div>
    """, unsafe_allow_html=True)

def render_normality_recommendation(results):
    valid = [r for r in results if r.get("normal") is not None]
    if not valid: return "wilcoxon"
    all_normal = all(r["normal"] for r in valid)
    if all_normal:
        color, bg, border_c = "#166534","#F0FDF4","#BBF7D0"
        icon  = "✓"
        title = "Selisih berdistribusi normal pada semua variabel (Sig. Shapiro-Wilk ≥ 0,05)"
        desc  = "Rekomendasi otomatis: Paired Samples T-Test (Parametrik)"
        rec   = "t-test"
    else:
        not_normal = [r["label"] for r in valid if not r["normal"]]
        color, bg, border_c = "#92400E","#FFFBEB","#FDE68A"
        icon  = "!"
        title = f"Distribusi tidak normal pada: {', '.join(not_normal)} (Sig. Shapiro-Wilk < 0,05)"
        desc  = "Rekomendasi otomatis: Wilcoxon Signed Ranks Test (Non-Parametrik)"
        rec   = "wilcoxon"
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border_c};border-radius:10px;padding:12px 18px;display:flex;align-items:center;gap:14px;margin:10px 0;">
      <div style="font-size:20px;color:{color};font-weight:800;flex-shrink:0;">{icon}</div>
      <div>
        <div style="font-size:13px;font-weight:700;color:{color};">{title}</div>
        <div style="font-size:12px;color:{color};margin-top:3px;opacity:.9;">{desc}</div>
      </div>
    </div>
    <div style="font-size:11px;color:#64748b;font-style:italic;margin-bottom:8px;">
      H₀: Selisih berdistribusi normal · α = 0,05 · Acuan: Shapiro-Wilk (n &lt; 50)
    </div>
    """, unsafe_allow_html=True)
    return rec

def compute_paired_ttest_pair(light, dark, light_lbl, dark_lbl):
    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    mask  = ~(light.isna() | dark.isna())
    light, dark = light[mask], dark[mask]
    n      = len(light)
    diff   = light - dark
    dmean  = float(diff.mean())
    dstd   = float(diff.std(ddof=1))
    dse    = dstd / np.sqrt(n)
    df_val = n - 1
    t_stat, p_two = stats.ttest_rel(light, dark)
    p_one  = p_two / 2
    ci_low, ci_up = stats.t.interval(0.95, df_val, loc=dmean, scale=dse)
    corr_r, corr_p = stats.pearsonr(light, dark) if n >= 2 else (np.nan, np.nan)
    return {
        "light_lbl": light_lbl, "dark_lbl": dark_lbl, "n": n,
        "light_mean": float(light.mean()), "dark_mean": float(dark.mean()),
        "light_std": float(light.std(ddof=1)), "dark_std": float(dark.std(ddof=1)),
        "light_se": float(light.std(ddof=1))/np.sqrt(n),
        "dark_se":  float(dark.std(ddof=1))/np.sqrt(n),
        "diff_mean": dmean, "diff_std": dstd, "diff_se": dse,
        "ci_low": float(ci_low), "ci_up": float(ci_up),
        "t": float(t_stat), "df": df_val,
        "p_one": float(p_one), "p_two": float(p_two),
        "corr_r": float(corr_r) if not np.isnan(corr_r) else np.nan,
        "corr_p": float(corr_p) if not np.isnan(corr_p) else np.nan,
    }

def render_spss_paired_ttest(pairs_data):
    stat_rows = ""
    for idx, p in enumerate(pairs_data):
        for role, lbl, mean, std, se in [
            (f"Pair {idx+1}", p["light_lbl"], p["light_mean"], p["light_std"], p["light_se"]),
            ("", p["dark_lbl"], p["dark_mean"], p["dark_std"], p["dark_se"]),
        ]:
            stat_rows += f"""
            <tr>
              <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#f5f5f5;white-space:nowrap;">{role}</td>
              <td style="border:1px solid #bbb;padding:7px 12px;">{lbl}</td>
              <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{mean:.4f}</td>
              <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['n']}</td>
              <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{std:.4f}</td>
              <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{se:.4f}</td>
            </tr>"""
    corr_rows = ""
    for idx, p in enumerate(pairs_data):
        cr = f"{p['corr_r']:.3f}" if not np.isnan(p["corr_r"]) else "—"
        cp = f"{p['corr_p']:.3f}" if not np.isnan(p["corr_p"]) else "—"
        corr_rows += f"""
        <tr>
          <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#f5f5f5;">Pair {idx+1}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;">{p['light_lbl']} &amp; {p['dark_lbl']}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['n']}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{cr}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{cp}</td>
        </tr>"""
    test_rows = ""
    for idx, p in enumerate(pairs_data):
        sig2   = f"{p['p_two']:.3f}" if not np.isnan(p["p_two"]) else "—"
        is_sig = (not np.isnan(p["p_two"])) and p["p_two"] < 0.05
        sig_bg = "#f0fdf4" if is_sig else "#eaf4ff"
        test_rows += f"""
        <tr>
          <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#f5f5f5;white-space:nowrap;">Pair {idx+1}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;">{p['light_lbl']} − {p['dark_lbl']}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['diff_mean']:.4f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['diff_std']:.4f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['diff_se']:.4f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['ci_low']:.4f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['ci_up']:.4f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['t']:.3f}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p['df']}</td>
          <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;background:{sig_bg};font-weight:700;">{sig2}</td>
        </tr>"""
    st.markdown(f"""
    <div style="margin:20px 0 8px 0;">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid #333;padding-bottom:4px;">Paired Samples Statistics</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;">
        <thead><tr style="background:#d9d9d9;">
          <th colspan="2" style="border:1px solid #aaa;padding:7px 12px;"></th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Mean</th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">N</th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Std. Deviation</th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Std. Error Mean</th>
        </tr></thead>
        <tbody>{stat_rows}</tbody>
      </table>
    </div>
    <div style="margin:16px 0 8px 0;">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid #333;padding-bottom:4px;">Paired Samples Correlations</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;">
        <thead><tr style="background:#d9d9d9;">
          <th colspan="2" style="border:1px solid #aaa;padding:7px 12px;"></th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">N</th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Correlation</th>
          <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Sig.</th>
        </tr></thead>
        <tbody>{corr_rows}</tbody>
      </table>
    </div>
    <div style="margin:16px 0 24px 0;">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid #333;padding-bottom:4px;">Paired Samples Test</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;">
        <thead>
          <tr style="background:#d9d9d9;">
            <th colspan="2" style="border:1px solid #aaa;padding:7px 12px;"></th>
            <th colspan="5" style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Paired Differences</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">t</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">df</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;background:#eaf4ff;">Sig. (2-tailed)</th>
          </tr>
          <tr style="background:#ececec;">
            <th colspan="2" style="border:1px solid #aaa;padding:7px 12px;"></th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Mean</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Std. Deviation</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Std. Error Mean</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">CI Lower 95%</th>
            <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">CI Upper 95%</th>
            <th colspan="3" style="border:1px solid #aaa;"></th>
          </tr>
        </thead>
        <tbody>{test_rows}</tbody>
      </table>
      <div style="font-size:11px;color:#444;margin-top:5px;font-style:italic;">α = 0.05 · Two-tailed · 95% Confidence Interval of the Difference</div>
    </div>""", unsafe_allow_html=True)

def render_spss_wilcoxon(pairs_data):
    ranks_rows = ""
    footnotes  = []
    abc    = "abcdefghijklmnopqrstuvwxyz"
    fn_idx = 0
    for pd_item in pairs_data:
        vn    = pd_item["var_name"]
        l_lbl = pd_item["light_lbl"]
        d_lbl = pd_item["dark_lbl"]
        labels   = ["","",""]
        hubungan = [f"{d_lbl} < {l_lbl}", f"{d_lbl} > {l_lbl}", f"{l_lbl} = {d_lbl}"]
        n_vals   = [pd_item['neg_n'], pd_item['pos_n'], pd_item['ties_n']]
        for i in range(3):
            current_letter = abc[fn_idx]
            if n_vals[i] > 0:
                labels[i] = f"<sup>{current_letter}</sup>"
                footnotes.append(f"{current_letter}. {hubungan[i]}")
            fn_idx += 1
        ranks_rows += f"""
        <tr>
            <td rowspan="4" style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#f5f5f5;vertical-align:middle;white-space:nowrap;">{vn}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;">Negative Ranks</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['neg_n']}{labels[0]}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['neg_mean']}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['neg_sum']}</td>
        </tr>
        <tr>
            <td style="border:1px solid #bbb;padding:7px 12px;">Positive Ranks</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['pos_n']}{labels[1]}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['pos_mean']}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['pos_sum']}</td>
        </tr>
        <tr>
            <td style="border:1px solid #bbb;padding:7px 12px;">Ties</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{pd_item['ties_n']}{labels[2]}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;"></td>
            <td style="border:1px solid #bbb;padding:7px 12px;"></td>
        </tr>
        <tr>
            <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;">Total</td>
            <td style="border:1px solid #bbb;padding:7px 12px;text-align:right;font-weight:600;">{pd_item['total_n']}</td>
            <td style="border:1px solid #bbb;padding:7px 12px;"></td>
            <td style="border:1px solid #bbb;padding:7px 12px;"></td>
        </tr>"""
    footnote_html = "<br>".join(footnotes) if footnotes else ""
    ranks_html = f"""
    <div style="margin:20px 0 8px 0;">
        <div style="font-weight:700;font-size:14px;border-bottom:2px solid #333;padding-bottom:4px;">Ranks</div>
        <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;">
            <thead><tr style="background:#d9d9d9;">
                <th colspan="2" style="border:1px solid #aaa;padding:7px 12px;"></th>
                <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">N</th>
                <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Mean Rank</th>
                <th style="border:1px solid #aaa;padding:7px 12px;text-align:center;">Sum of Ranks</th>
            </tr></thead>
            <tbody>{ranks_rows}</tbody>
        </table>
        <div style="font-size:11px;color:#444;margin-top:5px;font-style:italic;line-height:1.6;">{footnote_html}</div>
    </div>"""
    def get_z_superscript(pd_item):
        z     = pd_item["z_val"]
        neg_n = pd_item["neg_n"]
        pos_n = pd_item["pos_n"]
        if neg_n == 0 and pos_n == 0: return "", ""
        elif z <= 0: return "b","b. Based on negative ranks."
        else:        return "c","c. Based on positive ranks."
    test_stat_headers = "".join([
        f'<th style="border:1px solid #aaa;padding:7px 12px;text-align:center;font-size:12px;">{p["var_name"]}</th>'
        for p in pairs_data
    ])
    z_footnotes_dict = {}
    z_cells = ""
    for p in pairs_data:
        sup, note = get_z_superscript(p)
        if sup and sup not in z_footnotes_dict:
            z_footnotes_dict[sup] = note
        z_cells += f'<td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p["z_val"]:.3f}<sup>{sup}</sup></td>'
    p_cells = "".join([
        f'<td style="border:1px solid #bbb;padding:7px 12px;text-align:right;">{p["p_val"]:.3f}</td>'
        for p in pairs_data
    ])
    z_footnote_html = "<br>".join(z_footnotes_dict.values())
    test_stats_html = f"""
    <div style="margin:16px 0 24px 0;">
        <div style="font-weight:700;font-size:14px;border-bottom:2px solid #333;padding-bottom:4px;">Test Statistics<sup>a</sup></div>
        <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;">
            <thead><tr style="background:#d9d9d9;">
                <th style="border:1px solid #aaa;padding:7px 12px;text-align:left;"></th>
                {test_stat_headers}
            </tr></thead>
            <tbody>
                <tr>
                    <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#f5f5f5;">Z</td>
                    {z_cells}
                </tr>
                <tr>
                    <td style="border:1px solid #bbb;padding:7px 12px;font-weight:600;background:#eaf4ff;">Asymp. Sig. (2-tailed)</td>
                    {p_cells}
                </tr>
            </tbody>
        </table>
        <div style="font-size:11px;color:#444;margin-top:5px;font-style:italic;line-height:1.8;">
            a. Wilcoxon Signed Ranks Test<br>{z_footnote_html}
        </div>
    </div>"""
    st.markdown(ranks_html + test_stats_html, unsafe_allow_html=True)

def dataset_manager(df, expected_columns, save_path, title, filename_base):
    st.markdown('<div style="font-size:16px;font-weight:600;color:#1e293b;margin-bottom:8px;">Kelola Dataset</div>', unsafe_allow_html=True)
    action = st.radio("Pilih aksi", ["Export Dataset","Import Dataset"], horizontal=True, key=f"dataset_action_{filename_base}")
    if action == "Export Dataset":
        file_type = st.selectbox("Pilih format file", ["Excel (.xlsx)","CSV (.csv)","PDF (.pdf)"], key=f"file_type_{filename_base}")
        buffer = io.BytesIO()
        if file_type == "Excel (.xlsx)":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Dataset")
            buffer.seek(0)
            st.download_button("Download File", data=buffer, file_name=f"{filename_base}.xlsx")
        elif file_type == "CSV (.csv)":
            st.download_button("Download File", data=df.to_csv(index=False), file_name=f"{filename_base}.csv")
        elif file_type == "PDF (.pdf)":
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [Paragraph(title, styles["Title"]), Spacer(1,20)]
            data = [df.columns.tolist()] + df.values.tolist()
            table = Table(data)
            table.setStyle(TableStyle([
                ("BACKGROUND",(0,0),(-1,0),colors.darkblue),
                ("TEXTCOLOR",(0,0),(-1,0),colors.white),
                ("ALIGN",(0,0),(-1,-1),"CENTER"),
                ("GRID",(0,0),(-1,-1),0.5,colors.grey),
                ("FONTSIZE",(0,0),(-1,-1),8)
            ]))
            elements.append(table)
            doc.build(elements)
            buffer.seek(0)
            st.download_button("Download File", data=buffer, file_name=f"{filename_base}.pdf")
    elif action == "Import Dataset":
        import_key = f"import_status_{filename_base}"
        if import_key not in st.session_state:
            st.session_state[import_key] = None
        if st.session_state[import_key] == "success":
            st.success("Dataset berhasil diimport!")
            if st.button("Upload File Lain", key=f"reset_import_{filename_base}"):
                st.session_state[import_key] = None
                st.rerun()
            return
        uploaded_file = st.file_uploader("Upload file dataset", type=["xlsx","csv"], key=f"upload_{filename_base}")
        if uploaded_file is not None:
            df_new = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(".xlsx") else pd.read_csv(uploaded_file)
            if list(df_new.columns) != expected_columns:
                st.error("Struktur dataset tidak sesuai. Pastikan kolom file sama persis dengan template.")
            else:
                st.markdown("**Preview Data:**")
                st.dataframe(df_new.head(5), use_container_width=True)
                if st.button("Konfirmasi Import", type="primary", use_container_width=True, key=f"confirm_import_{filename_base}"):
                    try:
                        if "time_on_task" in filename_base:       save_data("data_tot", current_user, app, df_new)
                        elif "error_rate" in filename_base:        save_data("data_error", current_user, app, df_new)
                        elif "ueq_light" in filename_base:         save_ueq("data_ueq_light", current_user, app, df_new)
                        elif "ueq_dark" in filename_base:          save_ueq("data_ueq_dark", current_user, app, df_new)
                        elif "preferensi_positif" in filename_base: save_pref("data_pref_pos", current_user, app, df_new)
                        elif "preferensi_negatif" in filename_base: save_pref("data_pref_neg", current_user, app, df_new)
                        else: df_new.to_csv(save_path, index=False)
                        st.session_state[import_key] = "success"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")

def render_delete_button(file_path, label, columns, default_value=0, key_suffix=""):
    confirm_key = f"confirm_delete_{key_suffix}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False
    if not st.session_state[confirm_key]:
        if st.button(f"Hapus Data {label}", use_container_width=True, type="secondary", key=f"btn_delete_{key_suffix}"):
            st.session_state[confirm_key] = True
            st.rerun()
    else:
        st.warning(f"Yakin ingin menghapus semua data **{label}**? Tindakan ini tidak bisa dibatalkan.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Batal", use_container_width=True, key=f"cancel_delete_{key_suffix}"):
                st.session_state[confirm_key] = False
                st.rerun()
        with c2:
            if st.button("Ya, Hapus", type="primary", use_container_width=True, key=f"confirm_yes_{key_suffix}"):
                try:
                    SUPABASE_URL = st.secrets["SUPABASE_URL"]
                    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
                    headers = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=minimal"}
                    table_map = {"tot":"data_tot","error":"data_error","ueq_light":"data_ueq_light","ueq_dark":"data_ueq_dark","pref_pos":"data_pref_pos","pref_neg":"data_pref_neg"}
                    if key_suffix in table_map:
                        requests.delete(f"{SUPABASE_URL}/rest/v1/{table_map[key_suffix]}?username=eq.{current_user}&app=eq.{app}", headers=headers)
                    st.session_state[confirm_key] = False
                    st.success(f"Data {label} berhasil dihapus!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menghapus: {e}")

def create_donut_chart(data_dict, chart_colors):
    if not data_dict: return None
    fig = go.Figure(data=[go.Pie(
        labels=list(data_dict.keys()), values=list(data_dict.values()),
        hole=.6, marker=dict(colors=chart_colors, line=dict(color='#FFFFFF',width=2)),
        textinfo='none', showlegend=False, hoverinfo='label+percent'
    )])
    fig.update_layout(margin=dict(t=0,b=0,l=0,r=0), height=160,
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# ======================
# AUTH
# ======================
if not render_auth_page():
    st.stop()

current_user = st.session_state.get("current_user", "default")
USER_DIR     = os.path.join(BASE_DIR, "userdata", current_user)

if "last_user" not in st.session_state or st.session_state["last_user"] != current_user:
    st.session_state["last_user"] = current_user
    st.session_state["app_list"]  = load_app_list(current_user)

# ======================
# SIDEBAR MODERN
# ======================
with st.sidebar:
    st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)

    # Avatar & user card
    initials = current_user[:2].upper() if current_user else "UX"
    st.markdown(f"""
    <div class="sb-avatar-card">
        <div class="sb-avatar">{initials}</div>
        <div class="sb-user-info">
            <span class="sb-user-role">Researcher</span>
            <span class="sb-user-name">{current_user}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Research Object
    st.markdown('<span class="sb-section-label">Research Object</span>', unsafe_allow_html=True)
    app = st.selectbox("Aplikasi", st.session_state.app_list, label_visibility="collapsed", key="app_select")

    with st.expander("⚙️ Manage Applications", expanded=False):
        if st.session_state.get("app_added"):
            st.success(f"✓ '{st.session_state.app_added}' ditambahkan!")
            st.session_state["app_added"] = None
        if st.session_state.get("app_deleted"):
            st.warning(f"✓ '{st.session_state.app_deleted}' dihapus!")
            st.session_state["app_deleted"] = None
        if "input_key" not in st.session_state:
            st.session_state["input_key"] = 0
        new_app = st.text_input("Nama Aplikasi", placeholder="Contoh: Instagram", key=f"new_app_input_{st.session_state['input_key']}")
        if st.button("+ Tambah", use_container_width=True, key="btn_add_app"):
            if new_app and new_app.strip() not in st.session_state.app_list:
                nama = new_app.strip()
                st.session_state.app_list.append(nama)
                save_app_list(current_user, st.session_state.app_list)
                st.session_state["app_added"] = nama
                st.session_state["input_key"] += 1
                st.rerun()
            elif new_app and new_app.strip() in st.session_state.app_list:
                st.error("Sudah ada!")
        if st.session_state.app_list:
            st.markdown("---")
            app_delete = st.selectbox("Hapus:", st.session_state.app_list, key="del_select")
            if st.button("🗑 Hapus", use_container_width=True, key="btn_del_app"):
                nama_del = app_delete
                st.session_state.app_list.remove(app_delete)
                save_app_list(current_user, st.session_state.app_list)
                st.session_state["app_deleted"] = nama_del
                st.rerun()

    # Main Navigation
    st.markdown('<span class="sb-section-label">Main</span>', unsafe_allow_html=True)
    MENU_ITEMS = [
        ("🏠", "Home"), ("📊", "Overview"), ("⏱", "Time on Task"),
        ("❌", "Error Rate"), ("📋", "UEQ Analysis"), ("❤️", "Preferensi Responden"),
    ]
    for icon_nav, label in MENU_ITEMS:
        if st.button(f"{icon_nav}  {label}", key=f"nav_{label}", use_container_width=True):
            st.session_state["menu"] = label
            st.rerun()

    # Settings
    st.markdown('<span class="sb-section-label">Settings</span>', unsafe_allow_html=True)
    if st.button("⚙️  Settings", key="nav_settings", use_container_width=True):
        st.session_state["menu"] = "Settings"
        st.rerun()

    # Study Parameters
    st.markdown('<span class="sb-section-label">Study Parameters</span>', unsafe_allow_html=True)
    n = st.number_input("Sample Size (N)", min_value=1, max_value=100, value=25, help="Jumlah responden")

    # Active App Card
    st.markdown(f"""
    <div class="sb-app-card">
        <div class="sb-app-card-label">Active Study</div>
        <div class="sb-app-card-name">{app if app else "—"}</div>
        <div class="sb-app-card-meta">N = {n} responden · 3 tasks</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("Reset All Data", use_container_width=True, type="secondary", key="btn_reset_split"):
        st.session_state["show_reset_confirm"] = True
    st.markdown("<div style='margin-top:6px;'></div>", unsafe_allow_html=True)
    if st.button("Logout", use_container_width=True, type="primary", key="btn_logout"):
        st.session_state["show_logout_confirm"] = True

# Ambil menu dari session_state
menu = st.session_state.get("menu", "Home")

# ======================
# DIALOG RESET & LOGOUT
# ======================
@st.dialog("Konfirmasi Reset Data")
def reset_dialog():
    st.markdown("Yakin ingin menghapus **semua data** akun **{}**?".format(st.session_state.get("current_user","")))
    st.caption("Tindakan ini tidak dapat dibatalkan.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Batal", use_container_width=True, key="dialog_reset_batal"):
            st.session_state["show_reset_confirm"] = False
            st.rerun()
    with col2:
        if st.button("Ya, Hapus", use_container_width=True, type="primary", key="dialog_reset_hapus"):
            tables = ["data_tot","data_error","data_ueq_light","data_ueq_dark","data_pref_pos","data_pref_neg","app_list"]
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
            headers = {"apikey":SUPABASE_KEY,"Authorization":f"Bearer {SUPABASE_KEY}","Content-Type":"application/json","Prefer":"return=minimal"}
            for table in tables:
                requests.delete(f"{SUPABASE_URL}/rest/v1/{table}?username=eq.{st.session_state.get('current_user','')}", headers=headers)
            st.session_state["app_list"] = []
            st.session_state["show_reset_confirm"] = False
            st.rerun()

if st.session_state.get("show_reset_confirm"):
    reset_dialog()

@st.dialog("Konfirmasi Logout")
def logout_dialog():
    st.markdown("Yakin ingin keluar dari akun **{}**?".format(st.session_state.get("current_user","")))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Batal", use_container_width=True, key="dialog_batal"):
            st.session_state["show_logout_confirm"] = False
            st.rerun()
    with col2:
        if st.button("Ya, Logout", use_container_width=True, type="primary", key="dialog_logout"):
            logout()

if st.session_state.get("show_logout_confirm"):
    logout_dialog()

# ======================
# PATH REFERENSI
# ======================
file_tot       = ""
file_error     = ""
file_ueq_light = ""
file_ueq_dark  = ""

# ======================
# HELPER: ADJUST DATAFRAME
# ======================
def adjust_dataframe(df, n):
    if len(df) < n:
        new_rows = pd.DataFrame({"Responden": [f"R{i+1}" for i in range(len(df), n)]})
        df = pd.concat([df, new_rows], ignore_index=True)
    if len(df) > n:
        df = df.iloc[:n]
    df["Responden"] = [f"R{i+1}" for i in range(len(df))]
    return df

# ======================
# LOAD DATA
# ======================
columns = ["Responden","Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]

df_tot = load_data("data_tot", current_user, app)
if df_tot.empty: df_tot = pd.DataFrame(columns=columns)
df_tot = adjust_dataframe(df_tot, n)
for c in columns[1:]:
    if c not in df_tot: df_tot[c] = 0

df_error = load_data("data_error", current_user, app)
if df_error.empty: df_error = pd.DataFrame(columns=columns)
df_error = adjust_dataframe(df_error, n)
for c in columns[1:]:
    if c not in df_error: df_error[c] = 0

scales = {
    "Daya tarik": [1,12,14,16,24,25], "Kejelasan": [2,4,13,21],
    "Efisiensi": [9,20,22,23], "Ketepatan": [8,11,17,19],
    "Stimulasi": [5,6,7,18], "Kebaruan": [3,10,15,26]
}
items = [f"I{i}" for i in range(1,27)]

light_df = load_ueq("data_ueq_light", current_user, app, n)
dark_df  = load_ueq("data_ueq_dark",  current_user, app, n)
light_df = light_df[items].apply(pd.to_numeric, errors="coerce")
dark_df  = dark_df[items].apply(pd.to_numeric, errors="coerce")

# ======================
# UEQ FUNCTIONS
# ======================
def preprocess_ueq(df):
    df = df.copy().apply(pd.to_numeric, errors='coerce')
    df_t = df - 4
    for i in [3,4,5,9,10,12,17,18,19,21,23,24,25]:
        col = f"I{i}"
        if col in df_t.columns: df_t[col] = -df_t[col]
    return df_t

def calculate_ueq_tool_style(df):
    df_proc = preprocess_ueq(df)
    scales_map = {
        "Daya tarik":[1,12,14,16,24,25],"Kejelasan":[2,4,13,21],
        "Efisiensi":[9,20,22,23],"Ketepatan":[8,11,17,19],
        "Stimulasi":[5,6,7,18],"Kebaruan":[3,10,15,26]
    }
    results = []
    for scale_name, item_indices in scales_map.items():
        cols = [f"I{i}" for i in item_indices]
        per_person = df_proc[cols].mean(axis=1)
        results.append({"Scale":scale_name,"Mean":round(per_person.mean(),6),"Variance":round(per_person.var(),6)})
    return pd.DataFrame(results)

def paired_test_spss(light, dark):
    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    diff  = np.array(light) - np.array(dark)
    mean  = np.mean(diff)
    std   = np.std(diff, ddof=1)
    n_    = len(diff)
    se    = std / np.sqrt(n_)
    t, p_two = stats.ttest_rel(light, dark)
    df_   = n_ - 1
    p_one = p_two / 2
    ci_low, ci_up = stats.t.interval(0.95, df_, loc=mean, scale=se)
    return mean, std, se, ci_low, ci_up, t, df_, p_one, p_two

# ======================
# MENU: HOME
# ======================
if menu == "Home":
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#4f46e5,#6366f1);padding:40px;border-radius:20px;
    color:white;margin-bottom:30px;box-shadow:0 10px 15px -3px rgba(0,0,0,0.1);">
        <div style="font-size:28px;font-weight:800;letter-spacing:-0.5px;">
            Dashboard Analitik UX — Light Mode vs Dark Mode
        </div>
        <div style="font-size:14px;margin-top:12px;max-width:700px;line-height:1.7;opacity:0.9;">
            Platform analitik berbasis web untuk penelitian perbandingan pengalaman pengguna (UX) antara
            Light Mode dan Dark Mode pada aplikasi mobile.
        </div>
        <div style="margin-top:20px;display:flex;gap:15px;">
            <div style="background:rgba(255,255,255,0.2);padding:8px 15px;border-radius:30px;font-size:11px;font-weight:600;">
                Current Object: {app if app else "None"}
            </div>
            <div style="background:rgba(255,255,255,0.2);padding:8px 15px;border-radius:30px;font-size:11px;font-weight:600;">
                Sample Size: {n}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Tentang Platform")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="card">
            <div style="font-size:14px;font-weight:700;color:#4f46e5;margin-bottom:10px;">Analisis Statistik Otomatis</div>
            <div style="font-size:12px;line-height:1.6;color:{text_main};">
                Sistem secara otomatis melakukan uji normalitas Shapiro-Wilk dan menentukan metode uji
                yang sesuai — Paired T-Test (parametrik) atau Wilcoxon Signed Ranks Test (non-parametrik).
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="card">
            <div style="font-size:14px;font-weight:700;color:#4f46e5;margin-bottom:10px;">Interactivity & Visual Insight</div>
            <div style="font-size:12px;line-height:1.6;color:{text_main};">
                Menyediakan grafik interaktif, tabel perbandingan, serta kesimpulan otomatis untuk
                mempermudah interpretasi perbedaan UX antara Light Mode dan Dark Mode.
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("### Modul Analisis Terintegrasi")
    col1, col2, col3, col4 = st.columns(4)
    modules = [
        ("⏱ Time on Task", "Mengukur efisiensi waktu penyelesaian tugas (detik)."),
        ("❌ Error Rate",   "Mengukur tingkat kesalahan pengguna saat menyelesaikan tugas (%)."),
        ("📋 UEQ Standard", "Evaluasi 6 dimensi UX: Daya Tarik, Kejelasan, Efisiensi, Ketepatan, Stimulasi, Kebaruan."),
        ("❤️ Preference",   "Analisis kecenderungan pilihan pengguna pada 6 aspek via Mean Preference Analysis.")
    ]
    for col, (title, desc) in zip([col1,col2,col3,col4], modules):
        col.markdown(f"""
        <div class="card" style="text-align:center;">
            <div style="font-size:13px;font-weight:800;color:{text_main};margin-bottom:5px;">{title}</div>
            <div style="font-size:10px;color:{text_soft};">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.info(f"""
    Panduan Penggunaan:
    1. Pilih atau tambahkan objek penelitian melalui sidebar — saat ini: {app}.
    2. Input data Time on Task dan Error Rate per responden.
    3. Input data kuesioner UEQ (Light Mode & Dark Mode).
    4. Input data preferensi responden.
    5. Lihat ringkasan pada menu Overview.
    """)

# ======================
# MENU: OVERVIEW
# ======================
if menu == "Overview":
    avg_light_tot = df_tot[["Light_T1","Light_T2","Light_T3"]].mean().mean()
    avg_dark_tot  = df_tot[["Dark_T1","Dark_T2","Dark_T3"]].mean().mean()
    avg_light_err = df_error[["Light_T1","Light_T2","Light_T3"]].mean().mean()
    avg_dark_err  = df_error[["Dark_T1","Dark_T2","Dark_T3"]].mean().mean()
    light_ueq_mean = calculate_ueq_tool_style(light_df)["Mean"].mean()
    dark_ueq_mean  = calculate_ueq_tool_style(dark_df)["Mean"].mean()

    aspek = {
        "Readability":["R1","R2","R3","R4"], "Eye Strain":["ES1","ES2","ES3","ES4"],
        "Usability":["U1","U2","U3","U4"],   "Battery":["B1","B2","B3","B4"],
        "Efficiency":["E1","E2","E3","E4"],  "Aesthetic":["ED1","ED2","ED3","ED4"],
    }
    aspek_result = []
    df_pos_ov = load_pref("data_pref_pos", current_user, app, n).fillna(0)
    df_neg_ov = load_pref("data_pref_neg", current_user, app, n).fillna(0)
    first_cols = list(aspek.values())[0]
    ec = [c for c in first_cols if c in df_pos_ov.columns]
    if ec and df_pos_ov[ec].sum().sum() > 0:
        for a, cols in aspek.items():
            pos_val = df_pos_ov[cols].mean().mean() if all(c in df_pos_ov.columns for c in cols) else np.nan
            neg_val = (8 - df_neg_ov[cols]).mean().mean() if all(c in df_neg_ov.columns for c in cols) else np.nan
            if pd.isna(pos_val) or pd.isna(neg_val): continue
            aspek_result.append("Light Mode" if (pos_val+neg_val)/2 < 4 else "Dark Mode")

    light_pref = aspek_result.count("Light Mode")
    dark_pref  = aspek_result.count("Dark Mode")
    best_pref  = "Light Mode" if light_pref >= dark_pref else "Dark Mode"

    st.markdown(f"""
    <div style="margin-bottom:28px;">
        <div style="font-size:24px;font-weight:700;color:#1E293B;letter-spacing:-0.3px;">Research Overview</div>
        <div style="font-size:13px;color:#64748B;margin-top:3px;">{app} &nbsp;·&nbsp; {n} responden &nbsp;·&nbsp; Within-Subject Design</div>
    </div>
    """, unsafe_allow_html=True)

    def _winner_badge(wins):
        if wins: return '<span style="font-size:9px;font-weight:600;background:#EEF2FF;color:#4338CA;padding:2px 7px;border-radius:20px;margin-left:5px;vertical-align:middle;">BEST</span>'
        return ""

    def _kpi(title, l_val, d_val, unit, lower_is_better=False):
        l_wins = (l_val < d_val) if lower_is_better else (l_val > d_val)
        d_wins = not l_wins
        return f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:20px 18px;height:100%;">
            <div style="font-size:10px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:16px;">{title}</div>
            <div style="display:flex;flex-direction:column;gap:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:12px;color:#64748B;display:flex;align-items:center;gap:6px;">
                        <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#6366F1;flex-shrink:0;"></span>Light
                    </div>
                    <div style="font-size:16px;font-weight:700;color:#4338CA;">{round(l_val,2)}{unit}{_winner_badge(l_wins)}</div>
                </div>
                <div style="height:1px;background:#F1F5F9;"></div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div style="font-size:12px;color:#64748B;display:flex;align-items:center;gap:6px;">
                        <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:#334155;flex-shrink:0;"></span>Dark
                    </div>
                    <div style="font-size:16px;font-weight:700;color:#334155;">{round(d_val,2)}{unit}{_winner_badge(d_wins)}</div>
                </div>
            </div>
        </div>"""

    col_a,col_b,col_c,col_d,col_e = st.columns(5)
    with col_a: st.markdown(_kpi("UEQ Score", light_ueq_mean, dark_ueq_mean, ""), unsafe_allow_html=True)
    with col_b: st.markdown(_kpi("Time on Task", avg_light_tot, avg_dark_tot, "s", lower_is_better=True), unsafe_allow_html=True)
    with col_c: st.markdown(_kpi("Error Rate", avg_light_err, avg_dark_err, "%", lower_is_better=True), unsafe_allow_html=True)
    with col_d:
        pref_color = "#4338CA" if best_pref=="Light Mode" else "#1E293B"
        pref_bg    = "#EEF2FF" if best_pref=="Light Mode" else "#F1F5F9"
        st.markdown(f"""
        <div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:20px 18px;height:100%;">
            <div style="font-size:10px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:16px;">Best Preference</div>
            <div style="font-size:18px;font-weight:700;color:{pref_color};margin-bottom:8px;">{best_pref}</div>
            <div style="display:inline-block;font-size:10px;font-weight:600;background:{pref_bg};color:{pref_color};padding:3px 10px;border-radius:20px;">
                {light_pref} Light &nbsp;·&nbsp; {dark_pref} Dark
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_e:
        st.markdown(f"""
        <div style="background:#6366F1;border-radius:14px;padding:20px 18px;height:100%;color:white;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:16px;opacity:0.7;">Objek Studi</div>
            <div style="font-size:20px;font-weight:700;margin-bottom:6px;">{app}</div>
            <div style="font-size:11px;opacity:0.7;">N = {n} responden · 3 tugas per mode</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
    st.markdown('<div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:12px;">Perbandingan Metrik</div>', unsafe_allow_html=True)

    col_g1,col_g2,col_g3 = st.columns(3)
    def _bar_chart(title, l_val, d_val, unit):
        fig = go.Figure()
        fig.add_trace(go.Bar(x=["Light","Dark"], y=[l_val,d_val],
            marker_color=["#6366F1","#334155"],
            text=[f"{round(l_val,1)}{unit}",f"{round(d_val,1)}{unit}"],
            textposition="outside", width=0.45))
        fig.update_layout(
            title=dict(text=title,font=dict(size=12,color="#64748B"),x=0,xanchor="left"),
            yaxis=dict(showgrid=True,gridcolor="#F1F5F9",zeroline=False,tickfont=dict(size=10,color="#94A3B8"),showline=False),
            xaxis=dict(tickfont=dict(size=11,color="#374151"),showline=False),
            plot_bgcolor="white",paper_bgcolor="white",
            margin=dict(t=36,b=16,l=8,r=8), height=220, showlegend=False)
        return fig
    with col_g1: st.plotly_chart(_bar_chart("Time on Task (detik)", avg_light_tot, avg_dark_tot, "s"), use_container_width=True, config={"displayModeBar":False})
    with col_g2: st.plotly_chart(_bar_chart("Error Rate (%)", avg_light_err, avg_dark_err, "%"), use_container_width=True, config={"displayModeBar":False})
    with col_g3: st.plotly_chart(_bar_chart("UEQ Score", light_ueq_mean, dark_ueq_mean, ""), use_container_width=True, config={"displayModeBar":False})

# ======================
# MENU: TIME ON TASK
# ======================
if menu == "Time on Task":
    st.markdown('<div style="font-size:28px;font-weight:700;color:#1e293b;margin-bottom:10px;">Time on Task Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;color:#6b7280;">Uji normalitas Shapiro-Wilk otomatis · Rekomendasi metode: Paired T-Test atau Wilcoxon Signed Ranks Test</div>', unsafe_allow_html=True)

    with st.expander("Dataset Manager", expanded=False):
        dataset_manager(df_tot, columns, file_tot, "Dataset Time on Task", f"time_on_task_{app}")

    st.markdown("### Dataset Input")
    df_edit = st.data_editor(df_tot, key="tot_editor", use_container_width=True, column_config={
        "Responden": st.column_config.TextColumn("Responden"),
        "Light_T1": st.column_config.NumberColumn("Light T1 (detik)", min_value=0, step=0.1),
        "Light_T2": st.column_config.NumberColumn("Light T2 (detik)", min_value=0, step=0.1),
        "Light_T3": st.column_config.NumberColumn("Light T3 (detik)", min_value=0, step=0.1),
        "Dark_T1":  st.column_config.NumberColumn("Dark T1 (detik)",  min_value=0, step=0.1),
        "Dark_T2":  st.column_config.NumberColumn("Dark T2 (detik)",  min_value=0, step=0.1),
        "Dark_T3":  st.column_config.NumberColumn("Dark T3 (detik)",  min_value=0, step=0.1),
    })

    if st.button("Simpan Data Time on Task", type="primary", use_container_width=True):
        save_data("data_tot", current_user, app, df_edit)
        st.session_state["saved_tot"] = True
        st.rerun()
    if st.session_state.get("saved_tot"):
        st.success("Data Time on Task berhasil disimpan!")
        st.session_state["saved_tot"] = False

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    render_delete_button(file_path=file_tot, label="Time on Task", columns=columns[1:], default_value=0, key_suffix="tot")

    data_kosong = df_edit[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    if st.button("ANALISIS DATA", type="secondary", key="analyze_tot"):
        if data_kosong:
            st.warning("Data masih kosong.")
            st.stop()
        st.markdown("---")
        light_per_user = df_edit[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
        dark_per_user  = df_edit[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)

        st.markdown("### Uji Normalitas Selisih (Dark − Light)")
        norm_results = []
        for i in range(1,4):
            norm_results.append(shapiro_and_ks(df_edit[f"Light_T{i}"], df_edit[f"Dark_T{i}"], label=f"Dark_T{i} − Light_T{i}"))
        norm_results.append(shapiro_and_ks(light_per_user, dark_per_user, label="Dark (mean) − Light (mean)"))
        render_normality_table(norm_results)
        rec = render_normality_recommendation(norm_results)

        st.markdown("#### Pilih Metode Uji Statistik")
        default_idx = 0 if rec == "t-test" else 1
        method_choice = st.radio("Metode:", ["Paired Samples T-Test (Parametrik)","Wilcoxon Signed Ranks Test (Non-Parametrik)"], index=default_idx, horizontal=True, key="method_choice_tot")
        use_ttest = method_choice.startswith("Paired")

        st.markdown("---")
        st.markdown("### Overall Metrics")
        avg_l = light_per_user.mean()
        avg_d = dark_per_user.mean()
        task_avgs = pd.DataFrame({"Task":["T1","T2","T3"],"Light Mode":[df_edit[f"Light_T{i}"].mean() for i in range(1,4)],"Dark Mode":[df_edit[f"Dark_T{i}"].mean() for i in range(1,4)]})
        col1,col2,col3 = st.columns(3)
        with col1:
            better = "Light" if avg_l < avg_d else "Dark"
            st.metric("Lowest Time on Task", better, f"{abs(avg_l-avg_d):.1f}s", delta_color="normal" if avg_l < avg_d else "inverse")
        with col2: st.metric("Light Mode Avg", f"{avg_l:.1f}s")
        with col3: st.metric("Dark Mode Avg",  f"{avg_d:.1f}s")
        st.dataframe(task_avgs.round(2), use_container_width=True)

        p_values, z_or_t_values = [], []
        if use_ttest:
            st.markdown("### Paired Samples T-Test — Per Task")
            pairs_per_task = []
            for i in range(1,4):
                item = compute_paired_ttest_pair(pd.to_numeric(df_edit[f"Light_T{i}"],errors="coerce"), pd.to_numeric(df_edit[f"Dark_T{i}"],errors="coerce"), f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item); p_values.append(item["p_two"]); z_or_t_values.append(item["t"])
            render_spss_paired_ttest(pairs_per_task)
            st.markdown("### Overall Paired T-Test (Mean per User)")
            overall_pair = compute_paired_ttest_pair(light_per_user, dark_per_user, "Light (mean)", "Dark (mean)")
            render_spss_paired_ttest([overall_pair])
            overall_stat, overall_p, stat_label = overall_pair["t"], overall_pair["p_two"], "t"
        else:
            st.markdown("### Wilcoxon Signed Ranks Test — Per Task")
            pairs_per_task = []
            for i in range(1,4):
                item = compute_wilcoxon_pair(pd.to_numeric(df_edit[f"Light_T{i}"],errors="coerce"), pd.to_numeric(df_edit[f"Dark_T{i}"],errors="coerce"), f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item); p_values.append(item["p_val"]); z_or_t_values.append(item["z_val"])
            render_spss_wilcoxon(pairs_per_task)
            st.markdown("### Overall Wilcoxon Test (Mean per User)")
            overall_item = compute_wilcoxon_pair(light_per_user, dark_per_user, "Light (mean)", "Dark (mean)")
            render_spss_wilcoxon([overall_item])
            overall_stat, overall_p, stat_label = overall_item["z_val"], overall_item["p_val"], "Z"

        st.markdown("### Visual Comparison")
        fig, ((ax1,ax2),(ax3,ax4)) = plt.subplots(2,2,figsize=(15,10))
        fig.suptitle("Time on Task Analysis", fontsize=16, fontweight='bold')
        x, width = np.arange(3), 0.35
        ax1.bar(x-width/2, task_avgs["Light Mode"], width, label='Light', color="#6366f1", alpha=0.8)
        ax1.bar(x+width/2, task_avgs["Dark Mode"],  width, label='Dark',  color="#1e293b", alpha=0.8)
        ax1.set_title("Per Task Comparison"); ax1.set_xticks(x); ax1.set_xticklabels(["T1","T2","T3"])
        ax1.set_ylabel("Time (detik)"); ax1.legend(); ax1.grid(True, alpha=0.3)
        ax2.hist(light_per_user.dropna(), bins=15, alpha=0.7, color="#6366f1", label='Light', density=True)
        ax2.hist(dark_per_user.dropna(),  bins=15, alpha=0.7, color="#1e293b", label='Dark',  density=True)
        ax2.set_title("Distribution"); ax2.legend(); ax2.grid(True, alpha=0.3)
        colors_sig = ["#10b981" if p < 0.05 else "#ef4444" for p in p_values]
        ax3.bar([f"T{i}" for i in range(1,4)], z_or_t_values, color=colors_sig, alpha=0.8)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title("t-values" if use_ttest else "Z-Scores"); ax3.grid(True, alpha=0.3)
        ax4.bar([f"T{i}" for i in range(1,4)], p_values, color=colors_sig, alpha=0.8)
        ax4.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='α=0.05')
        ax4.set_title("P-Values"); ax4.set_ylim(0, max(0.3, max(p_values)*1.1)); ax4.legend(); ax4.grid(True, alpha=0.3)
        plt.tight_layout(); st.pyplot(fig)

        sig_tasks = sum(p < 0.05 for p in p_values)
        overall_sig = "Signifikan" if overall_p < 0.05 else "Tidak Signifikan"
        method_name = "Paired T-Test" if use_ttest else "Wilcoxon Signed Ranks"
        st.markdown("### Statistical Summary")
        st.markdown(f"""
        <div style="background:#f8fafc;padding:24px;border-radius:12px;border-left:4px solid #6366f1;">
          <div style="font-size:16px;font-weight:700;color:{text_main};margin-bottom:12px;">Overall Findings</div>
          <ul style="font-size:14px;color:#374151;line-height:1.8;margin:0;">
            <li>Metode: <b>{method_name}</b></li>
            <li><b>{sig_tasks}/3 tasks</b> menunjukkan perbedaan signifikan (p &lt; 0.05)</li>
            <li><b>Overall:</b> {stat_label}={overall_stat:.3f}, p={overall_p:.3f} — {overall_sig}</li>
            <li>Mean Light: <b>{avg_l:.1f}s</b> | Mean Dark: <b>{avg_d:.1f}s</b></li>
            <li>{'Light Mode lebih cepat' if avg_l < avg_d else 'Dark Mode lebih cepat'} secara deskriptif</li>
          </ul>
        </div>""", unsafe_allow_html=True)

# ======================
# MENU: ERROR RATE
# ======================
if menu == "Error Rate":
    st.markdown('<div style="font-size:28px;font-weight:700;color:#1e293b;margin-bottom:10px;">Error Rate Analysis</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:14px;color:#6b7280;">Uji normalitas Shapiro-Wilk otomatis · Rekomendasi metode: Paired T-Test atau Wilcoxon Signed Ranks Test</div>', unsafe_allow_html=True)

    with st.expander("Dataset Manager", expanded=False):
        dataset_manager(df_error, columns, file_error, "Dataset Error Rate", f"error_rate_{app}")

    st.markdown("### Dataset Input")
    df_edit = st.data_editor(df_error, key="error_editor", use_container_width=True, column_config={
        "Responden": st.column_config.TextColumn("Responden"),
        "Light_T1": st.column_config.NumberColumn("Light T1 (error %)", min_value=0, max_value=100, step=0.1, format="%.1f%%"),
        "Light_T2": st.column_config.NumberColumn("Light T2 (error %)", min_value=0, max_value=100, step=0.1, format="%.1f%%"),
        "Light_T3": st.column_config.NumberColumn("Light T3 (error %)", min_value=0, max_value=100, step=0.1, format="%.1f%%"),
        "Dark_T1":  st.column_config.NumberColumn("Dark T1 (error %)",  min_value=0, max_value=100, step=0.1, format="%.1f%%"),
        "Dark_T2":  st.column_config.NumberColumn("Dark T2 (error %)",  min_value=0, max_value=100, step=0.1, format="%.1f%%"),
        "Dark_T3":  st.column_config.NumberColumn("Dark T3 (error %)",  min_value=0, max_value=100, step=0.1, format="%.1f%%"),
    })

    if st.button("Simpan Data Error Rate", type="primary", use_container_width=True):
        save_data("data_error", current_user, app, df_edit)
        st.session_state["saved_error"] = True
        st.rerun()
    if st.session_state.get("saved_error"):
        st.success("Data Error Rate berhasil disimpan!")
        st.session_state["saved_error"] = False

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    render_delete_button(file_path=file_error, label="Error Rate", columns=columns[1:], default_value=0, key_suffix="error")

    data_kosong_err = df_edit[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    if st.button("ANALISIS DATA", type="secondary", key="analyze_error_rate"):
        if data_kosong_err:
            st.warning("Data masih kosong.")
            st.stop()
        st.markdown("---")
        light_per_user = df_edit[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
        dark_per_user  = df_edit[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)

        st.markdown("### Uji Normalitas Selisih (Dark − Light)")
        norm_results = []
        for i in range(1,4):
            norm_results.append(shapiro_and_ks(df_edit[f"Light_T{i}"], df_edit[f"Dark_T{i}"], label=f"Dark_T{i} − Light_T{i}"))
        norm_results.append(shapiro_and_ks(light_per_user, dark_per_user, label="Dark (mean) − Light (mean)"))
        render_normality_table(norm_results)
        rec = render_normality_recommendation(norm_results)

        st.markdown("#### Pilih Metode Uji Statistik")
        default_idx = 0 if rec == "t-test" else 1
        method_choice = st.radio("Metode:", ["Paired Samples T-Test (Parametrik)","Wilcoxon Signed Ranks Test (Non-Parametrik)"], index=default_idx, horizontal=True, key="method_choice_error")
        use_ttest = method_choice.startswith("Paired")

        st.markdown("---")
        st.markdown("### Overall Metrics")
        avg_l = light_per_user.mean()
        avg_d = dark_per_user.mean()
        task_avgs = pd.DataFrame({"Task":["T1","T2","T3"],"Light Mode":[df_edit[f"Light_T{i}"].mean() for i in range(1,4)],"Dark Mode":[df_edit[f"Dark_T{i}"].mean() for i in range(1,4)]})
        col1,col2,col3 = st.columns(3)
        with col1:
            better = "Light" if avg_l < avg_d else "Dark"
            st.metric("Lowest Error Rate", better, f"{abs(avg_l-avg_d):.1f}%", delta_color="normal" if avg_l < avg_d else "inverse")
        with col2: st.metric("Light Mode Avg", f"{avg_l:.1f}%")
        with col3: st.metric("Dark Mode Avg",  f"{avg_d:.1f}%")
        st.dataframe(task_avgs.round(2), use_container_width=True)

        p_values, z_or_t_values = [], []
        if use_ttest:
            st.markdown("### Paired Samples T-Test — Per Task")
            pairs_per_task = []
            for i in range(1,4):
                item = compute_paired_ttest_pair(pd.to_numeric(df_edit[f"Light_T{i}"],errors="coerce"), pd.to_numeric(df_edit[f"Dark_T{i}"],errors="coerce"), f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item); p_values.append(item["p_two"]); z_or_t_values.append(item["t"])
            render_spss_paired_ttest(pairs_per_task)
            st.markdown("### Overall Paired T-Test (Mean per User)")
            overall_pair = compute_paired_ttest_pair(light_per_user, dark_per_user, "Light (mean)", "Dark (mean)")
            render_spss_paired_ttest([overall_pair])
            overall_stat, overall_p, stat_label = overall_pair["t"], overall_pair["p_two"], "t"
        else:
            st.markdown("### Wilcoxon Signed Ranks Test — Per Task")
            pairs_per_task = []
            for i in range(1,4):
                item = compute_wilcoxon_pair(pd.to_numeric(df_edit[f"Light_T{i}"],errors="coerce"), pd.to_numeric(df_edit[f"Dark_T{i}"],errors="coerce"), f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item); p_values.append(item["p_val"]); z_or_t_values.append(item["z_val"])
            render_spss_wilcoxon(pairs_per_task)
            st.markdown("### Overall Wilcoxon Test (Mean per User)")
            overall_item = compute_wilcoxon_pair(light_per_user, dark_per_user, "Light (mean)", "Dark (mean)")
            render_spss_wilcoxon([overall_item])
            overall_stat, overall_p, stat_label = overall_item["z_val"], overall_item["p_val"], "Z"

        st.markdown("### Visual Comparison")
        fig, ((ax1,ax2),(ax3,ax4)) = plt.subplots(2,2,figsize=(15,10))
        fig.suptitle("Error Rate Analysis", fontsize=16, fontweight='bold')
        x, width = np.arange(3), 0.35
        ax1.bar(x-width/2, task_avgs["Light Mode"], width, label='Light', color="#6366f1", alpha=0.8)
        ax1.bar(x+width/2, task_avgs["Dark Mode"],  width, label='Dark',  color="#1e293b", alpha=0.8)
        ax1.set_title("Per Task Comparison"); ax1.set_xticks(x); ax1.set_xticklabels(["T1","T2","T3"])
        ax1.set_ylabel("Error Rate (%)"); ax1.legend(); ax1.grid(True, alpha=0.3)
        ax2.hist(light_per_user.dropna(), bins=15, alpha=0.7, color="#6366f1", label='Light', density=True)
        ax2.hist(dark_per_user.dropna(),  bins=15, alpha=0.7, color="#1e293b", label='Dark',  density=True)
        ax2.set_title("Distribution"); ax2.legend(); ax2.grid(True, alpha=0.3)
        colors_sig = ["#10b981" if p < 0.05 else "#ef4444" for p in p_values]
        ax3.bar([f"T{i}" for i in range(1,4)], z_or_t_values, color=colors_sig, alpha=0.8)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title("t-values" if use_ttest else "Z-Scores"); ax3.grid(True, alpha=0.3)
        ax4.bar([f"T{i}" for i in range(1,4)], p_values, color=colors_sig, alpha=0.8)
        ax4.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='α=0.05')
        ax4.set_title("P-Values"); ax4.set_ylim(0, max(0.3, max(p_values)*1.1)); ax4.legend(); ax4.grid(True, alpha=0.3)
        plt.tight_layout(); st.pyplot(fig)

        sig_tasks = sum(p < 0.05 for p in p_values)
        overall_sig = "Signifikan" if overall_p < 0.05 else "Tidak Signifikan"
        method_name = "Paired T-Test" if use_ttest else "Wilcoxon Signed Ranks"
        st.markdown("### Statistical Summary")
        st.markdown(f"""
        <div style="background:#f8fafc;padding:24px;border-radius:12px;border-left:4px solid #6366f1;">
          <div style="font-size:16px;font-weight:700;color:{text_main};margin-bottom:12px;">Overall Findings</div>
          <ul style="font-size:14px;color:#374151;line-height:1.8;margin:0;">
            <li>Metode: <b>{method_name}</b></li>
            <li><b>{sig_tasks}/3 tasks</b> menunjukkan perbedaan signifikan (p &lt; 0.05)</li>
            <li><b>Overall:</b> {stat_label}={overall_stat:.3f}, p={overall_p:.3f} — {overall_sig}</li>
            <li>Mean Light: <b>{avg_l:.1f}%</b> | Mean Dark: <b>{avg_d:.1f}%</b></li>
            <li>{'Light Mode lebih akurat' if avg_l < avg_d else 'Dark Mode lebih akurat'} secara deskriptif</li>
          </ul>
        </div>""", unsafe_allow_html=True)

# ======================
# MENU: UEQ ANALYSIS
# ======================
if menu == "UEQ Analysis":
    st.markdown(f"""
    <div style="font-size:24px;font-weight:700;color:#1e293b;margin-bottom:4px;">Analisis UEQ — {app}</div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:20px;">Logika identik UEQ Data Analysis Tool Version 13</div>
    """, unsafe_allow_html=True)

    REVERSE_ITEMS = {3,4,5,9,10,12,17,18,19,21,23,24,25}
    SKALA_MAP = {
        "Daya tarik":[1,12,14,16,24,25],"Kejelasan":[2,4,13,21],
        "Efisiensi":[9,20,22,23],"Ketepatan":[8,11,17,19],
        "Stimulasi":[5,6,7,18],"Kebaruan":[3,10,15,26],
    }
    LABEL_KIRI  = ["menyusahkan","tak dapat dipahami","kreatif","mudah dipelajari","bermanfaat","membosankan","tidak menarik","tak dapat diprediksi","cepat","berdaya cipta","menghalangi","baik","rumit","tidak disukai","lazim","tidak nyaman","aman","memotivasi","memenuhi ekspektasi","tidak efisien","jelas","tidak praktis","terorganisasi","atraktif","ramah pengguna","konservatif"]
    LABEL_KANAN = ["menyenangkan","dapat dipahami","monoton","sulit dipelajari","kurang bermanfaat","mengasyikkan","menarik","dapat diprediksi","lambat","konvensional","mendukung","buruk","sederhana","menggembirakan","terdepan","nyaman","tidak aman","tidak memotivasi","tidak memenuhi ekspektasi","efisien","membingungkan","praktis","berantakan","tidak atraktif","tidak ramah pengguna","inovatif"]

    def ueq_transform_local(df_raw):
        dt = df_raw.copy().apply(pd.to_numeric, errors="coerce") - 4
        for i in REVERSE_ITEMS:
            col = f"I{i}"
            if col in dt.columns: dt[col] = -dt[col]
        return dt

    def ueq_scale_stats_local(df_raw):
        dt = ueq_transform_local(df_raw)
        results = []
        for sk, items_sk in SKALA_MAP.items():
            cols = [f"I{i}" for i in items_sk]
            per_person = dt[cols].mean(axis=1).dropna()
            n_ = len(per_person)
            mean = float(per_person.mean())
            var_ = float(per_person.var(ddof=1))
            std_ = float(per_person.std(ddof=1))
            t_crit = t_dist.ppf(0.975, df=n_-1) if n_ > 1 else 1.96
            ci = t_crit * std_ / np.sqrt(n_) if n_ > 0 else np.nan
            results.append({"Skala":sk,"N":n_,"Mean":round(mean,4),"Varians":round(var_,4),
                            "Std. Dev.":round(std_,4),"Confidence (±)":round(ci,4),
                            "CI Bawah":round(mean-ci,4),"CI Atas":round(mean+ci,4)})
        return pd.DataFrame(results)

    def interpret_category_local(score):
        if score > 1.5: return "Excellent"
        elif score > 0.8: return "Good"
        elif score > 0.0: return "Above Average"
        elif score > -0.8: return "Below Average"
        else: return "Bad"

    items_label = [f"I{i}" for i in range(1,27)]
    u_light = load_ueq("data_ueq_light", current_user, app, n)
    u_dark  = load_ueq("data_ueq_dark",  current_user, app, n)
    u_light_disp = u_light.copy()
    u_light_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(u_light_disp))])
    u_dark_disp = u_dark.copy()
    u_dark_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(u_dark_disp))])

    tab_input, tab_dt, tab_hasil, tab_ci, tab_dist, tab_bench, tab_inkonsisten = st.tabs([
        "Data Mentah","Data Transformation (DT)","Hasil Skala",
        "Confidence Interval","Distribusi Jawaban","Benchmark","Deteksi Inkonsistensi",
    ])

    with tab_input:
        st.markdown("### Input Data Skor Kuesioner (Skala 1-7)")
        with st.expander("Dataset Manager — Light Mode", expanded=False):
            dataset_manager(u_light, items_label, file_ueq_light, "UEQ Light Mode", f"ueq_light_{app}")
        with st.expander("Dataset Manager — Dark Mode", expanded=False):
            dataset_manager(u_dark, items_label, file_ueq_dark, "UEQ Dark Mode", f"ueq_dark_{app}")
        st.markdown(f"**Light Mode** (n={n})")
        edit_l = st.data_editor(u_light_disp, key="ueq_raw_light", use_container_width=True, column_config={"Responden":st.column_config.TextColumn(disabled=True),**{f"I{i}":st.column_config.NumberColumn(f"I{i}",min_value=1,max_value=7,step=1) for i in range(1,27)}})
        st.markdown(f"**Dark Mode** (n={n})")
        edit_d = st.data_editor(u_dark_disp, key="ueq_raw_dark", use_container_width=True, column_config={"Responden":st.column_config.TextColumn(disabled=True),**{f"I{i}":st.column_config.NumberColumn(f"I{i}",min_value=1,max_value=7,step=1) for i in range(1,27)}})
        if st.button("Simpan Data Kuesioner", type="primary", use_container_width=True):
            save_ueq("data_ueq_light", current_user, app, edit_l[items_label])
            save_ueq("data_ueq_dark",  current_user, app, edit_d[items_label])
            st.session_state["saved_ueq"] = True; st.rerun()
        if st.session_state.get("saved_ueq"):
            st.success("Data UEQ berhasil disimpan!"); st.session_state["saved_ueq"] = False
        col_del_l, col_del_d = st.columns(2)
        with col_del_l: render_delete_button(file_path=file_ueq_light, label="UEQ Light Mode", columns=items_label, default_value=4, key_suffix="ueq_light")
        with col_del_d: render_delete_button(file_path=file_ueq_dark,  label="UEQ Dark Mode",  columns=items_label, default_value=4, key_suffix="ueq_dark")

    df_light_clean = edit_l[items_label].apply(pd.to_numeric, errors="coerce")
    df_dark_clean  = edit_d[items_label].apply(pd.to_numeric, errors="coerce")
    dt_light    = ueq_transform_local(df_light_clean)
    dt_dark     = ueq_transform_local(df_dark_clean)
    stats_light = ueq_scale_stats_local(df_light_clean)
    stats_dark  = ueq_scale_stats_local(df_dark_clean)

    with tab_dt:
        st.markdown("### Data Transformation — Sheet DT")
        col_dt1, col_dt2 = st.columns(2)
        with col_dt1:
            st.markdown("**Light Mode**")
            dt_l_disp = dt_light.copy().round(2)
            dt_l_disp.insert(0,"Responden",[f"R{i+1}" for i in range(len(dt_l_disp))])
            st.dataframe(dt_l_disp, use_container_width=True)
        with col_dt2:
            st.markdown("**Dark Mode**")
            dt_d_disp = dt_dark.copy().round(2)
            dt_d_disp.insert(0,"Responden",[f"R{i+1}" for i in range(len(dt_d_disp))])
            st.dataframe(dt_d_disp, use_container_width=True)

    with tab_hasil:
        st.markdown("### Hasil Analisis Skala UEQ")
        tabel_gabung = pd.DataFrame({
            "Skala":stats_light["Skala"],"Mean Light":stats_light["Mean"],
            "Var. Light":stats_light["Varians"],"Mean Dark":stats_dark["Mean"],"Var. Dark":stats_dark["Varians"],
        })
        tabel_gabung["Unggul"] = tabel_gabung.apply(lambda r: "Light Mode" if r["Mean Light"]>r["Mean Dark"] else ("Dark Mode" if r["Mean Dark"]>r["Mean Light"] else "Seimbang"), axis=1)
        st.table(tabel_gabung)

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(x=stats_light["Skala"],y=stats_light["Mean"],name="Light Mode",marker_color="#6366f1",text=[f"{v:.4f}" for v in stats_light["Mean"]],textposition="outside",error_y=dict(type='data',array=stats_light["Confidence (±)"].tolist(),visible=True,color="#6366f1",thickness=1.5,width=6)))
        fig_bar.add_trace(go.Bar(x=stats_dark["Skala"], y=stats_dark["Mean"], name="Dark Mode", marker_color="#1e293b",text=[f"{v:.4f}" for v in stats_dark["Mean"]], textposition="outside",error_y=dict(type='data',array=stats_dark["Confidence (±)"].tolist(),visible=True,color="#1e293b",thickness=1.5,width=6)))
        fig_bar.add_hline(y=0.0,line_color="black",line_width=1)
        fig_bar.add_hline(y=0.8,line_dash="dot",line_color="#10b981",line_width=1.5,annotation_text="Batas Positif (0.8)",annotation_position="right")
        fig_bar.add_hline(y=-0.8,line_dash="dot",line_color="#ef4444",line_width=1.5,annotation_text="Batas Negatif (-0.8)",annotation_position="right")
        fig_bar.update_layout(yaxis=dict(range=[-3,3],title="Mean Score",dtick=0.5),barmode="group",height=500,legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),plot_bgcolor="white",paper_bgcolor="white")
        st.plotly_chart(fig_bar, use_container_width=True)

        col_il, col_id = st.columns(2)
        with col_il:
            st.markdown("**Light Mode**")
            cat_l = stats_light.copy(); cat_l["Kategori"] = cat_l["Mean"].apply(interpret_category_local)
            st.dataframe(cat_l[["Skala","Mean","Varians","Kategori"]], use_container_width=True, hide_index=True)
        with col_id:
            st.markdown("**Dark Mode**")
            cat_d = stats_dark.copy(); cat_d["Kategori"] = cat_d["Mean"].apply(interpret_category_local)
            st.dataframe(cat_d[["Skala","Mean","Varians","Kategori"]], use_container_width=True, hide_index=True)

        avg_l = stats_light["Mean"].mean(); avg_d = stats_dark["Mean"].mean()
        unggul = "Light Mode" if avg_l > avg_d else "Dark Mode"
        st.success(f"**Kesimpulan:** {unggul} lebih unggul pada aplikasi {app} (Light: {avg_l:.4f} | Dark: {avg_d:.4f}).")

    with tab_ci:
        st.markdown("### Confidence Interval (95%) per Skala")
        col_ci1, col_ci2 = st.columns(2)
        with col_ci1:
            st.markdown("**Light Mode**")
            st.dataframe(stats_light[["Skala","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]], use_container_width=True, hide_index=True)
        with col_ci2:
            st.markdown("**Dark Mode**")
            st.dataframe(stats_dark[["Skala","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]], use_container_width=True, hide_index=True)

    with tab_dist:
        st.markdown("### Distribusi Jawaban per Item")
        mode_dist = st.radio("Pilih Mode",["Light Mode","Dark Mode"],horizontal=True,key="dist_mode")
        df_dist = df_light_clean if mode_dist=="Light Mode" else df_dark_clean
        dist_rows = []
        for i in range(1,27):
            col_ = f"I{i}"
            vals = df_dist[col_].dropna() if col_ in df_dist.columns else pd.Series(dtype=float)
            counts = {v:0 for v in range(1,8)}
            for v in vals:
                try: counts[int(v)] += 1
                except: pass
            dist_rows.append({"Item":i,"Label":f"{LABEL_KIRI[i-1]} / {LABEL_KANAN[i-1]}","Skala":next((s for s,it in SKALA_MAP.items() if i in it),"-"),**{str(k):counts[k] for k in range(1,8)}})
        st.dataframe(pd.DataFrame(dist_rows), use_container_width=True, hide_index=True)

    with tab_bench:
        st.markdown("### Benchmark UEQ")
        st.caption("Benchmark: 468 studi, 21.175 responden.")
        BENCH_RANGES = {
            "Daya tarik":{"p25":0.69,"p50":1.18,"p75":1.58,"p90":1.84},
            "Kejelasan": {"p25":0.72,"p50":1.20,"p75":1.73,"p90":2.00},
            "Efisiensi": {"p25":0.60,"p50":1.05,"p75":1.50,"p90":1.88},
            "Ketepatan": {"p25":0.78,"p50":1.14,"p75":1.48,"p90":1.70},
            "Stimulasi": {"p25":0.50,"p50":1.00,"p75":1.35,"p90":1.70},
            "Kebaruan":  {"p25":0.16,"p50":0.70,"p75":1.12,"p90":1.60},
        }
        def get_benchmark_cat(mean, skala):
            b = BENCH_RANGES[skala]
            if mean >= b["p90"]: return "Excellent"
            elif mean >= b["p75"]: return "Good"
            elif mean >= b["p50"]: return "Above Average"
            elif mean >= b["p25"]: return "Below Average"
            else: return "Bad"
        bench_rows = []
        for _, row_l in stats_light.iterrows():
            sk = row_l["Skala"]; row_d = stats_dark[stats_dark["Skala"]==sk].iloc[0]; b = BENCH_RANGES[sk]
            bench_rows.append({"Skala":sk,"Mean Light":row_l["Mean"],"Kategori Light":get_benchmark_cat(row_l["Mean"],sk),"Mean Dark":row_d["Mean"],"Kategori Dark":get_benchmark_cat(row_d["Mean"],sk)})
        st.dataframe(pd.DataFrame(bench_rows), use_container_width=True, hide_index=True)

    with tab_inkonsisten:
        st.markdown("### Deteksi Jawaban Tidak Konsisten")
        mode_ink = st.radio("Pilih Mode",["Light Mode","Dark Mode"],horizontal=True,key="inkons_mode")
        df_ink = df_light_clean if mode_ink=="Light Mode" else df_dark_clean
        dt_ink = ueq_transform_local(df_ink)
        hasil = []
        for idx in range(len(dt_ink)):
            row = dt_ink.iloc[idx]
            crit = sum(1 for sk,items_sk in SKALA_MAP.items() if len(vals:=row[[f"I{i}" for i in items_sk]].dropna())>=2 and (vals.max()-vals.min())>3)
            raw_row = df_ink.iloc[idx] if idx < len(df_ink) else pd.Series()
            same = int(raw_row.value_counts().max()) if len(raw_row)>0 else 0
            hasil.append({"Responden":f"R{idx+1}","Skala Kritis":crit,"Perlu Dihapus?":"Ya" if crit>=2 else "Tidak","Jawaban Identik":same,"Critical Length":"Ya" if same>15 else "Tidak"})
        df_check = pd.DataFrame(hasil)
        def highlight_inkons(row):
            if row["Perlu Dihapus?"].startswith("Ya") or row["Critical Length"].startswith("Ya"):
                return ["background-color:#FEF3C7"]*len(row)
            return [""]*len(row)
        st.dataframe(df_check.style.apply(highlight_inkons,axis=1), use_container_width=True, hide_index=True)
        n_hapus = (df_check["Perlu Dihapus?"].str.startswith("Ya")).sum()
        n_crit  = (df_check["Critical Length"].str.startswith("Ya")).sum()
        if n_hapus > 0 or n_crit > 0:
            st.warning(f"Ditemukan {n_hapus} responden dengan 2+ skala kritis dan {n_crit} dengan Critical Length.")
        else:
            st.success("Tidak ditemukan jawaban yang mencurigakan.")

    st.markdown("---")
    st.caption("UEQ Analysis · Logika identik UEQ Data Analysis Tool Version 13 · Muhammad Farhan, UII 2026")

# ======================
# MENU: PREFERENSI RESPONDEN
# ======================
if menu == "Preferensi Responden":
    st.markdown(f'<div style="font-size:28px;font-weight:700;color:#1e293b;margin-bottom:10px;">Preferensi Responden - {app}</div>', unsafe_allow_html=True)
    st.info("Metode Analisis: Mean Preference Analysis (Skala Likert 1–7, Bipolar). Nilai 1 = Light Mode · Nilai 7 = Dark Mode · Nilai 4 = Netral.")

    columns_pref = ["Responden","R1","R2","R3","R4","ES1","ES2","ES3","ES4","U1","U2","U3","U4","B1","B2","B3","B4","E1","E2","E3","E4","ED1","ED2","ED3","ED4"]
    file_pos = os.path.join(USER_DIR, f"preferensi_positif_{app}.csv")
    file_neg = os.path.join(USER_DIR, f"preferensi_negatif_{app}.csv")

    tab_input_pref, tab_analisis = st.tabs(["Input Data Kuesioner","Hasil Analisis dan Narasi"])

    with tab_input_pref:
        with st.expander("Dataset Manager - Preferensi Positif", expanded=False):
            dataset_manager(load_pref("data_pref_pos",current_user,app,n), columns_pref, file_pos, "Dataset Preferensi Positif", f"preferensi_positif_{app}")
        with st.expander("Dataset Manager - Preferensi Negatif", expanded=False):
            dataset_manager(load_pref("data_pref_neg",current_user,app,n), columns_pref, file_neg, "Dataset Preferensi Negatif", f"preferensi_negatif_{app}")
        st.markdown("---")
        st.markdown("### 1. Pernyataan Positif")
        df_pos = adjust_dataframe(load_pref("data_pref_pos",current_user,app,n), n)
        df_pos_edit = st.data_editor(df_pos, key="pos_editor_final", use_container_width=True)
        st.markdown("---")
        st.markdown("### 2. Pernyataan Negatif")
        df_neg = adjust_dataframe(load_pref("data_pref_neg",current_user,app,n), n)
        df_neg_edit = st.data_editor(df_neg, key="neg_editor_final", use_container_width=True)
        st.markdown("---")
        if st.button("Simpan Semua Data Preferensi", type="primary", use_container_width=True):
            save_pref("data_pref_pos", current_user, app, df_pos_edit)
            save_pref("data_pref_neg", current_user, app, df_neg_edit)
            st.session_state["saved_pref"] = True; st.rerun()
        if st.session_state.get("saved_pref"):
            st.success("Data Preferensi berhasil disimpan!"); st.session_state["saved_pref"] = False
        col_del_pos, col_del_neg = st.columns(2)
        with col_del_pos: render_delete_button(file_path=file_pos, label="Preferensi Positif", columns=columns_pref[1:], default_value=0, key_suffix="pref_pos")
        with col_del_neg: render_delete_button(file_path=file_neg, label="Preferensi Negatif", columns=columns_pref[1:], default_value=0, key_suffix="pref_neg")

    with tab_analisis:
        cols_data_pref = columns_pref[1:]
        def _cek_supabase(table):
            try:
                df_check = load_pref(table, current_user, app, n)
                cols_only = [c for c in cols_data_pref if c != "Responden"]
                return df_check[cols_only].apply(pd.to_numeric,errors="coerce").sum().sum() > 0
            except: return False
        pos_terisi = _cek_supabase("data_pref_pos")
        neg_terisi = _cek_supabase("data_pref_neg")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if pos_terisi: st.success("Data Preferensi Positif sudah terisi.")
            else:          st.warning("Data Preferensi Positif belum diisi.")
        with col_s2:
            if neg_terisi: st.success("Data Preferensi Negatif sudah terisi.")
            else:          st.warning("Data Preferensi Negatif belum diisi.")

        if not pos_terisi or not neg_terisi:
            st.info("Silakan isi data preferensi terlebih dahulu."); st.stop()

        if st.button("Refresh Analisis", use_container_width=True): st.rerun()

        aspek_map = {
            "Keterbacaan (Readability)":["R1","R2","R3","R4"],
            "Kelelahan Mata (Eye Strain)":["ES1","ES2","ES3","ES4"],
            "Usability":["U1","U2","U3","U4"],
            "Konsumsi Baterai":["B1","B2","B3","B4"],
            "Efisien Kinerja":["E1","E2","E3","E4"],
            "Estetika & Daya Tarik":["ED1","ED2","ED3","ED4"]
        }
        final_data = []
        for name, cols in aspek_map.items():
            m_pos     = df_pos_edit[cols].apply(pd.to_numeric,errors='coerce').mean().mean()
            m_neg_raw = df_neg_edit[cols].apply(pd.to_numeric,errors='coerce').mean().mean()
            m_neg_rev = 8 - m_neg_raw
            grand_mean = (m_pos + m_neg_rev) / 2
            if pd.isna(grand_mean):      kecenderungan, color_code = "Data Kosong","#94a3b8"
            elif grand_mean < 4:         kecenderungan, color_code = "Light Mode","#6366f1"
            elif grand_mean > 4:         kecenderungan, color_code = "Dark Mode","#1e293b"
            else:                        kecenderungan, color_code = "Netral","#10b981"
            final_data.append({"Aspek Pengalaman":name,"Mean Positif":round(m_pos,3),"Mean Negatif (Raw)":round(m_neg_raw,3),"Grand Mean":round(grand_mean,3),"Preferensi":kecenderungan,"Color":color_code})
        res_df = pd.DataFrame(final_data)

        st.markdown("### Tabel Rekapitulasi Preferensi")
        st.table(res_df[["Aspek Pengalaman","Mean Positif","Mean Negatif (Raw)","Grand Mean","Preferensi"]])

        st.markdown("### Grafik Kecenderungan Per Aspek")
        fig_pref = go.Figure()
        fig_pref.add_trace(go.Bar(x=res_df["Aspek Pengalaman"],y=res_df["Grand Mean"],marker_color=res_df["Color"],text=res_df["Grand Mean"],textposition='auto'))
        fig_pref.add_hline(y=4,line_dash="dash",line_color="red",annotation_text="Titik Netral (4.0)")
        fig_pref.update_layout(yaxis=dict(range=[1,7],title="Skor Preferensi"),height=450)
        st.plotly_chart(fig_pref, use_container_width=True)

        l_aspek = res_df[res_df["Preferensi"]=="Light Mode"]["Aspek Pengalaman"].tolist()
        d_aspek = res_df[res_df["Preferensi"]=="Dark Mode"]["Aspek Pengalaman"].tolist()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div style="background-color:rgba(99,102,241,0.1);padding:15px;border-radius:10px;border-left:5px solid #6366f1;"><b style="color:#6366f1;">Unggul Light Mode</b><br><p style="font-size:13px;margin-top:8px;">{", ".join(l_aspek) if l_aspek else "Tidak ada"}</p></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div style="background-color:rgba(30,41,59,0.1);padding:15px;border-radius:10px;border-left:5px solid #1e293b;"><b style="color:#1e293b;">Unggul Dark Mode</b><br><p style="font-size:13px;margin-top:8px;">{", ".join(d_aspek) if d_aspek else "Tidak ada"}</p></div>', unsafe_allow_html=True)

        aspek_max = res_df.loc[res_df["Grand Mean"].idxmax()]
        aspek_min = res_df.loc[res_df["Grand Mean"].idxmin()]
        st.success(f"""
        Kesimpulan Akhir Preferensi:
        - Preferensi Dark Mode terkuat: {aspek_max['Aspek Pengalaman']} (Skor: {aspek_max['Grand Mean']}).
        - Preferensi Light Mode terkuat: {aspek_min['Aspek Pengalaman']} (Skor: {aspek_min['Grand Mean']}).
        - Secara keseluruhan lebih optimal menggunakan {'Light Mode' if len(l_aspek)>len(d_aspek) else 'Dark Mode'}.
        """)

# ======================
# MENU: SETTINGS
# ======================
if menu == "Settings":
    render_settings_page()