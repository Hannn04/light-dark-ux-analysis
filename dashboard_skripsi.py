import streamlit as st
from PIL import Image
icon = Image.open("assets/icon.png")

st.set_page_config(
    page_title="Dashboard Analitik UX | Penelitian Light Mode vs Dark Mode",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="expanded"
)

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
import pingouin as pg
from scipy.stats import t as t_dist
import requests
from PIL import Image

# TAMBAHKAN INI setelah from auth import ...
from db import (
    load_app_list, save_app_list,
    load_data, save_data,
    load_ueq, save_ueq,
    load_pref, save_pref,
    pref_exists
)

from auth import render_auth_page, logout, render_settings_page, load_users, get_cookie_controller

_controller = get_cookie_controller()
if not st.session_state.get("logged_in") and not st.session_state.get("logged_out"):
    if not st.session_state.get("_cookie_ready"):
        st.session_state["_cookie_ready"] = True
        st.rerun()
    else:
        _saved_user = _controller.get("session_user")
        if _saved_user and _saved_user in load_users():
            st.session_state.update({"logged_in": True, "current_user": _saved_user})
            st.rerun()


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


if "app_list" not in st.session_state:
    st.session_state.app_list = []

# Pastikan confirm_reset juga diinisialisasi di sini agar rapi
if "confirm_reset" not in st.session_state:
    st.session_state.confirm_reset = False

if "show_logout_confirm" not in st.session_state:
    st.session_state.show_logout_confirm = False


if "show_reset_confirm" not in st.session_state:
    st.session_state.show_reset_confirm = False

# ✅ Perbaikan — sesuai handbook (>0.8 = positif, -0.8 s.d. 0.8 = netral, <-0.8 = negatif)
def interpret_ueq(score):
    if score > 0.8:    return "Positive"
    elif score >= -0.8: return "Neutral"
    else:              return "Negative"

def wilcoxon_full_spss(light, dark):

    light = pd.to_numeric(light, errors="coerce")
    dark = pd.to_numeric(dark, errors="coerce")

    mask = ~(light.isna() | dark.isna())
    light = light[mask]
    dark = dark[mask]

    diff = dark - light
    df = pd.DataFrame({"diff": diff})

    # buang ties
    df = df[df["diff"] != 0]

    df["abs"] = df["diff"].abs()
    df["rank"] = rankdata(df["abs"], method="average")

    negative = df[df["diff"] < 0]
    positive = df[df["diff"] > 0]

    n = len(df)

    # ======================
    # RANKS TABLE
    # ======================
    ranks_table = pd.DataFrame({
        "": ["Negative Ranks", "Positive Ranks", "Ties", "Total"],
        "N": [
            len(negative),
            len(positive),
            len(diff) - n,
            len(diff)
        ],
        "Mean Rank": [
            round(negative["rank"].mean(), 2) if len(negative) > 0 else 0,
            round(positive["rank"].mean(), 2) if len(positive) > 0 else 0,
            "",
            ""
        ],
        "Sum of Ranks": [
            round(negative["rank"].sum(), 2),
            round(positive["rank"].sum(), 2),
            "",
            ""
        ]
    })

    # ======================
    # HITUNG W
    # ======================
    W_pos = positive["rank"].sum()
    W_neg = negative["rank"].sum()
    T = W_neg

    # ======================
    # MEAN & SD + TIE CORRECTION
    # ======================
    mean_T = n * (n + 1) / 4

    ties_count = df["abs"].value_counts()
    tie_sum = np.sum(ties_count**3 - ties_count)

    var_T = (n * (n + 1) * (2*n + 1) - 0.5 * tie_sum) / 24
    sd_T = np.sqrt(var_T)

   
    

    

    # ======================
    # 🔥 P-VALUE DARI SCIPY (SUDAH BENAR)
    # ======================
    light_clean = light[df.index]
    dark_clean = dark[df.index]
    
    res = wilcoxon(
        light,
        dark,
        zero_method='wilcox',
        correction=False,   # 🔥 WAJIB
        alternative='two-sided',
        method='approx'
    )

    z = stats.norm.ppf(res.pvalue / 2) * (-1 if W_neg < W_pos else 1)
    p = res.pvalue

    W_pos = positive["rank"].sum()
    W_neg = negative["rank"].sum()
    W = min(W_pos, W_neg)

    mean_T = n * (n + 1) / 4

    ties_count = df["abs"].value_counts()
    tie_sum = np.sum(ties_count**3 - ties_count)

    var_T = (n * (n + 1) * (2*n + 1) - 0.5 * tie_sum) / 24
    sd_T = np.sqrt(var_T)

    
    # SPSS secara default tidak menggunakan continuity correction untuk nilai Z
    correction = 0
    z_raw = (W - mean_T + correction) / sd_T
    # SPSS convention: Z negatif jika W_neg <= W_pos, positif jika W_neg > W_pos
    z = -abs(z_raw) if W_neg <= W_pos else abs(z_raw)
 
    # p-value dari Z (two-tailed)
    p = 2 * (1 - norm.cdf(abs(z)))
 
    stats_table = pd.DataFrame({
        "": ["Z", "Asymp. Sig (2-tailed)"],
        "Value": [round(z, 3), round(p, 3)]
    })
 
    return ranks_table, stats_table


def compute_wilcoxon_pair(light, dark, light_lbl, dark_lbl):
    """Compute Wilcoxon stats for one pair and return a display-ready dict."""
    ranks_table, stats_table = wilcoxon_full_spss(light, dark)

    z_val = float(stats_table.iloc[0, 1])
    p_val = float(stats_table.iloc[1, 1])

    neg_n   = int(ranks_table.iloc[0]["N"])
    pos_n   = int(ranks_table.iloc[1]["N"])
    ties_n  = int(ranks_table.iloc[2]["N"])
    total_n = int(ranks_table.iloc[3]["N"])

    neg_mean = ranks_table.iloc[0]["Mean Rank"]
    pos_mean = ranks_table.iloc[1]["Mean Rank"]
    neg_sum  = ranks_table.iloc[0]["Sum of Ranks"]
    pos_sum  = ranks_table.iloc[1]["Sum of Ranks"]

    def fmt(v, decimals=2):
        try:
            return f"{float(v):.{decimals}f}"
        except (TypeError, ValueError):
            return ""

    return {
        "var_name":  f"{dark_lbl} - {light_lbl}",
        "light_lbl": light_lbl,
        "dark_lbl":  dark_lbl,
        "neg_n": neg_n, "pos_n": pos_n, "ties_n": ties_n, "total_n": total_n,
        "neg_mean": fmt(neg_mean), "pos_mean": fmt(pos_mean),
        "neg_sum":  fmt(neg_sum),  "pos_sum":  fmt(pos_sum),
        "z_val": z_val, "p_val": p_val,
    }

def shapiro_and_ks(light: pd.Series, dark: pd.Series, label: str) -> dict:
    from scipy.stats import kstest, norm as sp_norm
    import warnings

    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    mask  = ~(light.isna() | dark.isna())
    diff  = (dark - light)[mask]

    if len(diff) < 3:
        return {
            "label": label, "n": int(mask.sum()),
            "ks_stat": np.nan, "ks_p": np.nan,
            "sw_stat": np.nan, "sw_p": np.nan,
            "normal": None,
        }

    n = len(diff)

    # --- Shapiro-Wilk ---
    from scipy.stats import shapiro
    sw_stat, sw_p = shapiro(diff)

    # --- Lilliefors yang lebih akurat ---
    # Standardisasi menggunakan mean & std sampel (bukan populasi)
    diff_mean = diff.mean()
    diff_std  = diff.std(ddof=1)
    diff_standardized = (diff - diff_mean) / diff_std

    # Hitung KS statistic manual
    from scipy.stats import norm as sp_norm
    n_obs = len(diff_standardized)
    diff_sorted = np.sort(diff_standardized)
    
    # CDF empiris vs teoritis
    cdf_teoritis = sp_norm.cdf(diff_sorted)
    ecdf_atas  = np.arange(1, n_obs + 1) / n_obs
    ecdf_bawah = np.arange(0, n_obs) / n_obs
    
    ks_stat = max(
        np.max(np.abs(ecdf_atas  - cdf_teoritis)),
        np.max(np.abs(ecdf_bawah - cdf_teoritis))
    )

    # P-value menggunakan Lilliefors via statsmodels
    try:
        from statsmodels.stats.diagnostic import lilliefors as lf_test
        ks_stat_lf, ks_p = lf_test(diff.values, dist='norm')
        ks_stat = ks_stat_lf  # gunakan stat dari lilliefors langsung
    except Exception:
        # Fallback: gunakan aproksimasi Dallal-Wilkinson
        # Formula yang lebih dekat ke SPSS
        z = ks_stat * (np.sqrt(n_obs) + 0.12 + 0.11 / np.sqrt(n_obs))
        ks_p = np.exp(-2 * z**2) * 2
        ks_p = min(ks_p, 1.0)

    normal = bool(sw_p >= 0.05)

    return {
        "label":   label,
        "n":       int(n),
        "ks_stat": round(float(ks_stat), 3),
        "ks_p":    float(ks_p),   # jangan dibulatkan dulu, biar _fmt_p yang handle
        "sw_stat": round(float(sw_stat), 3),
        "sw_p":    float(sw_p),
        "normal":  normal,
    }
 
 
def render_normality_table(results: list) -> None:
    """
    Tabel Tests of Normality SPSS-style:
    Hanya Shapiro-Wilk, identik dengan output SPSS Explore (tanpa Kolmogorov-Smirnov).
    """
    is_dark = st.session_state.get("app_theme", "light") == "dark"
    bg_header = "#1e293b" if is_dark else "#d9d9d9"
    bg_subheader = "#334155" if is_dark else "#ececec"
    bg_first_col = "#1e293b" if is_dark else "#f5f5f5"
    text_color = "#f1f5f9" if is_dark else "#0f172a"
    text_soft = "#94a3b8" if is_dark else "#64748b"
    border_color = "#475569" if is_dark else "#aaa"
    border_cell = "#334155" if is_dark else "#bbb"

    def _fmt_p(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        if v < 0.001:
            return "<,001"   # ← pakai koma seperti SPSS Indonesia
        return f"{v:.3f}".replace(".", ",")  # ← ganti titik ke koma

    def _fmt_stat(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        return f"{v:.3f}"

    rows_html = ""
    for r in results:
        sw_sig  = (not (isinstance(r["sw_p"], float) and np.isnan(r["sw_p"]))) and r["sw_p"] < 0.05
        p_sw_color  = "#ef4444" if sw_sig else "inherit"  # soft red

        rows_html += f"""
        <tr>
          <td style="border:1px solid {border_cell};padding:6px 12px;font-weight:600;
            background:{bg_first_col};color:{text_color};white-space:nowrap;">{r['label']}</td>
          <td style="border:1px solid {border_cell};padding:6px 12px;text-align:center;color:{text_color};">{_fmt_stat(r['sw_stat'])}</td>
          <td style="border:1px solid {border_cell};padding:6px 12px;text-align:center;color:{text_color};">{r['n']}</td>
          <td style="border:1px solid {border_cell};padding:6px 12px;text-align:center;color:{p_sw_color};font-weight:{'700' if sw_sig else '400'};">{_fmt_p(r['sw_p'])}</td>
        </tr>"""

    st.markdown(f"""
    <div style="margin:16px 0 4px 0;overflow-x:auto;">
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;
        min-width:400px;width:100%;color:{text_color};">
        <thead>
          <tr>
            <th rowspan="2" style="border:1px solid {border_color};padding:7px 12px;background:{bg_header};
              color:{text_color};text-align:left;font-weight:700;font-size:13px;">
              Tests of Normality
            </th>
            <th colspan="3" style="border:1px solid {border_color};padding:7px 12px;background:{bg_header};
              color:{text_color};text-align:center;font-weight:600;font-size:12px;">
              Shapiro-Wilk
            </th>
          </tr>
          <tr style="background:{bg_subheader};color:{text_color};">
            <th style="border:1px solid {border_color};padding:6px 12px;text-align:center;font-size:12px;color:{text_color};">Statistic</th>
            <th style="border:1px solid {border_color};padding:6px 12px;text-align:center;font-size:12px;color:{text_color};">df</th>
            <th style="border:1px solid {border_color};padding:6px 12px;text-align:center;font-size:12px;color:{text_color};">Sig.</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)
 
 
def render_normality_recommendation(results: list) -> str:
    """
    Tampilkan rekomendasi otomatis berdasarkan Shapiro-Wilk (acuan SPSS untuk n<50).
    Return "t-test" atau "wilcoxon".
    """
    valid = [r for r in results if r.get("normal") is not None]
    if not valid:
        return "wilcoxon"
 
    all_normal = all(r["normal"] for r in valid)
 
    if all_normal:
        color, bg, border = "#166534", "#F0FDF4", "#BBF7D0"
        icon   = "✓"
        title  = "Selisih berdistribusi normal pada semua variabel (Sig. Shapiro-Wilk ≥ 0,05)"
        desc   = "Rekomendasi otomatis: Paired Samples T-Test (Parametrik)"
        rec    = "t-test"
    else:
        not_normal = [r["label"] for r in valid if not r["normal"]]
        color, bg, border = "#92400E", "#FFFBEB", "#FDE68A"
        icon   = "!"
        title  = f"Distribusi tidak normal pada: {', '.join(not_normal)} (Sig. Shapiro-Wilk < 0,05)"
        desc   = "Rekomendasi otomatis: Wilcoxon Signed Ranks Test (Non-Parametrik)"
        rec    = "wilcoxon"
 
    st.markdown(f"""
    <div style="background:{bg};border:1px solid {border};border-radius:10px;
      padding:12px 18px;display:flex;align-items:center;gap:14px;margin:10px 0;">
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
 
 
def compute_paired_ttest_pair(light: pd.Series, dark: pd.Series,
                               light_lbl: str, dark_lbl: str) -> dict:
    """Hitung Paired T-Test untuk satu pasang Series."""
    light = pd.to_numeric(light, errors="coerce")
    dark  = pd.to_numeric(dark,  errors="coerce")
    mask  = ~(light.isna() | dark.isna())
    light, dark = light[mask], dark[mask]
    n = len(light)
 
    diff   = light - dark
    dmean  = float(diff.mean())
    dstd   = float(diff.std(ddof=1))
    dse    = dstd / np.sqrt(n)
    df_val = n - 1
 
    t_stat, p_two = stats.ttest_rel(light, dark)
    p_one  = p_two / 2
    ci_low, ci_up = stats.t.interval(0.95, df_val, loc=dmean, scale=dse)
    corr_r, corr_p = (stats.pearsonr(light, dark) if n >= 2 else (np.nan, np.nan))
 
    return {
        "light_lbl": light_lbl, "dark_lbl": dark_lbl, "n": n,
        "light_mean": float(light.mean()), "dark_mean": float(dark.mean()),
        "light_std":  float(light.std(ddof=1)), "dark_std": float(dark.std(ddof=1)),
        "light_se":   float(light.std(ddof=1)) / np.sqrt(n),
        "dark_se":    float(dark.std(ddof=1))  / np.sqrt(n),
        "diff_mean": dmean, "diff_std": dstd, "diff_se": dse,
        "ci_low": float(ci_low), "ci_up": float(ci_up),
        "t": float(t_stat), "df": df_val,
        "p_one": float(p_one), "p_two": float(p_two),
        "corr_r": float(corr_r) if not np.isnan(corr_r) else np.nan,
        "corr_p": float(corr_p) if not np.isnan(corr_p) else np.nan,
    }
 
 
def render_spss_paired_ttest(pairs_data: list) -> None:
    """Output Paired T-Test identik SPSS: Statistics + Correlations + Test."""
    is_dark = st.session_state.get("app_theme", "light") == "dark"
    bg_header = "#1e293b" if is_dark else "#d9d9d9"
    bg_subheader = "#334155" if is_dark else "#ececec"
    bg_first_col = "#1e293b" if is_dark else "#f5f5f5"
    text_color = "#f1f5f9" if is_dark else "#0f172a"
    text_soft = "#94a3b8" if is_dark else "#64748b"
    border_color = "#475569" if is_dark else "#aaa"
    border_cell = "#334155" if is_dark else "#bbb"

    # ---- Statistics ----
    stat_rows = ""
    for idx, p in enumerate(pairs_data):
        for role, lbl, mean, std, se in [
            (f"Pair {idx+1}", p["light_lbl"], p["light_mean"], p["light_std"], p["light_se"]),
            ("",              p["dark_lbl"],  p["dark_mean"],  p["dark_std"],  p["dark_se"]),
        ]:
            stat_rows += f"""
            <tr>
              <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;
                background:{bg_first_col};color:{text_color};white-space:nowrap;">{role}</td>
              <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">{lbl}</td>
              <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{mean:.4f}</td>
              <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['n']}</td>
              <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{std:.4f}</td>
              <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{se:.4f}</td>
            </tr>"""

    # ---- Correlations ----
    corr_rows = ""
    for idx, p in enumerate(pairs_data):
        cr = f"{p['corr_r']:.3f}" if not np.isnan(p["corr_r"]) else "—"
        cp = f"{p['corr_p']:.3f}" if not np.isnan(p["corr_p"]) else "—"
        corr_rows += f"""
        <tr>
          <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;
            background:{bg_first_col};color:{text_color};">Pair {idx+1}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">
            {p['light_lbl']} &amp; {p['dark_lbl']}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['n']}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{cr}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{cp}</td>
        </tr>"""

    # ---- Test ----
    test_rows = ""
    for idx, p in enumerate(pairs_data):
        sig2   = f"{p['p_two']:.3f}" if not np.isnan(p["p_two"]) else "—"
        is_sig = (not np.isnan(p["p_two"])) and p["p_two"] < 0.05
        if is_dark:
            sig_bg = "rgba(74, 222, 128, 0.15)" if is_sig else "rgba(96, 165, 250, 0.15)"
            sig_color = "#4ade80" if is_sig else "#60a5fa"
        else:
            sig_bg = "#f0fdf4" if is_sig else "#eaf4ff"
            sig_color = "#15803d" if is_sig else "#1d4ed8"

        test_rows += f"""
        <tr>
          <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;
            background:{bg_first_col};color:{text_color};white-space:nowrap;">Pair {idx+1}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">
            {p['light_lbl']} − {p['dark_lbl']}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['diff_mean']:.4f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['diff_std']:.4f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['diff_se']:.4f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['ci_low']:.4f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['ci_up']:.4f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['t']:.3f}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p['df']}</td>
          <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;
            background:{sig_bg};color:{sig_color};font-weight:700;">{sig2}</td>
        </tr>"""

    st.markdown(f"""
    <div style="margin:20px 0 8px 0;color:{text_color};">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid {border_color};
        padding-bottom:4px;">Paired Samples Statistics</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;color:{text_color};">
        <thead><tr style="background:{bg_header};">
          <th colspan="2" style="border:1px solid {border_color};padding:7px 12px;"></th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Mean</th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">N</th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Std. Deviation</th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Std. Error Mean</th>
        </tr></thead>
        <tbody>{stat_rows}</tbody>
      </table>
    </div>

    <div style="margin:16px 0 8px 0;color:{text_color};">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid {border_color};
        padding-bottom:4px;">Paired Samples Correlations</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;color:{text_color};">
        <thead><tr style="background:{bg_header};">
          <th colspan="2" style="border:1px solid {border_color};padding:7px 12px;"></th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">N</th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Correlation</th>
          <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Sig.</th>
        </tr></thead>
        <tbody>{corr_rows}</tbody>
      </table>
    </div>

    <div style="margin:16px 0 24px 0;color:{text_color};">
      <div style="font-weight:700;font-size:14px;border-bottom:2px solid {border_color};
        padding-bottom:4px;">Paired Samples Test</div>
      <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;color:{text_color};">
        <thead>
          <tr style="background:{bg_header};">
            <th colspan="2" style="border:1px solid {border_color};padding:7px 12px;"></th>
            <th colspan="5" style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">
              Paired Differences</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">t</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">df</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;background:{bg_subheader};color:{text_color};">
              Sig. (2-tailed)</th>
          </tr>
          <tr style="background:{bg_subheader};">
            <th colspan="2" style="border:1px solid {border_color};padding:7px 12px;"></th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Mean</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Std. Deviation</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Std. Error Mean</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">CI Lower 95%</th>
            <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">CI Upper 95%</th>
            <th colspan="3" style="border:1px solid {border_color};"></th>
          </tr>
        </thead>
        <tbody>{test_rows}</tbody>
      </table>
      <div style="font-size:11px;color:{text_soft};margin-top:5px;font-style:italic;">
        α = 0.05 · Two-tailed · 95% Confidence Interval of the Difference
      </div>
    </div>""", unsafe_allow_html=True)

def render_spss_wilcoxon(pairs_data):
    """
    Render output Wilcoxon identik dengan SPSS Style.
    Menampilkan tabel Ranks dan Test Statistics.
    """
    is_dark = st.session_state.get("app_theme", "light") == "dark"
    bg_header = "#1e293b" if is_dark else "#d9d9d9"
    bg_subheader = "#334155" if is_dark else "#ececec"
    bg_first_col = "#1e293b" if is_dark else "#f5f5f5"
    bg_sig_col = "rgba(96, 165, 250, 0.15)" if is_dark else "#eaf4ff" # light blue sig highlight
    text_color = "#f1f5f9" if is_dark else "#0f172a"
    text_soft = "#94a3b8" if is_dark else "#64748b"
    border_color = "#475569" if is_dark else "#aaa"
    border_cell = "#334155" if is_dark else "#bbb"

    ranks_rows = ""
    footnotes = []
    abc = "abcdefghijklmnopqrstuvwxyz"
    fn_idx = 0

    for pd_item in pairs_data:
        vn = pd_item["var_name"]
        l_lbl = pd_item["light_lbl"]
        d_lbl = pd_item["dark_lbl"]

        labels = ["", "", ""]
        hubungan = [
            f"{d_lbl} < {l_lbl}",
            f"{d_lbl} > {l_lbl}",
            f"{l_lbl} = {d_lbl}"
        ]

        n_vals = [pd_item['neg_n'], pd_item['pos_n'], pd_item['ties_n']]

        for i in range(3):
            current_letter = abc[fn_idx]
            if n_vals[i] > 0:
                labels[i] = f"<sup>{current_letter}</sup>"
                footnotes.append(f"{current_letter}. {hubungan[i]}")
            fn_idx += 1

        ranks_rows += f"""
        <tr>
            <td rowspan="4" style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;
                background:{bg_first_col};color:{text_color};vertical-align:middle;white-space:nowrap;">{vn}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">Negative Ranks</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['neg_n']}{labels[0]}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['neg_mean']}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['neg_sum']}</td>
        </tr>
        <tr>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">Positive Ranks</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['pos_n']}{labels[1]}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['pos_mean']}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['pos_sum']}</td>
        </tr>
        <tr>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};">Ties</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{pd_item['ties_n']}{labels[2]}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};"></td>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};"></td>
        </tr>
        <tr>
            <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;color:{text_color};">Total</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;font-weight:600;color:{text_color};">{pd_item['total_n']}</td>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};"></td>
            <td style="border:1px solid {border_cell};padding:7px 12px;color:{text_color};"></td>
        </tr>"""

    footnote_html = "<br>".join(footnotes) if footnotes else ""

    ranks_html = f"""
    <div style="margin:20px 0 8px 0;color:{text_color};">
        <div style="font-weight:700;font-size:14px;border-bottom:2px solid {border_color};padding-bottom:4px;margin-bottom:0;">Ranks</div>
        <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;color:{text_color};">
            <thead>
                <tr style="background:{bg_header};color:{text_color};">
                    <th colspan="2" style="border:1px solid {border_color};padding:7px 12px;"></th>
                    <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">N</th>
                    <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Mean Rank</th>
                    <th style="border:1px solid {border_color};padding:7px 12px;text-align:center;color:{text_color};">Sum of Ranks</th>
                </tr>
            </thead>
            <tbody>{ranks_rows}</tbody>
        </table>
        <div style="font-size:11px;color:{text_soft};margin-top:5px;font-style:italic;line-height:1.6;">
            {footnote_html}
        </div>
    </div>"""

    # ======================
    # TEST STATISTICS (SPSS STYLE)
    # ======================
    def get_z_superscript(pd_item):
        """
        Tentukan superscript Z sesuai SPSS:
        - Z negatif → based on negative ranks → superscript 'b'
        - Z positif → based on positive ranks → superscript 'c'
        """
        z = pd_item["z_val"]
        neg_n = pd_item["neg_n"]
        pos_n = pd_item["pos_n"]
        if neg_n == 0 and pos_n == 0:
            return "", ""
        elif z <= 0:
            return "b", "b. Based on negative ranks."
        else:
            return "c", "c. Based on positive ranks."

    # Header kolom: nama variabel tiap pasangan
    test_stat_headers = "".join([
        f'<th style="border:1px solid {border_color};padding:7px 12px;text-align:center;font-size:12px;color:{text_color};">{p["var_name"]}</th>'
        for p in pairs_data
    ])

    # Baris Z dengan superscript
    z_footnotes_dict = {}
    z_cells = ""
    for p in pairs_data:
        sup, note = get_z_superscript(p)
        if sup and sup not in z_footnotes_dict:
            z_footnotes_dict[sup] = note
        z_cells += f'<td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p["z_val"]:.3f}<sup>{sup}</sup></td>'

    # Baris Asymp. Sig
    p_cells = ""
    for p in pairs_data:
        p_cells += f'<td style="border:1px solid {border_cell};padding:7px 12px;text-align:right;color:{text_color};">{p["p_val"]:.3f}</td>'

    # Footnote Z
    z_footnote_html = "<br>".join(z_footnotes_dict.values())

    test_stats_html = f"""
    <div style="margin:16px 0 24px 0;color:{text_color};">
        <div style="font-weight:700;font-size:14px;border-bottom:2px solid {border_color};padding-bottom:4px;margin-bottom:0;">
            Test Statistics<sup>a</sup>
        </div>
        <table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:100%;color:{text_color};">
            <thead>
                <tr style="background:{bg_header};color:{text_color};">
                    <th style="border:1px solid {border_color};padding:7px 12px;text-align:left;"></th>
                    {test_stat_headers}
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;background:{bg_first_col};color:{text_color};">Z</td>
                    {z_cells}
                </tr>
                <tr>
                    <td style="border:1px solid {border_cell};padding:7px 12px;font-weight:600;background:{bg_sig_col};color:{text_color};">Asymp. Sig. (2-tailed)</td>
                    {p_cells}
                </tr>
            </tbody>
        </table>
        <div style="font-size:11px;color:{text_soft};margin-top:5px;font-style:italic;line-height:1.8;">
            a. Wilcoxon Signed Ranks Test<br>
            {z_footnote_html}
        </div>
    </div>"""

    st.markdown(ranks_html + test_stats_html, unsafe_allow_html=True)


def dataset_manager(df, expected_columns, save_path, title, filename_base):

    st.markdown(f"""
    <div style="font-size:16px;font-weight:600;color:{text_main};margin-bottom:8px;">
    Kelola Dataset
    </div>
    """, unsafe_allow_html=True)

    action = st.radio(
        "Pilih aksi",
        ["Export Dataset", "Import Dataset"],
        horizontal=True,
        key=f"dataset_action_{filename_base}"
    )

    # ======================
    # EXPORT
    # ======================
    if action == "Export Dataset":

        file_type = st.selectbox(
            "Pilih format file",
            ["Excel (.xlsx)", "CSV (.csv)", "PDF (.pdf)"],
            key=f"file_type_{filename_base}"
        )

        buffer = io.BytesIO()

        if file_type == "Excel (.xlsx)":
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Dataset")
            buffer.seek(0)
            st.download_button(
                "Download File",
                data=buffer,
                file_name=f"{filename_base}.xlsx"
            )

        elif file_type == "CSV (.csv)":
            csv = df.to_csv(index=False)
            st.download_button(
                "Download File",
                data=csv,
                file_name=f"{filename_base}.csv"
            )

        elif file_type == "PDF (.pdf)":
            doc = SimpleDocTemplate(buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []
            elements.append(Paragraph(title, styles["Title"]))
            elements.append(Spacer(1, 20))
            data = [df.columns.tolist()] + df.values.tolist()
            table = Table(data)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 8)
            ]))
            elements.append(table)
            doc.build(elements)
            buffer.seek(0)
            st.download_button(
                "Download File",
                data=buffer,
                file_name=f"{filename_base}.pdf"
            )

    # ======================
    # IMPORT
    # ======================
    elif action == "Import Dataset":

        # Inisialisasi session state untuk status import
        import_key = f"import_status_{filename_base}"
        if import_key not in st.session_state:
            st.session_state[import_key] = None  # None | "success" | "error"

        # Tampilkan pesan hasil import jika ada
        if st.session_state[import_key] == "success":
            st.success("Dataset berhasil diimport!")
            if st.button("Upload File Lain", key=f"reset_import_{filename_base}"):
                st.session_state[import_key] = None
                st.rerun()
            return  # Hentikan render form upload

        uploaded_file = st.file_uploader(
            "Upload file dataset",
            type=["xlsx", "csv"],
            key=f"upload_{filename_base}"
        )

        if uploaded_file is not None:

            if uploaded_file.name.endswith(".xlsx"):
                df_new = pd.read_excel(uploaded_file)
            else:
                df_new = pd.read_csv(uploaded_file)

            if list(df_new.columns) != expected_columns:
                st.error("Struktur dataset tidak sesuai. Pastikan kolom file sama persis dengan template.")
            else:
                st.markdown("**Preview Data:**")
                st.dataframe(df_new.head(5), use_container_width=True)

                if st.button(
                    "Konfirmasi Import",
                    type="primary",
                    use_container_width=True,
                    key=f"confirm_import_{filename_base}"
                ):
                    try:
                        # Tentukan table & tipe berdasarkan filename_base
                        if "time_on_task" in filename_base:
                            save_data("data_tot", current_user, app, df_new)
                        elif "error_rate" in filename_base:
                            save_data("data_error", current_user, app, df_new)
                        elif "ueq_light" in filename_base:
                            save_ueq("data_ueq_light", current_user, app, df_new)
                        elif "ueq_dark" in filename_base:
                            save_ueq("data_ueq_dark", current_user, app, df_new)
                        elif "preferensi_positif" in filename_base:
                            save_pref("data_pref_pos", current_user, app, df_new)
                        elif "preferensi_negatif" in filename_base:
                            save_pref("data_pref_neg", current_user, app, df_new)
                        else:
                            df_new.to_csv(save_path, index=False)
                        st.session_state[import_key] = "success"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gagal menyimpan: {e}")

def render_delete_button(file_path, label, columns, default_value=0, key_suffix=""):
    confirm_key = f"confirm_delete_{key_suffix}"
    if confirm_key not in st.session_state:
        st.session_state[confirm_key] = False

    if not st.session_state[confirm_key]:
        if st.button(f"Hapus Data {label}", use_container_width=True,
                     type="secondary", key=f"btn_delete_{key_suffix}"):
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
            if st.button("Ya, Hapus", type="primary", use_container_width=True,
                         key=f"confirm_yes_{key_suffix}"):
                try:
                    # Hapus dari Supabase berdasarkan key_suffix
                    SUPABASE_URL = st.secrets["SUPABASE_URL"]
                    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
                    headers = {
                        "apikey": SUPABASE_KEY,
                        "Authorization": f"Bearer {SUPABASE_KEY}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal"
                    }
                    table_map = {
                        "tot": "data_tot",
                        "error": "data_error",
                        "ueq_light": "data_ueq_light",
                        "ueq_dark": "data_ueq_dark",
                        "pref_pos": "data_pref_pos",
                        "pref_neg": "data_pref_neg",
                    }
                    if key_suffix in table_map:
                        requests.delete(
                            f"{SUPABASE_URL}/rest/v1/{table_map[key_suffix]}?username=eq.{current_user}&app=eq.{app}",
                            headers=headers
                        )
                    st.session_state[confirm_key] = False
                    st.success(f"Data {label} berhasil dihapus!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal menghapus: {e}")
# ── Theme toggle (session_state) — default: light ─────────────────────────
if "app_theme" not in st.session_state:
    q_theme = st.query_params.get("theme", "light")
    st.session_state["app_theme"] = q_theme

theme = st.session_state["app_theme"]
if st.query_params.get("theme") != theme:
    st.query_params["theme"] = theme

if theme == "dark":
    plt.style.use("dark_background")
else:
    plt.style.use("default")

# Python colour variables (used in f-string HTML throughout the file)
if theme == "dark":
    bg_main    = "#020617"
    bg_card    = "#0f172a"
    bg_sidebar = "#020617"
    bg_insight = "#1e293b"
    text_main  = "#f1f5f9"
    text_soft  = "#94a3b8"
    border     = "#1e293b"
else:
    bg_main    = "#f8fafc"
    bg_card    = "#ffffff"
    bg_sidebar = "#f8fafc"
    bg_insight = "#f1f5f9"
    text_main  = "#111827"
    text_soft  = "#6b7280"
    border     = "#e5e7eb"

# ======================
# DARK MODE CSS OVERRIDE
# ======================
# config.toml = light, jadi dark mode butuh override manual yang komprehensif
if theme == "dark":
    st.markdown("""
    <style>
    /* ══════════════════════════════════════════════════
       DARK MODE — Comprehensive CSS Override
       config.toml = light, so we override everything here
    ══════════════════════════════════════════════════ */

    /* 1. CSS Variables */
    :root {
        --background-color: #020617 !important;
        --secondary-background-color: #0f172a !important;
        --text-color: #f1f5f9 !important;
        --primary-color: #6366f1 !important;
        --secondary-color: #818cf8 !important;
        --secondary-text-hover-color: #0f172a !important;
    }
    
    /* 2. App & main background */
    .stApp {
        background-color: #020617 !important;
    }
    section.main, section.main > div, .block-container {
        background-color: #020617 !important;
    }

    /* 3. Global text — use .stApp as scope to allow inline overrides */
    .stApp p, .stApp li, .stApp td, .stApp th,
    .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
    .stApp label, .stApp legend,
    .stMarkdown, .stMarkdown p, .stMarkdown li, .stMarkdown span,
    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span,
    [data-testid="stText"], [data-testid="stWidgetLabel"],
    [data-testid="stCaptionContainer"] {
        color: #f1f5f9 !important;
    }

    /* 4. Sidebar — all children inherit dark */
    [data-testid="stSidebar"] {
        background-color: #020617 !important;
    }
    [data-testid="stSidebar"] > div,
    [data-testid="stSidebar"] section,
    [data-testid="stSidebar"] .block-container {
        background-color: #020617 !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #f1f5f9 !important;
    }

    /* 5. Sidebar — input, select, number input */
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div,
    [data-testid="stSidebar"] [data-baseweb="textarea"] > div,
    [data-testid="stSidebar"] input[type="text"],
    [data-testid="stSidebar"] input[type="number"],
    [data-testid="stSidebar"] [data-testid="stNumberInput"] > div {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }
    [data-testid="stSidebar"] input {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
    }
    [data-testid="stSidebar"] input::placeholder {
        color: #64748b !important;
    }

    /* 6. Sidebar — expander & its inner content */
    [data-testid="stSidebar"] details,
    [data-testid="stSidebar"] details > div,
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"],
    [data-testid="stSidebar"] [data-testid="stExpanderDetails"] > div {
        background-color: #0f172a !important;
        border-color: rgba(99,102,241,0.3) !important;
    }
    /* Expander header/summary — background + text */
    [data-testid="stSidebar"] details summary,
    [data-testid="stSidebar"] details summary > div,
    [data-testid="stSidebar"] [data-testid="stExpander"] > div:first-child,
    [data-testid="stSidebar"] [data-testid="stExpanderToggleIcon"],
    [data-testid="stSidebar"] [data-testid="stExpanderToggleIcon"] ~ div {
        background-color: #0f172a !important;
        color: #6366f1 !important;
    }
    /* Streamlit wraps expander in an extra div — force it dark too */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background-color: #0f172a !important;
        border: 1px solid rgba(99,102,241,0.3) !important;
        border-radius: 12px !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] > div {
        background-color: #0f172a !important;
    }

    /* 7. Main content — input, select */
    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-baseweb="select"] li,
    [data-baseweb="textarea"] > div,
    [data-baseweb="input"] input,
    [data-baseweb="select"] input,
    input[type="text"], input[type="number"] {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }
    input::placeholder, textarea::placeholder {
        color: #64748b !important;
    }

    /* 8. Dropdown popover */
    [data-baseweb="popover"],
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"],
    [data-baseweb="popover"] li,
    [data-baseweb="list"] {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
    }
    [data-baseweb="popover"] li:hover,
    [data-baseweb="option"]:hover {
        background-color: #334155 !important;
    }

    /* 9. Cards & bordered containers */
    [data-testid="stVerticalBlockBorderWrapper"] > div,
    div[data-testid="stMetricV2"],
    .card, .p-card, .pref-card, .kpi-card,
    .sidebar-active-card, .sidebar-user-card {
        background-color: #0f172a !important;
        border-color: #1e293b !important;
    }

    /* 10. DataFrames & tables */
    [data-testid="stDataFrame"],
    [data-testid="stTable"],
    .stDataFrame,
    .stTable,
    div[data-component-name="st.dataframe"],
    div[data-component-name="st.data_editor"] {
        filter: invert(0.9) hue-rotate(180deg) !important;
        background:#0f172a !important;
    }

    [data-testid="stDataFrame"] div[role="grid"]{
        background:#0f172a !important;
    }

    [data-testid="stDataFrame"] div[role="columnheader"]{
        background:#1e293b !important;
        color:#f1f5f9 !important;
    }

    [data-testid="stDataFrame"] div[role="gridcell"]{
        background:#0f172a !important;
        color:#f1f5f9 !important;
    }

    [data-testid="stDataFrame"] input{
        background:#0f172a !important;
        color:#f1f5f9 !important;
    }

    /* 11. Main area expanders */
    /* Modern Expander */
    [data-testid="stExpander"]{
        border:1px solid rgba(99,102,241,.18) !important;
        border-radius:14px !important;
        overflow:hidden !important;
        background:#0f172a !important;
        box-shadow:0 6px 20px rgba(0,0,0,.18);
    }

    [data-testid="stExpander"] details{
        background:#0f172a !important;
    }

    [data-testid="stExpander"] summary{
        background:#111827 !important;
        padding:16px 20px !important;
        font-size:16px !important;
        font-weight:700 !important;
        color:#f8fafc !important;
        border-bottom:1px solid rgba(99,102,241,.15);
    }

    [data-testid="stExpanderDetails"]{
        background:#0f172a !important;
        padding:22px !important;
    }
                
    .stDownloadButton button{
        width:220px;
        height:44px;
        border-radius:10px !important;
    }

    .stRadio label{
        font-weight:600 !important;
    }

    [data-baseweb="select"]>div{
        min-height:44px !important;
        border-radius:10px !important;
    }

    /* 12. File uploader */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] > div,
    [data-testid="stFileUploaderDropzone"] {
        background-color: #0f172a !important;
        border-color: #334155 !important;
        color: #f1f5f9 !important;
    }
    [data-testid="stFileUploader"] span,
    [data-testid="stFileUploader"] p,
    [data-testid="stFileUploader"] small {
        color: #94a3b8 !important;
    }

    /* 13. Radio & checkbox */
    [data-testid="stRadio"] label,
    [data-testid="stRadio"] span,
    [data-testid="stCheckbox"] label,
    [data-testid="stCheckbox"] span {
        color: #f1f5f9 !important;
    }

    /* 14. Tabs */
    [data-baseweb="tab-list"] {
        background-color: transparent !important;
        border-bottom-color: #1e293b !important;
    }
    [data-baseweb="tab"] {
        color: #94a3b8 !important;
        background-color: transparent !important;
    }
    [aria-selected="true"][data-baseweb="tab"] {
        color: #6366f1 !important;
        border-bottom-color: #6366f1 !important;
    }
    [data-baseweb="tab-panel"] {
        background-color: transparent !important;
    }

    /* 15. Alerts */
    .stAlert, [data-testid="stAlert"] {
        background-color: rgba(99,102,241,0.1) !important;
        border-color: rgba(99,102,241,0.3) !important;
    }
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span {
        color: #f1f5f9 !important;
    }
    /* Info box */
    [data-testid="stAlert"][data-baseweb="notification"] {
        background-color: rgba(99,102,241,0.12) !important;
    }

    /* 16. Metrics */
    [data-testid="stMetricLabel"] { color: #94a3b8 !important; }
    [data-testid="stMetricValue"] { color: #f1f5f9 !important; }
    [data-testid="stMetricDelta"] { color: #94a3b8 !important; }

    /* 17. Number input — polished dark styling */
    [data-testid="stNumberInput"] > div {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        transition: all 0.2s ease-in-out !important;
    }
    [data-testid="stNumberInput"] > div:hover {
        border-color: #475569 !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    }
    [data-testid="stNumberInput"] > div:focus-within {
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
    }
    [data-testid="stNumberInput"] > div > div:first-child {
        flex: 1 !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        background-color: transparent !important;
    }
    [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stNumberInput"] [data-baseweb="input"] > div,
    [data-testid="stNumberInput"] [data-baseweb="input"] * {
        background-color: transparent !important;
        border: none !important;
    }
    [data-testid="stNumberInput"] input {
        background-color: transparent !important;
        color: #f1f5f9 !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 12px !important;
        height: 100% !important;
        width: 100% !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }
    /* Hide browser's built-in spin buttons */
    [data-testid="stNumberInput"] input::-webkit-search-cancel-button,
    [data-testid="stNumberInput"] input::-webkit-inner-spin-button,
    [data-testid="stNumberInput"] input::-webkit-outer-spin-button {
        -webkit-appearance: none !important;
        appearance: none !important;
        margin: 0 !important;
    }
    [data-testid="stNumberInput"] input[type=number] {
        -moz-appearance: textfield !important;
    }
    [data-testid="stNumberInput"] > div > div:last-child {
        background-color: transparent !important;
        border-left: 1px solid #334155 !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        gap: 0px !important;
        padding: 0px !important;
        margin: 0px !important;
    }
    [data-testid="stNumberInput"] button {
        background-color: transparent !important;
        color: #94a3b8 !important;
        border: none !important;
        border-radius: 0px !important;
        width: 32px !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 16px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out !important;
        cursor: pointer !important;
        margin: 0 !important;
        padding: 0 !important;
    }
    [data-testid="stNumberInput"] button:hover {
        background-color: rgba(255, 255, 255, 0.06) !important;
        color: #6366f1 !important;
    }
    [data-testid="stNumberInput"] button:active {
        background-color: rgba(255, 255, 255, 0.1) !important;
    }
    [data-testid="stNumberInput"] button:first-child {
        border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
    }
    /* Active +/- */
    [data-testid="stNumberInput"] button:active {
        background-color: #4338ca !important;
        transform: scale(0.95) !important;
        box-shadow: none !important;
    }
    /* Tooltip help icon */
    [data-testid="stNumberInput"] svg[data-testid="stTooltipIcon"],
    [data-testid="stWidgetLabel"] svg {
        color: #475569 !important;
        fill: #475569 !important;
        transition: color 0.2s ease !important;
    }
    [data-testid="stWidgetLabel"]:hover svg {
        color: #6366f1 !important;
        fill: #6366f1 !important;
    }


    /* 18. Scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }

    /* 19. HR divider */
    hr { border-color: #1e293b !important; }

    /* 20. Code & pre */
    code { background: #1e293b !important; color: #a78bfa !important; }
    pre { background: #0f172a !important; border-color: #1e293b !important; }

    /* 21. Buttons — default secondary */
    [data-testid="stBaseButton-secondary"] {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
        border-color: #334155 !important;
    }
    [data-testid="stBaseButton-secondary"]:hover {
        background-color: #334155 !important;
    }

    /* 22. Caption & small */
    .stCaption, [data-testid="stCaptionContainer"],
    small { color: #64748b !important; }

    /* 23. Tooltip */
    [data-testid="stTooltipContent"] {
        background-color: #1e293b !important;
        color: #f1f5f9 !important;
    }

    /* 24. Dialog / Modal Dark Mode Override */
    div[data-testid="stDialog"] [role="dialog"],
    div[role="dialog"],
    [data-testid="stModal"] > div {
        background-color: #0f172a !important;
        color: #f1f5f9 !important;
        border: 1px solid #1e293b !important;
        border-radius: 16px !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
    }

    /* Headings and text labels inside dialog */
    div[data-testid="stDialog"] h1,
    div[data-testid="stDialog"] h2,
    div[data-testid="stDialog"] h3,
    div[data-testid="stDialog"] h4,
    div[data-testid="stDialog"] h5,
    div[data-testid="stDialog"] h6,
    div[data-testid="stDialog"] label,
    div[data-testid="stDialog"] p,
    div[data-testid="stDialog"] span,
    div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] p,
    div[data-testid="stDialog"] [data-testid="stMarkdownContainer"] span {
        color: #f1f5f9 !important;
    }

    /* Close button ("X") styling inside dialog */
    div[data-testid="stDialog"] button[aria-label="Close"],
    div[role="dialog"] button[aria-label="Close"] {
        color: #94a3b8 !important;
        background-color: transparent !important;
        border: none !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stDialog"] button[aria-label="Close"]:hover,
    div[role="dialog"] button[aria-label="Close"]:hover {
        color: #f1f5f9 !important;
        background-color: rgba(255, 255, 255, 0.1) !important;
    }
    div[data-testid="stDialog"] button[aria-label="Close"] svg,
    div[role="dialog"] button[aria-label="Close"] svg {
        fill: currentColor !important;
        color: currentColor !important;
    }
    </style>
    """, unsafe_allow_html=True)

# ======================
# CSS MODERN
# ======================

st.markdown("""
<style>

:root {
    --secondary-color: #6366F1;
    --secondary-text-hover-color: #FFFFFF;
    --background-color: #f8fafc;
    --secondary-background-color: #ffffff;
    --text-color: #111827;
    --text-soft: #6b7280;
    --border-color: #e5e7eb;
}

.stButton > button[kind="secondary"] {
    border-radius: 30px !important;
    border: 1px solid var(--secondary-color) !important;
    background-color: transparent !important;
    color: var(--secondary-color) !important;
    padding: 8px 16px !important;
    transition: all 0.3s ease !important;
}

.stButton > button[kind="secondary"]:hover {
    background-color: var(--secondary-color) !important;
    color: var(--secondary-text-hover-color) !important;
    box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3) !important;
}

/* Disable typing in selectbox search inside dialogs */
div[data-testid="stDialog"] div[data-baseweb="select"] input,
div[role="dialog"] div[data-baseweb="select"] input,
[data-testid="stModal"] div[data-baseweb="select"] input {
    pointer-events: none !important;
    caret-color: transparent !important;
    user-select: none !important;
}
/* Sembunyikan header Streamlit (Deploy & Menu) dan action elements di kanan atas */
header[data-testid="stHeader"],
[data-testid="stHeader"],
[data-testid="stHeaderActionElements"],
[data-testid="stMainMenu"],
button[id="MainMenu"],
div[class*="stHeaderActionElements"],
button[class*="stHeaderActionElements"] {
    display: none !important;
}

/* Sidebar Styling yang lebih clean */
[data-testid="stSidebar"]  {
    background-color: var(--secondary-background-color) !important;
    border-right: 1px solid rgba(128, 128, 128, 0.2) !important;
}
[data-testid="stSidebar"] .stMarkdown p, 
[data-testid="stSidebar"] label, 
[data-testid="stSidebar"] .sidebar-title {
    color: var(--text-color) !important;
}
            
/* Header di Sidebar */
.sidebar-branding {
    padding: 4px 0;
    margin-bottom: 12px;
    border-bottom: 2px solid rgba(128, 128, 128, 0.2);
}

.sidebar-title {
    font-size: 16px;
    font-weight: 800;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
            
.stApp {
    background-color: var(--background-color);
}

/* Kategori Menu */
.menu-label {
    font-weight: 700;
    font-size: 8px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 4px !important;
    margin-top: 6px !important;
}

/* Tombol Reset Minimalis */
.stButton > button {
    width: 100%;
    border-radius: 4px;
    font-size: 11px !important;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    transition: all 0.3s;
    padding: 6px !important;
}

* {
    transition: background 0.3s ease, color 0.3s ease;
}

[data-testid="stMetricV2"] {
    background-color: var(--secondary-background-color);
    color: var(--text-color);
}
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    background-color: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 12px !important;
}

.block-container {
    max-width: 1500px;
    padding-top: 24px;
}

/* Tambahkan ini di dalam <style> */
.stDataFrame, .stTable {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(128, 128, 128, 0.2);
}

.chart-container {
    padding: 10px;
    background: transparent;
}

.main-title {
    font-size: 28px;
    font-weight: 600;
    color: var(--text-color);
}

.subtitle {
    color: var(--text-color);
    opacity: 0.7;
    margin-bottom: 30px;
}

.section-title {
    font-size: 18px;
    font-weight: 600;
    margin-top: 40px;
    margin-bottom: 15px;
}

.card {
    background: var(--secondary-background-color) !important;
    padding: 24px;
    border-radius: 20px;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    transition: all 0.3s ease;
    height: 100%;
    color: var(--text-color) !important;
    margin-bottom: 20px !important;
}

/* Hanya target Streamlit markdown container, bukan semua elemen inline */
.stMarkdown {
    color: var(--text-color);
}
.stMarkdown p {
    color: var(--text-color);
}
            
.stAlert {
    background-color: rgba(128, 128, 128, 0.1) !important;
    color: var(--text-color) !important;
}

details {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 8px;
}

/* Inner body content of main-area expanders */
details > div,
[data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] > div {
    background: var(--secondary-background-color) !important;
    color: var(--text-color) !important;
}

/* Download button in expander - make it stand out */
[data-testid="stExpander"] [data-testid="stDownloadButton"] button,
[data-testid="stExpander"] [data-testid="stDownloadButton"] button:focus {
    background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}

[data-testid="stExpander"] [data-testid="stDownloadButton"] button:hover {
    background: linear-gradient(135deg, #818cf8, #6366f1) !important;
    box-shadow: 0 4px 12px rgba(99,102,241,0.4) !important;
    transform: translateY(-1px) !important;
}

/* Radio labels inside expander */
[data-testid="stExpander"] .stRadio label,
[data-testid="stExpander"] .stRadio span {
    color: var(--text-color) !important;
}

/* Selectbox inside expander */
[data-testid="stExpander"] [data-baseweb="select"] > div {
    background: var(--background-color) !important;
    color: var(--text-color) !important;
    border-color: rgba(128,128,128,0.3) !important;
}

div[data-testid="stSidebar"] details {
    background: rgba(128, 128, 128, 0.05) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 12px !important;
}

div[data-testid="stSidebar"] details summary {
    color: var(--text-color) !important;
    font-weight: 700 !important;
    font-size: 12px !important;
    opacity: 0.8;
}

.card:hover {
    transform: translateY(-5px);
    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    border-color: #6366f1;
}

.metric-container {
    display: flex;
    flex-direction: column;
}

.metric-title {
    font-size: 14px;
    font-weight: 500;
    color: #64748b;
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.metric-value {
    font-size: 26px;
    font-weight: 800;
    color: var(--text-color) !important;
    line-height: 1.2;
}

[data-testid="stSidebar"] div[data-baseweb="select"] > div {
    background-color: var(--background-color) !important;
    color: var(--text-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
}

.metric-footer {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(128, 128, 128, 0.15);
}

.status-badge {
    display: inline-block;
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    margin-top: 5px;
}

/* Warna identitas untuk label */
.val-light {
    color: #6366f1;
    font-weight: 800;
}

.val-dark {
    color: #a78bfa;
    font-weight: 800;
}

.vs-divider {
    color: #94a3b8;
    font-size: 14px;
    font-weight: 400;
    margin: 0 4px;
}

.pref-card {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 15px;
    padding: 20px;
    text-align: center;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    color: var(--text-color) !important;
}
.pref-label {
    font-size: 12px;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    margin-bottom: 10px;
}
.pref-value {
    font-size: 20px;
    font-weight: 700;
    color: var(--text-color) !important;
}

h3 {
    font-size: 16px !important;
}

.p-card {
    background-color: var(--secondary-background-color) !important;
    padding: 20px;
    border-radius: 15px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    margin-bottom: 20px;
    color: var(--text-color) !important;
}

/* Kasih jarak normal sidebar */
[data-testid="stSidebar"] .block-container {
    padding-top: 5px !important;
    padding-bottom: 5px !important;
}

/* Biar tiap komponen ga nempel */
section[data-testid="stSidebar"] .stSelectbox,
section[data-testid="stSidebar"] .stNumberInput {
    margin-top: 6px;
    margin-bottom: 6px !important;
}
            
.sidebar-header h1 {
    font-size: 18px !important;
}

.sidebar-header p {
    font-size: 9px !important;
}

.sidebar-card {
    padding: 10px !important;
    font-size: 10px !important;
}
            
section[data-testid="stSidebar"] > div:first-child {
    height: 100vh;
    display: flex;
    flex-direction: column;
    
}
            
div[data-baseweb="select"] {
    margin-top: 4px;
}

/* Fix jarak label ke input */
label[data-testid="stWidgetLabel"] {
    margin-bottom: 4px !important;
}

/* Khusus sidebar selectbox */
section[data-testid="stSidebar"] .stSelectbox {
    margin-bottom: 10px;
} 

section[data-testid="stSidebar"] [data-baseweb="select"],
section[data-testid="stSidebar"] [data-baseweb="select"] *,
section[data-testid="stSidebar"] [data-baseweb="select"] input {
    cursor: pointer !important;
}
            
/* Manage Applications expander — styling keren */
    div[data-testid="stSidebar"] details {
        background: rgba(128, 128, 128, 0.05) !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        border-radius: 12px !important;
        transition: all 0.3s ease !important;
    }

    div[data-testid="stSidebar"] details:hover {
        border-color: #6366f1 !important;
        box-shadow: 0 4px 12px rgba(99,102,241,0.15) !important;
    }

    div[data-testid="stSidebar"] details summary {
        color: var(--text-color) !important;
        font-weight: 700 !important;
        font-size: 12px !important;
        letter-spacing: 0.3px !important;
        padding: 10px 14px !important;
        opacity: 0.8;
    }

    div[data-testid="stSidebar"] details summary:hover {
        color: #6366f1 !important;
        opacity: 1;
    }

    div[data-testid="stSidebar"] details summary svg {
        fill: #6366f1 !important;
        color: #6366f1 !important;
    }

/* Custom classes for theme-adaptive styling */
.sidebar-active-card {
    background: rgba(128, 128, 128, 0.08);
    padding: 18px;
    border-radius: 14px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    margin-top: 16px;
}
.sidebar-active-label {
    font-size: 11px;
    color: #6366F1;
    font-weight: 800;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.sidebar-active-value {
    font-size: 18px;
    font-weight: 800;
    color: var(--text-color);
    margin-bottom: 8px;
}
.sidebar-user-card {
    background: rgba(128, 128, 128, 0.08);
    padding: 14px 18px;
    border-radius: 14px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    font-size: 12px;
    color: var(--text-color);
    text-align: center;
    margin-bottom: 12px;
}
.unggul-light-card {
    background-color: rgba(99, 102, 241, 0.1);
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #6366f1;
}
.unggul-light-title {
    color: #6366f1;
}
.unggul-dark-card {
    background-color: rgba(148, 163, 184, 0.1);
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid var(--text-color);
}
.unggul-dark-title {
    color: var(--text-color);
}
.kpi-card {
    background: var(--secondary-background-color) !important;
    border: 1px solid rgba(128, 128, 128, 0.2) !important;
    border-radius: 14px;
    padding: 20px 18px;
    height: 100%;
    margin-bottom: 20px !important;
}
.kpi-title {
    font-size: 10px;
    font-weight: 700;
    color: #94A3B8;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 16px;
}
.kpi-label {
    font-size: 12px;
    color: var(--text-color);
    display: flex;
    align-items: center;
    gap: 6px;
    opacity: 0.8;
}
.kpi-value-light {
    font-size: 16px;
    font-weight: 700;
    color: #6366F1 !important;
}
.kpi-value-dark {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-color) !important;
}
.kpi-divider {
    height: 1px;
    background: rgba(128, 128, 128, 0.15);
}
.pref-value-text {
    font-size: 18px;
    font-weight: 700;
    color: var(--text-color) !important;
    margin-bottom: 8px;
}
.pref-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 600;
    background: rgba(128, 128, 128, 0.15);
    color: var(--text-color);
    padding: 3px 10px;
    border-radius: 20px;
}

/* ========================================================
   RESPONSIVE GRID COLUMN RULES & MOBILE OPTIMIZATIONS
   ======================================================== */
@media (max-width: 1024px) {
    /* For tablets and smaller: allow columns to wrap */
    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: 16px !important;
    }
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 220px !important;
        flex: 1 1 calc(50% - 16px) !important;
        width: 100% !important;
    }
}

@media (max-width: 767px) {
    /* For mobile screens: force full width vertical stack */
    [data-testid="stHorizontalBlock"] > [data-testid="column"] {
        min-width: 100% !important;
        width: 100% !important;
        flex: 1 1 100% !important;
    }
    
    /* Clean up container paddings for tight mobile screens */
    .block-container {
        padding-left: 12px !important;
        padding-right: 12px !important;
        padding-top: 16px !important;
    }
    
    /* Ensure tables can scroll horizontally without overflowing the page */
    .stDataFrame, .stTable {
        width: 100% !important;
        overflow-x: auto !important;
    }
    
    /* Optimize fonts and padding inside KPI cards on mobile */
    .kpi-card {
        padding: 16px 14px !important;
    }
    
    /* Scaled down heading fonts on mobile */
    h1 {
        font-size: 1.8rem !important;
    }
    h2 {
        font-size: 1.4rem !important;
    }
    h3 {
        font-size: 1.1rem !important;
    }
            
    /* MOBILE ADJUSTMENTS: Allow sidebar to collapse naturally */
    [data-testid="stSidebar"] {
        display: flex !important;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        display: none !important;
        width: 0 !important;
        min-width: 0 !important;
    }
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        top: 8px !important;
        left: 8px !important;
        z-index: 999999 !important;
    }
    header[data-testid="stHeader"] {
        display: flex !important;
        background-color: var(--secondary-background-color, #ffffff) !important;
        border-bottom: 1px solid rgba(128, 128, 128, 0.15) !important;
        height: 50px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    header[data-testid="stHeader"]::after {
        content: "UX Analytics" !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #2563eb !important;
        position: absolute !important;
        left: 52px !important;
        top: 50% !important;
        transform: translateY(-50%) !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMainViewContainer"] {
        margin-left: 0 !important;
        width: 100% !important;
    }
    [data-testid="stMainViewContainer"] {
        margin-left: 0 !important;
        width: 100% !important;
    }
}
            
    

</style>
""", unsafe_allow_html=True)

# Bridge to disable search typing inside the selectbox in the dialog
import streamlit.components.v1 as components
components.html("""
<script>
    const parentDoc = window.parent.document;
    const makeReadonly = () => {
        const selector = 'div[data-testid="stDialog"] div[data-baseweb="select"] input, div[role="dialog"] div[data-baseweb="select"] input, [data-testid="stModal"] div[data-baseweb="select"] input';
        const inputs = parentDoc.querySelectorAll(selector);
        inputs.forEach(input => {
            if (!input.readOnly) {
                input.readOnly = true;
                input.style.caretColor = 'transparent';
                input.style.pointerEvents = 'none';
            }
        });
    };
    makeReadonly();
    if (!window.parent.readonlySelectboxInterval) {
        window.parent.readonlySelectboxInterval = setInterval(makeReadonly, 100);
    }
</script>
""", height=0, width=0)

# CSS override tema — blok f-string terpisah, hanya berisi aturan tema
st.markdown(f"""
<style>
[data-testid="stSidebar"] {{
    background-color: {bg_sidebar} !important;
    background: {bg_sidebar} !important;
    opacity: 1 !important;
    border-right: 1px solid {border} !important;
}}
header[data-testid="stHeader"] {{
    background-color: {bg_card} !important;
    background: {bg_card} !important;
    opacity: 1 !important;
}}
[data-testid="stSidebarCollapsedControl"] {{
    background-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
}}
[data-testid="stSidebarCollapsedControl"] button {{
    background-color: transparent !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}}
[data-testid="stSidebarCollapsedControl"] button::before,
[data-testid="collapsedControl"] button::before {{
    content: "" !important;
    display: block !important;
    width: 20px !important;
    height: 20px !important;
    background-color: {text_main} !important;
    -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='3' y1='12' x2='21' y2='12'%3E%3C/line%3E%3Cline x1='3' y1='6' x2='21' y2='6'%3E%3C/line%3E%3Cline x1='3' y1='18' x2='21' y2='18'%3E%3C/line%3E%3C/svg%3E") !important;
    mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='3' y1='12' x2='21' y2='12'%3E%3C/line%3E%3Cline x1='3' y1='6' x2='21' y2='6'%3E%3C/line%3E%3Cline x1='3' y1='18' x2='21' y2='18'%3E%3C/line%3E%3C/svg%3E") !important;
    -webkit-mask-repeat: no-repeat !important;
    mask-repeat: no-repeat !important;
    -webkit-mask-size: contain !important;
    mask-size: contain !important;
}}
[data-testid="stSidebarCollapsedControl"] svg,
[data-testid="stSidebarCollapsedControl"] button svg,
[data-testid="collapsedControl"] svg {{
    display: none !important;
}}
[data-testid="stMetricV2"] {{
    background-color: {bg_card} !important;
    color: {text_main} !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"] > div {{
    background-color: {bg_card} !important;
}}
.main-title {{ color: {text_main} !important; }}
.subtitle {{ color: {text_soft} !important; }}
.card {{
    background: {bg_card} !important;
    border-color: {border} !important;
    color: {text_main} !important;
}}
.card b, .card strong {{ color: {text_main} !important; }}
.card span {{ color: {text_soft} !important; }}
.card li {{ color: {text_main} !important; }}
.metric-title {{ color: {text_soft} !important; }}
.metric-value {{ color: {text_main} !important; }}
.pref-card {{
    background: {bg_card} !important;
    border-color: {border} !important;
    color: {text_main} !important;
}}
.pref-label {{ color: {text_soft} !important; }}
.pref-value {{ color: {text_main} !important; }}
.p-card {{
    background-color: {bg_card} !important;
    border-color: {border} !important;
    color: {text_main} !important;
}}
/* Theme toggle button */
#btn_theme_toggle, button[key="btn_theme_toggle"],
[data-testid="stSidebar"] button:has(> div > p:contains("Dark Mode")),
[data-testid="stSidebar"] button:has(> div > p:contains("Light Mode")) {{
    background: {'rgba(167,139,250,0.15)' if theme == 'dark' else 'rgba(99,102,241,0.1)'} !important;
    color: {'#a78bfa' if theme == 'dark' else '#4f46e5'} !important;
    border: 1px solid {'rgba(167,139,250,0.4)' if theme == 'dark' else 'rgba(99,102,241,0.3)'} !important;
    border-radius: 20px !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    margin-bottom: 8px !important;
    transition: all 0.2s ease !important;
}}
</style>
""", unsafe_allow_html=True)


# ========================================================
# 1. TEMPATKAN FUNGSI GLOBAL DI SINI (SETELAH IMPORT)
# ========================================================
def create_donut_chart(data_dict, colors):
    if not data_dict: 
        return None
    fig = go.Figure(data=[go.Pie(
        labels=list(data_dict.keys()),
        values=list(data_dict.values()),
        hole=.6,
        marker=dict(colors=colors, line=dict(color='#FFFFFF', width=2)),
        textinfo='none', 
        showlegend=False, 
        hoverinfo='label+percent'
    )])
    fig.update_layout(
        margin=dict(t=0, b=0, l=0, r=0),
        height=160,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
    )
    return fig

# ======================
# SIDEBAR UI (MODERN VERSION)
# ======================

if not render_auth_page():
    st.stop()

current_user = st.session_state.get("current_user", "default")
USER_DIR = os.path.join(BASE_DIR, "userdata", current_user)

if "last_user" not in st.session_state or st.session_state["last_user"] != current_user:
    st.session_state["last_user"] = current_user
    st.session_state["app_list"] = load_app_list(current_user)

with st.sidebar:

    # ======================
    # BRANDING HEADER (Orbicular style)
    # ======================
    st.markdown(f"""
        <!-- University Branding -->
        <div class="sidebar-univ-full" style="font-size: 10px; font-weight: 700; color: {text_soft}; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px; padding-left: 2px;">
            Universitas Islam Indonesia
        </div>
        <div class="sidebar-univ-short" style="display: none; font-size: 10px; font-weight: 700; color: {text_soft}; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 12px; padding-left: 2px;">
            UII
        </div>
        
        <!-- Logo and Title -->
        <div class="brand-logo-container" style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding-left: 2px;">
            <div style="background-color: #1d4ed8; color: white; border-radius: 50%; width: 26px; height: 26px; display: flex; align-items: center; justify-content: center; box-shadow: 0 2px 8px rgba(29, 78, 216, 0.25);">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="20" x2="18" y2="10"></line>
                    <line x1="12" y1="20" x2="12" y2="4"></line>
                    <line x1="6" y1="20" x2="6" y2="14"></line>
                </svg>
            </div>
            <span class="brand-title-text" style="font-size: 18px; font-weight: 700; color: {text_main}; font-family: 'Inter', sans-serif; letter-spacing: -0.5px;">UX Analytics</span>
        </div>
    """, unsafe_allow_html=True)

    # ======================
    # SECTION 1: RESEARCH OBJECT (Compact Layout)
    # ======================
    st.markdown("""
        <div style="padding-top: 4px; padding-bottom: 2px;">
            <div class="section-header" style="
                font-size: 10px;
                font-weight: 700;
                color: #4f46e5;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
            ">
                Research Object
            </div>
    """, unsafe_allow_html=True)
    
    app = st.selectbox(
        "Aplikasi Analisis", 
        st.session_state.app_list, 
        label_visibility="collapsed",
        help="Pilih objek penelitian yang akan dianalisis"
    )
    
    st.markdown('<div class="manage-btn-wrapper">', unsafe_allow_html=True)
    if st.button("Manage Objects", use_container_width=True, key="btn_manage_objects", help="Kelola Objek Penelitian"):
        st.session_state["show_manage_objects"] = True
    st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div style='margin: 4px 0;'></div>", unsafe_allow_html=True)

    # ======================
    # SECTION 2: MAIN NAVIGATION (Modern Vertical List)
    # ======================
    st.markdown("""
        <div style="padding-top: 4px; padding-bottom: 2px;">
            <div class="section-header" style="
                font-size: 10px;
                font-weight: 700;
                color: #6366f1;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
            ">
                Menu Dashboard
            </div>
        </div>
    """, unsafe_allow_html=True)

    menu_options = [
        "Home", 
        "Overview", 
        "Time on Task", 
        "Error Rate", 
        "UEQ Analysis", 
        "Preferensi Responden", 
        "Settings"
    ]
    
    default_idx = 0
    if "current_page" in st.session_state:
        try:
            default_idx = menu_options.index(st.session_state.current_page)
        except ValueError:
            pass

    menu = st.radio(
        "Menu Navigasi",
        menu_options,
        index=default_idx,
        label_visibility="collapsed",
        key="sidebar_menu_radio"
    )
    st.session_state["current_page"] = menu

    st.markdown("<div style='margin: 2px 0;'></div>", unsafe_allow_html=True)

    # ======================
    # SECTION 3: PARAMETERS (Compact)
    # ======================
    st.markdown("""
        <div style="padding-top: 4px; padding-bottom: 2px;">
            <div class="section-header" style="
                font-size: 10px;
                font-weight: 700;
                color: #059669;
                text-transform: uppercase;
                letter-spacing: 1px;
                margin-bottom: 6px;
            ">
                Study Parameter
            </div>
    """, unsafe_allow_html=True)
    
    n = st.number_input(
        "Sample Size (N)", 
        min_value=1, 
        max_value=100, 
        value=25, 
        help="Jumlah responden dalam penelitian ini"
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # ======================
    # STYLING OVERRIDES
    # ======================
    is_dark = (theme == "dark")
    text_main = "#f1f5f9" if is_dark else "#0f172a"
    text_soft = "#94a3b8" if is_dark else "#64748b"

    st.markdown(f"""
    <style>
    /* Adjust sidebar padding and spacing to add breathing room while preventing scrollbars */
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {{
        padding: 16px 12px 14px 12px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        gap: 10px !important;
    }}

    /* Polished, clean Number Input styling for both Light & Dark modes */
    [data-testid="stNumberInput"] > div {{
        background-color: {'#1e293b' if is_dark else '#ffffff'} !important;
        border: 1px solid {'#334155' if is_dark else '#cbd5e1'} !important;
        border-radius: 8px !important;
        overflow: hidden !important;
        height: 36px !important;
        display: flex !important;
        align-items: center !important;
        transition: all 0.2s ease-in-out !important;
    }}
    
    [data-testid="stNumberInput"] > div:hover {{
        border-color: {'#475569' if is_dark else '#94a3b8'} !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
    }}
    
    [data-testid="stNumberInput"] > div:focus-within {{
        border-color: #6366f1 !important;
        box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25) !important;
    }}
    
    [data-testid="stNumberInput"] > div > div:first-child {{
        flex: 1 !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        background-color: transparent !important;
    }}

    [data-testid="stNumberInput"] [data-baseweb="input"],
    [data-testid="stNumberInput"] [data-baseweb="input"] > div,
    [data-testid="stNumberInput"] [data-baseweb="input"] * {{
        background-color: transparent !important;
        border: none !important;
    }}

    [data-testid="stNumberInput"] input {{
        background-color: transparent !important;
        color: {text_main} !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 12px !important;
        height: 100% !important;
        width: 100% !important;
        font-size: 14px !important;
        font-weight: 500 !important;
    }}
    
    [data-testid="stNumberInput"] > div > div:last-child {{
        background-color: transparent !important;
        border-left: 1px solid {'#334155' if is_dark else '#cbd5e1'} !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        gap: 0px !important;
        padding: 0px !important;
        margin: 0px !important;
    }}
    
    [data-testid="stNumberInput"] button {{
        background-color: transparent !important;
        color: {'#94a3b8' if is_dark else '#64748b'} !important;
        border: none !important;
        border-radius: 0px !important;
        width: 32px !important;
        height: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 16px !important;
        font-weight: 500 !important;
        transition: all 0.15s ease-in-out !important;
        cursor: pointer !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    [data-testid="stNumberInput"] button:hover {{
        background-color: {'rgba(255, 255, 255, 0.06)' if is_dark else 'rgba(0, 0, 0, 0.04)'} !important;
        color: #6366f1 !important;
    }}
    [data-testid="stNumberInput"] button:active {{
        background-color: #4338ca !important;
        transform: scale(0.95) !important;
    }}
    
    [data-testid="stNumberInput"] button:first-child {{
        border-right: 1px solid {'rgba(255, 255, 255, 0.08)' if is_dark else 'rgba(0, 0, 0, 0.08)'} !important;
    }}

    /* Styling untuk semua tombol di sidebar */
    div[data-testid="stSidebar"] button {{
        height: 32px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        border-radius: 6px !important;
        background: transparent !important;
        border: 1px solid rgba(128,128,128,0.2) !important;
        color: var(--text-color) !important;
        transition: all 0.2s ease !important;
    }}
    div[data-testid="stSidebar"] button:hover {{
        background: rgba(99, 102, 241, 0.06) !important;
        border-color: #6366f1 !important;
        color: #6366f1 !important;
    }}

    /* Aesthetic dashed outline button for Manage Objects placed below */
    div.element-container:has(.manage-btn-wrapper) + div.element-container button,
    div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer button {{
        width: 100% !important;
        height: 32px !important;
        background: transparent !important;
        border: 1px dashed rgba(148, 163, 184, 0.35) !important;
        color: {text_soft} !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        border-radius: 6px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 6px !important;
        transition: all 0.2s ease !important;
    }}
    div.element-container:has(.manage-btn-wrapper) + div.element-container button::before,
    div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer button::before {{
        content: "" !important;
        display: inline-block !important;
        width: 13px !important;
        height: 13px !important;
        background-color: currentColor !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20h9'%3E%3C/path%3E%3Cpath d='M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'%3E%3C/path%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 20h9'%3E%3C/path%3E%3Cpath d='M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z'%3E%3C/path%3E%3C/svg%3E") !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        flex-shrink: 0 !important;
        transition: all 0.2s ease !important;
    }}
    div.element-container:has(.manage-btn-wrapper) + div.element-container button p,
    div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer button p {{
        margin: 0 !important;
        padding: 0 !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        white-space: nowrap !important;
        color: inherit !important;
        line-height: 1 !important;
    }}
    div.element-container:has(.manage-btn-wrapper) + div.element-container button:hover,
    div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer button:hover {{
        border: 1px solid #3b82f6 !important;
        background: rgba(59, 130, 246, 0.05) !important;
        color: #3b82f6 !important;
    }}

    /* Style the radio sidebar navigation as menu items */
    [data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] {{
        display: none !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{
        display: flex !important;
        flex-direction: column !important;
        gap: 6px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label {{
        display: flex !important;
        align-items: center !important;
        padding: 7px 12px !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 8px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        margin: 0 !important;
        color: {text_soft} !important;
    }}
    /* Hide default radio circle icon */
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {{
        display: none !important;
    }}
    /* Style radio text */
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label p {{
        font-size: 14px !important;
        font-weight: 500 !important;
        margin: 0 !important;
        color: inherit !important;
    }}
    /* Hover and active states for radio items */
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:hover {{
        background: rgba(148, 163, 184, 0.08) !important;
        color: {text_main} !important;
        transform: translateX(4px) !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
        background: {'rgba(59, 130, 246, 0.1)' if not is_dark else '#3b82f6'} !important;
        border-color: transparent !important;
        color: {'#2563eb' if not is_dark else '#ffffff'} !important;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p {{
        font-weight: 600 !important;
    }}

    /* CSS Mask-based Outline Icons for Radio Labels */
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label::before {{
        content: "" !important;
        display: inline-block !important;
        width: 18px !important;
        height: 18px !important;
        margin-right: 12px !important;
        background-color: currentColor !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        flex-shrink: 0 !important;
    }}
    
    /* DOM index selectors (robust against input value changes) */
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(1)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="0"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Home"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/%3E%3Cpolyline points='9 22 9 12 15 12 15 22'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/%3E%3Cpolyline points='9 22 9 12 15 12 15 22'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(2)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="1"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Overview"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='7' height='9' x='3' y='3' rx='1'/%3E%3Crect width='7' height='5' x='14' y='3' rx='1'/%3E%3Crect width='7' height='9' x='14' y='12' rx='1'/%3E%3Crect width='7' height='5' x='3' y='16' rx='1'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect width='7' height='9' x='3' y='3' rx='1'/%3E%3Crect width='7' height='5' x='14' y='3' rx='1'/%3E%3Crect width='7' height='9' x='14' y='12' rx='1'/%3E%3Crect width='7' height='5' x='3' y='16' rx='1'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(3)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="2"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Time on Task"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpolyline points='12 6 12 12 16 14'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpolyline points='12 6 12 12 16 14'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(4)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="3"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Error Rate"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cline x1='15' x2='9' y1='9' y2='15'/%3E%3Cline x1='9' x2='15' y1='9' y2='15'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cline x1='15' x2='9' y1='9' y2='15'/%3E%3Cline x1='9' x2='15' y1='9' y2='15'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(5)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="4"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="UEQ Analysis"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='18' x2='18' y1='20' y2='10'/%3E%3Cline x1='12' x2='12' y1='20' y2='4'/%3E%3Cline x1='6' x2='6' y1='20' y2='14'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cline x1='18' x2='18' y1='20' y2='10'/%3E%3Cline x1='12' x2='12' y1='20' y2='4'/%3E%3Cline x1='6' x2='6' y1='20' y2='14'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(6)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="5"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Preferensi Responden"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z'/%3E%3C/svg%3E") !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:nth-of-type(7)::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="6"])::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] label:has(input[value="Settings"])::before {{
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='3'/%3E%3Cpath d='M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z'/%3E%3C/svg%3E") !important;
    }}

    /* === THEME TOGGLE SWITCH — Pill Style (matches reference) === */
    div[class*="theme_toggle_switch"] label {{
        display: inline-flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 10px !important;
        background: {'rgba(109,40,217,0.12)' if is_dark else 'rgba(237,233,254,0.9)'} !important;
        border: 1.5px solid {'rgba(139,92,246,0.25)' if is_dark else 'rgba(167,139,250,0.4)'} !important;
        padding: 6px 16px 6px 8px !important;
        height: 44px !important;
        border-radius: 999px !important;
        box-sizing: border-box !important;
        cursor: pointer !important;
        transition: background 0.2s ease, border-color 0.2s ease !important;
        vertical-align: middle !important;
        margin: 0 auto !important;
    }}
    div[class*="theme_toggle_switch"] label:hover {{
        background: {'rgba(109,40,217,0.18)' if is_dark else 'rgba(221,214,254,0.95)'} !important;
        border-color: {'rgba(139,92,246,0.4)' if is_dark else 'rgba(139,92,246,0.55)'} !important;
    }}

    /* Track: light lavender (light mode) → deep indigo (dark mode) */
    div[class*="theme_toggle_switch"] label > div:first-child,
    div[class*="theme_toggle_switch"] [data-testid="stCheckboxToToggle"] {{
        background-color: {'rgba(167,139,250,0.35)' if is_dark else '#e9d5ff'} !important;
        flex-shrink: 0 !important;
        transition: background-color 0.25s ease !important;
        width: 48px !important;
        height: 26px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        position: relative !important;
        border-radius: 999px !important;
        margin: 0 auto !important;
        left: auto !important;
        right: auto !important;
        float: none !important;
    }}
    div[class*="theme_toggle_switch"] label:has(input:checked) > div:first-child,
    div[class*="theme_toggle_switch"] label:has(input:checked) [data-testid="stCheckboxToToggle"] {{
        background-color: #6d28d9 !important;
    }}

    /* Knob: vivid indigo in light mode → white in dark mode */
    div[class*="theme_toggle_switch"] label > div:first-child > div,
    div[class*="theme_toggle_switch"] [data-testid="stCheckboxToToggle"] > div {{
        background-color: #6366f1 !important;
        box-shadow: 0 2px 6px rgba(99,102,241,0.45) !important;
        transition: transform 0.25s ease, background-color 0.2s ease !important;
        position: absolute !important;
        top: 3px !important;
        width: 20px !important;
        height: 20px !important;
        border-radius: 50% !important;
        transform: translate(3px, 0px) !important;
        left: 0 !important;
    }}
    div[class*="theme_toggle_switch"] label:has(input:checked) > div:first-child > div,
    div[class*="theme_toggle_switch"] label:has(input:checked) [data-testid="stCheckboxToToggle"] > div {{
        background-color: #ffffff !important;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25) !important;
        transform: translate(25px, 0px) !important;
    }}

    /* Icon inside knob */
    div[class*="theme_toggle_switch"] label > div:first-child > div::after,
    div[class*="theme_toggle_switch"] [data-testid="stCheckboxToToggle"] > div::after {{
        content: "" !important;
        display: block !important;
        width: 12px !important;
        height: 12px !important;
        position: absolute !important;
        top: 50% !important;
        left: 50% !important;
        transform: translate(-50%, -50%) !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        -webkit-mask-position: center !important;
        mask-position: center !important;
        /* Sun icon for light mode (unchecked) */
        background-color: #ffffff !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
    }}
    div[class*="theme_toggle_switch"] label:has(input:checked) > div:first-child > div::after,
    div[class*="theme_toggle_switch"] label:has(input:checked) [data-testid="stCheckboxToToggle"] > div::after {{
        /* Moon icon for dark mode (checked) */
        background-color: #4f46e5 !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
    }}

    /* Label text area */
    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"] {{
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
        flex-grow: 1 !important;
    }}
    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"] p {{
        margin: 0 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: {'#a78bfa' if is_dark else '#5b21b6'} !important;
        white-space: nowrap !important;
        letter-spacing: 0.1px !important;
    }}

    /* Icon left of label text — moon or sun */
    div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"]::before {{
        content: "" !important;
        display: inline-block !important;
        flex-shrink: 0 !important;
        width: 18px !important;
        height: 18px !important;
        -webkit-mask-repeat: no-repeat !important;
        mask-repeat: no-repeat !important;
        -webkit-mask-size: contain !important;
        mask-size: contain !important;
        -webkit-mask-position: center !important;
        mask-position: center !important;
        background-color: #7c3aed !important;
        /* Moon icon — default (dark mode checked) */
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z'/%3E%3C/svg%3E") !important;
    }}
    /* Light mode: sun icon (unchecked) */
    div[class*="theme_toggle_switch"] label:not(:has(input:checked)) div[data-testid="stMarkdownContainer"]::before {{
        background-color: #f59e0b !important;
        -webkit-mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
        mask-image: url("data:image/svg+xml;utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='12' cy='12' r='4'/%3E%3Cpath d='M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41'/%3E%3C/svg%3E") !important;
    }}

    /* Center the toggle widget containers at all levels in the sidebar */
    [data-testid="stSidebar"] div.element-container:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"] div.stElementContainer:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"] div.element-container:has([data-testid="stCheckbox"]),
    [data-testid="stSidebar"] div.stElementContainer:has([data-testid="stCheckbox"]),
    [data-testid="stSidebar"] div.element-container:has([data-testid="stToggle"]),
    [data-testid="stSidebar"] div.stElementContainer:has([data-testid="stToggle"]),
    [data-testid="stSidebar"] div[class*="theme_toggle_switch"],
    [data-testid="stSidebar"] [data-testid="stCheckbox"],
    [data-testid="stSidebar"] div.stCheckbox,
    [data-testid="stSidebar"] [data-testid="stToggle"],
    [data-testid="stSidebar"] div.stToggle {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        margin: 0 auto !important;
        padding: 0 !important;
    }}

    /* User card styling */
    .sidebar-user-card {{
        padding: 6px 10px !important;
        background: rgba(148, 163, 184, 0.06) !important;
        border: 1px solid rgba(148, 163, 184, 0.15) !important;
        border-radius: 10px !important;
    }}
    
    /* Custom HTML logout link button styling */
    .logout-link-btn:hover {{
        border-color: #ef4444 !important;
        background: rgba(239, 68, 68, 0.05) !important;
        color: #ef4444 !important;
    }}

    /* Hide the hidden logout button elements */
    .hidden-logout-btn,
    [data-testid="stSidebar"] div[data-testid="element-container"]:has(.hidden-logout-btn),
    [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hidden-logout-btn) {{
        display: none !important;
    }}

    [data-testid="stSidebar"] div[data-testid="element-container"]:has(.hidden-logout-btn) + div[data-testid="element-container"],
    [data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hidden-logout-btn) + div[data-testid="stElementContainer"] {{
        position: absolute !important;
        width: 0px !important;
        height: 0px !important;
        min-height: 0px !important;
        overflow: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
    }}

    /* Sibling selector for Reset Data button */
    [data-testid="stSidebar"] div.element-container:has(.reset-btn-wrapper) + div.element-container button,
    [data-testid="stSidebar"] div.stElementContainer:has(.reset-btn-wrapper) + div.stElementContainer button {{
        background: transparent !important;
        border: 1px solid rgba(148, 163, 184, 0.25) !important;
        color: {text_soft} !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.5px !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
        height: 32px !important;
    }}
    [data-testid="stSidebar"] div.element-container:has(.reset-btn-wrapper) + div.element-container button p,
    [data-testid="stSidebar"] div.stElementContainer:has(.reset-btn-wrapper) + div.stElementContainer button p {{
        margin: 0 !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        color: inherit !important;
    }}
    [data-testid="stSidebar"] div.element-container:has(.reset-btn-wrapper) + div.element-container button:hover,
    [data-testid="stSidebar"] div.stElementContainer:has(.reset-btn-wrapper) + div.stElementContainer button:hover {{
        background: rgba(239, 68, 68, 0.08) !important;
        border-color: #ef4444 !important;
        color: #ef4444 !important;
    }}

    /* ========================================================
       COLLAPSED SIDEBAR DOCK STYLES (Ultra-Sleek Vertical Dock)
       ======================================================== */
    @media (min-width: 768px) {{
        /* Keep collapsed sidebar visible as 70px dock instead of translation off-screen */
        [data-testid="stSidebar"][aria-expanded="false"] {{
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        margin-left: 0px !important;
        left: 0px !important;
        transform: translate3d(0px, 0px, 0px) !important;
        min-width: 70px !important;
        max-width: 70px !important;
        width: 70px !important;
        transition: all 0.2s ease !important;
        border-right: 1px solid rgba(128,128,128,0.15) !important;
        background-color: {'#0f172a' if is_dark else '#f8fafc'} !important;
        z-index: 100000 !important;
        position: relative !important;
    }}
    
    /* Invisible drag-to-expand handle on the right edge of the collapsed sidebar */
    [data-testid="stSidebar"][aria-expanded="false"]::after {{
        content: "" !important;
        position: absolute !important;
        top: 0 !important;
        right: 0 !important;
        width: 12px !important;
        height: 100% !important;
        cursor: ew-resize !important;
        z-index: 100002 !important;
    }}
    
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarUserContent"] {{
        display: flex !important;
        flex-direction: column !important;
        visibility: visible !important;
        opacity: 1 !important;
        padding: 8px 0px 8px 0px !important;
        height: 100% !important;
        box-sizing: border-box !important;
        align-items: center !important;
    }}
    /* Push the element containers to distribute: top group vs bottom group */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] {{
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
        align-items: center !important;
        width: 100% !important;
    }}
    /* Spacer: push toggle + user card to bottom */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] > div.element-container:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] > div.stElementContainer:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] > div.element-container:has([data-testid="stCheckbox"]),
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] > div.stElementContainer:has([data-testid="stCheckbox"]) {{
        margin-top: auto !important;
    }}
    
    /* Adjust main content layout spacing and width when sidebar is collapsed to prevent overlapping */
    [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) {{
        padding-left: 0px !important;
    }}
    [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMainViewContainer"] {{
        margin-left: 70px !important;
        padding-left: 0px !important;
        width: calc(100% - 70px) !important;
    }}
    
    /* Style the floating expand button control when collapsed */
    [data-testid="stSidebarCollapsedControl"] {{
        left: 0px !important;
        top: 0px !important;
        width: 100px !important;
        height: 100px !important;
        background: transparent !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
        border: none !important;
        z-index: 100001 !important;
    }}
    [data-testid="stSidebarCollapsedControl"] button {{
        background: transparent !important;
        border: none !important;
        color: {text_soft} !important;
        width: 100% !important;
        height: 100% !important;
        margin: 0 auto !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}

    button[kind="header"] {{
    display: flex !important;
    justify-content: center !important;
    align-items: center !important;
    }}
    [data-testid="stSidebarCollapsedControl"]:hover button {{
        color: #6366f1 !important;
    }}
    
    /* Style the collapse button inside the sidebar */
    [data-testid="stSidebar"] button[class*="CollapseButton"] {{
        top: 12px !important;
        right: 12px !important;
        background: transparent !important;
        border: 1px solid rgba(128, 128, 128, 0.15) !important;
        border-radius: 8px !important;
        color: {text_soft} !important;
        transition: all 0.2s ease !important;
    }}
    [data-testid="stSidebar"] button[class*="CollapseButton"]:hover {{
        background: rgba(148, 163, 184, 0.08) !important;
        border-color: rgba(99, 102, 241, 0.4) !important;
        color: #6366f1 !important;
    }}
    
    /* Hide full university name and show UII when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-univ-full {{
        display: none !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-univ-short {{
        display: block !important;
        text-align: center !important;
        padding-left: 0 !important;
        font-size: 11px !important;
        font-weight: 800 !important;
        letter-spacing: 0.5px !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .brand-logo-container {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 5px auto 10px auto !important;
        padding: 0 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .brand-logo-container div {{
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        min-height: 36px !important;
        border-radius: 50% !important;
        flex-shrink: 0 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .brand-logo-container div svg {{
        width: 18px !important;
        height: 18px !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .brand-title-text {{
        display: none !important;
    }}
    
    /* Hide the collapse button inside the sidebar when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] button[class*="CollapseButton"],
    [data-testid="stSidebar"][aria-expanded="false"] button[data-testid="stSidebarCollapseButton"] {{
        display: none !important;
    }}
    
    /* Hide section headers when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] .section-header {{
        display: none !important;
    }}
    
    /* Hide the selectbox widget (Research Object) and its container when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(div.stSelectbox),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(div.stSelectbox),
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.manage-btn-wrapper),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.manage-btn-wrapper),
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.manage-btn-wrapper) + div.element-container,
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer,
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.manage-btn-wrapper) + div.element-container + div.element-container,
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.manage-btn-wrapper) + div.stElementContainer + div.stElementContainer {{
        display: none !important;
        height: 0px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* Hide the parameters widget (Sample Size) when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(div.stNumberInput),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(div.stNumberInput) {{
        display: none !important;
        height: 0px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* Hide the Reset Data button and container when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.reset-btn-wrapper),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.reset-btn-wrapper),
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.reset-btn-wrapper) + div.element-container,
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.reset-btn-wrapper) + div.stElementContainer,
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.reset-btn-wrapper) + div.element-container + div.element-container,
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.reset-btn-wrapper) + div.stElementContainer + div.stElementContainer {{
        display: none !important;
        height: 0px !important;
        margin: 0 !important;
        padding: 0 !important;
    }}
    
    /* Style radio navigation items as centered squares when collapsed */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] label {{
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        width: 38px !important;
        height: 38px !important;
        border-radius: 8px !important;
        margin: 0 auto !important;
        position: relative !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] {{
        gap: 6px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        width: 100% !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {{
        position: absolute !important;
        left: 0 !important;
        top: 0 !important;
        width: 100% !important;
        height: 100% !important;
        pointer-events: none !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] label p {{
        display: block !important;
        position: absolute !important;
        left: 60px !important;
        top: 50% !important;
        transform: translateY(-50%) scale(0.9) !important;
        background-color: #3b82f6 !important;
        color: #ffffff !important;
        padding: 6px 12px !important;
        border-radius: 6px !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        white-space: nowrap !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15) !important;
        opacity: 0 !important;
        pointer-events: none !important;
        transition: all 0.15s ease-in-out !important;
        z-index: 99999 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] label:hover p {{
        opacity: 1 !important;
        transform: translateY(-50%) scale(1) !important;
        pointer-events: auto !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] label::before {{
        margin-right: 0 !important;
        width: 20px !important;
        height: 20px !important;
    }}
    
    /* Reset padding for all element containers inside the collapsed sidebar to prevent offsets */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container,
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer,
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] > div {{
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important
    }}

    /* Fix toggle position - paksa center sempurna */
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has([data-testid="stToggle"]),
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has([data-testid="stToggle"]) {{
        width: 70px !important;
        min-width: 70px !important;
        max-width: 70px !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0 !important;
        margin: 0 !important;
        overflow: visible !important;
    }}

    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] {{
        width: 48px !important;
        min-width: 0 !important;
        max-width: 48px !important;
        margin: 0 auto !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }}

    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] label {{
        width: 48px !important;
        min-width: 48px !important;
        max-width: 48px !important;
        padding: 0 !important;
        margin: 0 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }}

    /* Pastikan semua children langsung di dalam stVerticalBlock juga ter-center */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] {{
        align-items: center !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }}

    /* Force logo container center - HAPUS rule stMarkdownContainer yang lama */
    [data-testid="stSidebar"][aria-expanded="false"] .brand-logo-container {{
        margin: 0 auto !important;
        padding: 0 !important;
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }}

    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-univ-short {{
        margin: 0 auto !important;
        text-align: center !important;
        padding: 0 !important;
        width: 100% !important;
        display: block !important;
    }}

    /* Force logo container center */
    [data-testid="stSidebar"][aria-expanded="false"] .brand-logo-container,
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-univ-short {{
        margin: 0 auto !important;
        text-align: center !important;
        padding: 0 !important;
        width: 100% !important;
        display: flex !important;
        justify-content: center !important;
    }}

    /* Style collapsed toggle switch to center it and hide its label text */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(div[class*="theme_toggle_switch"]),
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has([data-testid="stToggle"]),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has([data-testid="stToggle"]),
    [data-testid="stSidebar"][aria-expanded="false"] div[class*="theme_toggle_switch"],
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"],
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle,
    [data-testid="stSidebar"][aria-expanded="false"] div[class*="theme_toggle_switch"] label,
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle label {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        height: auto !important;
        margin: 6px 0 !important;
        padding: 0 !important;
        width: 100% !important;
        pointer-events: auto !important;
        position: relative !important;
        z-index: 100003 !important;
        box-shadow: none !important;
        border: none !important;
        background: transparent !important;
    }}


    /* Toggle: sembunyikan pill wrapper, tampilkan hanya track di tengah */
    [data-testid="stSidebar"][aria-expanded="false"] div[class*="theme_toggle_switch"] label,
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] label {{
        width: 70px !important;
        height: auto !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        padding: 0 !important;
        margin: 0 auto !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        gap: 0 !important;
    }}

    /* Pastikan track toggle (48x26px) tetap terlihat dan ter-center */
    [data-testid="stSidebar"][aria-expanded="false"] div[class*="theme_toggle_switch"] label > div:first-child,
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] label > div:first-child {{
        display: flex !important;
        flex-shrink: 0 !important;
        margin: 0 auto !important;
        left: auto !important;
        right: auto !important;
        position: relative !important;
    }}

    /* Ensure the toggle label and input are always clickable */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] label,
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] input,
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle label,
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle input {{
        pointer-events: auto !important;
        cursor: pointer !important;
        position: relative !important;
        z-index: 100004 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] div[class*="theme_toggle_switch"] label div[data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle [data-testid="stWidgetLabel"],
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stToggle"] div[data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"][aria-expanded="false"] div.stToggle div[data-testid="stMarkdownContainer"] {{
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        overflow: hidden !important;
        visibility: hidden !important;
        opacity: 0 !important;
    }}
    
    /* Style collapsed user card to show only the logout icon centered */
    [data-testid="stSidebar"][aria-expanded="false"] div.element-container:has(.sidebar-user-card),
    [data-testid="stSidebar"][aria-expanded="false"] div.stElementContainer:has(.sidebar-user-card) {{
        display: flex !important;
        justify-content: center !important;
        height: auto !important;
        margin: 2px 0 4px 0 !important;
        padding: 0 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-user-card {{
        background: transparent !important;
        border: none !important;
        padding: 0 !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
        box-shadow: none !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-user-card div,
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-user-card a {{
        display: none !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-user-card button.logout-link-btn {{
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        margin: 0 auto !important;
        border: none !important;
        background: transparent !important;
        width: 44px !important;
        height: 44px !important;
        color: {text_soft} !important;
        padding: 0 !important;
    }}
    [data-testid="stSidebar"][aria-expanded="false"] .sidebar-user-card button.logout-link-btn:hover {{
        color: #ef4444 !important;
        background: transparent !important;
        border: none !important;
    }}
    
    /* Force overflow: visible on all sidebar containers to allow tooltips to show outside the dock (only on screens with enough vertical space) */
    @media (min-height: 750px) {{
        [data-testid="stSidebar"][aria-expanded="false"],
        [data-testid="stSidebar"][aria-expanded="false"] > div,
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarUserContent"],
        [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stVerticalBlock"] {{
            overflow: visible !important;
        }}
    }}
    /* Always allow visible overflow for the radio elements so that the tooltip is not clipped locally */
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"],
    [data-testid="stSidebar"][aria-expanded="false"] [data-testid="stRadio"] div[role="radiogroup"] {{
        overflow: visible !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }}
    }}
    </style>
    """, unsafe_allow_html=True)

    # ======================
    # COMPACT BOTTOM AREA
    # ======================
    is_dark = (theme == "dark")
    
    # Reset button (Full width, clean outline text)
    st.markdown('<div class="reset-btn-wrapper">', unsafe_allow_html=True)
    if st.button("Reset Data", use_container_width=True, key="btn_reset_compact", help="Reset Semua Data"):
        st.session_state["show_reset_confirm"] = True
    st.markdown('</div>', unsafe_allow_html=True)
        
    st.markdown("<div style='margin-top: 4px;'></div>", unsafe_allow_html=True)
    
    # Toggle Dark Mode (styled switch)
    toggle_label = "Dark mode" if is_dark else "Light mode"
    is_dark_toggle = st.toggle(toggle_label, value=is_dark, key="theme_toggle_switch")
    if is_dark_toggle != is_dark:
        st.session_state["app_theme"] = "dark" if is_dark_toggle else "light"
        st.query_params["theme"] = "dark" if is_dark_toggle else "light"
        st.rerun()

    st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)

    # Profile Avatar + Name + Logout Row (Unified Flexbox layout)
    first_char = current_user[0].upper() if current_user else "U"
    st.markdown(f"""<div class="sidebar-user-card" style="display: flex; align-items: center; justify-content: space-between; padding: 6px 10px;">
<div style="display: flex; align-items: center; gap: 10px; min-width: 0; flex-grow: 1;">
<a href="#" id="avatar-logout-sidebar" style="position: relative; width: 34px; height: 34px; border-radius: 50%; background: linear-gradient(135deg, #3b82f6, #6366f1); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; flex-shrink: 0; text-decoration: none;" title="Keluar Akun">
{first_char}
<span style="position: absolute; bottom: 0; right: 0; width: 8px; height: 8px; border-radius: 50%; background-color: #10B981; border: 2px solid {'#020617' if theme == 'dark' else '#ffffff'};"></span>
</a>
<div class="user-name-wrapper" style="min-width: 0; flex-grow: 1;">
<div style="font-size: 14px; font-weight: 700; color: {text_main}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
{current_user}
</div>
</div>
</div>
<button id="btn-logout-sidebar" class="logout-link-btn" title="Keluar Akun" style="display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; border-radius: 8px; border: 1px solid rgba(148, 163, 184, 0.25); color: {text_soft}; background: transparent; cursor: pointer; transition: all 0.2s; flex-shrink: 0; padding: 0;">
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
</button>
</div>""", unsafe_allow_html=True)
    
    # Bridge click/drag events for custom sidebar interactions
    import streamlit.components.v1 as components
    components.html("""
    <script>
        const parentDoc = window.parent.document;
        
        // 1. Logout bridge
        if (!window.parent.__logoutListenerAttached) {
            window.parent.__logoutListenerAttached = true;
            parentDoc.addEventListener('click', function(e) {
                const target = e.target.closest('#btn-logout-sidebar, #avatar-logout-sidebar');
                if (target) {
                    e.preventDefault();
                    e.stopPropagation();
                    let hiddenBtn = parentDoc.querySelector('[data-testid="stSidebar"] div[data-testid="stElementContainer"]:has(.hidden-logout-btn) + div[data-testid="stElementContainer"] button');
                    if (!hiddenBtn) {
                        const m = parentDoc.querySelector('.hidden-logout-btn');
                        const container = m ? m.closest('[data-testid="stElementContainer"], [data-testid="element-container"]') : null;
                        const sibling = container ? container.nextElementSibling : null;
                        hiddenBtn = sibling ? sibling.querySelector('button') : null;
                    }
                    if (!hiddenBtn) {
                        const btns = Array.from(parentDoc.querySelectorAll('button'));
                        hiddenBtn = btns.find(b => (b.textContent || b.innerText || '').toLowerCase().includes('hidden out'));
                    }
                    if (hiddenBtn) {
                        hiddenBtn.click();
                    }
                }
            }, true);
        }
        
        // 2. Clean Drag-to-expand and Drag-to-collapse bridge
        
        // Clean up debug overlay if it exists
        const oldConsole = parentDoc.getElementById('js-debug-console');
        if (oldConsole) {
            oldConsole.remove();
        }
        
        // Clean up any old listeners if they exist to allow hot-reloading new code
        if (window.parent.__sidebarMouseDownHandler) {
            parentDoc.removeEventListener('mousedown', window.parent.__sidebarMouseDownHandler);
        }
        if (window.parent.__sidebarMouseMoveHandler) {
            parentDoc.removeEventListener('mousemove', window.parent.__sidebarMouseMoveHandler);
        }
        if (window.parent.__sidebarMouseUpHandler) {
            parentDoc.removeEventListener('mouseup', window.parent.__sidebarMouseUpHandler);
        }
        if (window.parent.__sidebarTouchStartHandler) {
            parentDoc.removeEventListener('touchstart', window.parent.__sidebarTouchStartHandler);
        }
        if (window.parent.__sidebarTouchMoveHandler) {
            parentDoc.removeEventListener('touchmove', window.parent.__sidebarTouchMoveHandler);
        }
        if (window.parent.__sidebarTouchEndHandler) {
            parentDoc.removeEventListener('touchend', window.parent.__sidebarTouchEndHandler);
        }
        if (window.parent.__sidebarClickHandler) {
            parentDoc.removeEventListener('click', window.parent.__sidebarClickHandler, true);
        }
        
        // Clean up any persistent inline styles from previous drag implementations
        const sidebarEl = parentDoc.querySelector('[data-testid="stSidebar"]');
        if (sidebarEl) {
            sidebarEl.style.removeProperty('width');
            sidebarEl.style.removeProperty('min-width');
            sidebarEl.style.removeProperty('max-width');
            sidebarEl.style.removeProperty('transition');
        }
        const mainContainerEl = parentDoc.querySelector('[data-testid="stMainViewContainer"]');
        if (mainContainerEl) {
            mainContainerEl.style.removeProperty('margin-left');
            mainContainerEl.style.removeProperty('width');
            mainContainerEl.style.removeProperty('transition');
        }
        
        let isDragging = false;
        let startX = 0;
        let startY = 0;
        let draggedState = 'collapsed'; // 'collapsed' or 'expanded'
        window.parent.__sidebarDragTriggered = false;
        
        function triggerExpand() {
            isDragging = false;
            window.parent.__sidebarDragTriggered = true;
            const expandBtn = parentDoc.querySelector('[data-testid="stSidebarCollapsedControl"] button, button[data-testid="stSidebarCollapsedControl"], button[class*="CollapsedControl"]');
            if (expandBtn) {
                expandBtn.click();
            }
        }
        
        function triggerCollapse() {
            isDragging = false;
            window.parent.__sidebarDragTriggered = true;
            const collapseBtn = parentDoc.querySelector('[data-testid="stSidebar"] button[data-testid="stSidebarCollapseButton"], [data-testid="stSidebar"] button[class*="CollapseButton"]');
            if (collapseBtn) {
                collapseBtn.click();
            }
        }
        
        window.parent.__sidebarMouseDownHandler = function(e) {
            const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return;
            const isCollapsed = sidebar.getAttribute('aria-expanded') === 'false';
            
            if (sidebar.contains(e.target) || e.target === sidebar) {
                // Ignore interactive inputs, links, buttons, and toggle/checkbox labels to allow regular clicks
                if (e.target.closest('a, button, input, select, textarea, [class*="theme_toggle_switch"], [data-testid="stCheckbox"], .stCheckbox, label')) {
                    return;
                }
                isDragging = true;
                draggedState = isCollapsed ? 'collapsed' : 'expanded';
                startX = e.clientX;
                startY = e.clientY;
                window.parent.__sidebarDragTriggered = false;
            }
        };
        
        window.parent.__sidebarMouseMoveHandler = function(e) {
            if (!isDragging) return;
            if (window.parent.__sidebarDragTriggered) return;
            
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            // Ignore if movement is primarily vertical
            if (Math.abs(deltaY) > Math.abs(deltaX)) {
                return;
            }
            
            if (draggedState === 'collapsed' && deltaX > 10) {
                e.preventDefault();
                triggerExpand();
            } else if (draggedState === 'expanded' && deltaX < -40) {
                e.preventDefault();
                triggerCollapse();
            }
        };
        
        window.parent.__sidebarMouseUpHandler = function(e) {
            if (!isDragging) return;
            isDragging = false;
            
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            // If they clicked the empty space without dragging, expand the collapsed sidebar
            if (!window.parent.__sidebarDragTriggered && Math.abs(deltaX) < 5 && Math.abs(deltaY) < 5 && draggedState === 'collapsed') {
                triggerExpand();
            }
        };
        
        window.parent.__sidebarTouchStartHandler = function(e) {
            const sidebar = parentDoc.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return;
            const isCollapsed = sidebar.getAttribute('aria-expanded') === 'false';
            
            if (sidebar.contains(e.target) || e.target === sidebar) {
                if (e.target.closest('a, button, input, select, textarea, [class*="theme_toggle_switch"], [data-testid="stCheckbox"], .stCheckbox, label')) {
                    return;
                }
                isDragging = true;
                draggedState = isCollapsed ? 'collapsed' : 'expanded';
                startX = e.touches[0].clientX;
                startY = e.touches[0].clientY;
                window.parent.__sidebarDragTriggered = false;
            }
        };
        
        window.parent.__sidebarTouchMoveHandler = function(e) {
            if (!isDragging) return;
            if (window.parent.__sidebarDragTriggered) return;
            
            const deltaX = e.touches[0].clientX - startX;
            const deltaY = e.touches[0].clientY - startY;
            
            if (Math.abs(deltaY) > Math.abs(deltaX)) {
                return;
            }
            
            if (draggedState === 'collapsed' && deltaX > 10) {
                e.preventDefault();
                triggerExpand();
            } else if (draggedState === 'expanded' && deltaX < -40) {
                e.preventDefault();
                triggerCollapse();
            }
        };
        
        window.parent.__sidebarTouchEndHandler = function(e) {
            if (!isDragging) return;
            isDragging = false;
            
            if (e.changedTouches.length === 0) return;
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - startX;
            const deltaY = touchEndY - startY;
            
            if (!window.parent.__sidebarDragTriggered && Math.abs(deltaX) < 5 && Math.abs(deltaY) < 5 && draggedState === 'collapsed') {
                triggerExpand();
            }
        };
        
        window.parent.__sidebarClickHandler = function(e) {
            if (window.parent.__sidebarDragTriggered) {
                e.preventDefault();
                e.stopPropagation();
                window.parent.__sidebarDragTriggered = false;
            }
        };
        
        // Attach new listeners
        parentDoc.addEventListener('mousedown', window.parent.__sidebarMouseDownHandler);
        parentDoc.addEventListener('mousemove', window.parent.__sidebarMouseMoveHandler);
        parentDoc.addEventListener('mouseup', window.parent.__sidebarMouseUpHandler);
        parentDoc.addEventListener('touchstart', window.parent.__sidebarTouchStartHandler);
        parentDoc.addEventListener('touchmove', window.parent.__sidebarTouchMoveHandler);
        parentDoc.addEventListener('touchend', window.parent.__sidebarTouchEndHandler);
        parentDoc.addEventListener('click', window.parent.__sidebarClickHandler, true);
    </script>
    """, height=0, width=0)

    # Hidden Streamlit button for logout
    st.markdown('<div class="hidden-logout-btn" style="display:none; width:0; height:0;"></div>', unsafe_allow_html=True)
    if st.button("Hidden Out", key="btn_logout_hidden"):
        print("DEBUG: btn_logout_hidden clicked!")
        st.session_state["show_logout_confirm"] = True
        st.rerun()

@st.dialog("Konfirmasi Reset Data")
def reset_dialog():
    st.markdown("Yakin ingin menghapus **semua data** akun **{}**?".format(
        st.session_state.get("current_user", "")))
    st.caption("Tindakan ini tidak dapat dibatalkan.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Batal", use_container_width=True, key="dialog_reset_batal"):
            st.session_state["show_reset_confirm"] = False
            st.rerun()
    with col2:
        if st.button("Ya, Hapus", use_container_width=True, type="primary", key="dialog_reset_hapus"):
            tables = ["data_tot", "data_error", "data_ueq_light", "data_ueq_dark", 
                      "data_pref_pos", "data_pref_neg", "app_list"]
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            for table in tables:
                requests.delete(
                    f"{SUPABASE_URL}/rest/v1/{table}?username=eq.{st.session_state.get('current_user','')}",
                    headers=headers
                )
            st.session_state["app_list"] = []
            st.session_state["show_reset_confirm"] = False
            st.rerun()

if st.session_state.get("show_reset_confirm") == True:
    reset_dialog()

@st.dialog("Konfirmasi Logout")
def logout_dialog():
    st.markdown("Yakin ingin keluar dari akun **{}**?".format(
        st.session_state.get("current_user", "")))
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Batal", use_container_width=True, key="dialog_batal"):
            st.session_state["show_logout_confirm"] = False
            st.rerun()
    with col2:
        if st.button("Ya, Logout", use_container_width=True, type="primary", key="dialog_logout"):
            logout()

if st.session_state.get("show_logout_confirm") == True:
    logout_dialog()

@st.dialog("Kelola Objek Penelitian")
def manage_objects_dialog():
    # Notifikasi add berhasil
    if st.session_state.get("app_added"):
        st.success(f"✓ '{st.session_state.app_added}' berhasil ditambahkan!")
        st.session_state["app_added"] = None

    # Notifikasi delete berhasil
    if st.session_state.get("app_deleted"):
        st.warning(f"✓ '{st.session_state.app_deleted}' berhasil dihapus!")
        st.session_state["app_deleted"] = None

    if "input_key" not in st.session_state:
        st.session_state["input_key"] = 0

    new_app = st.text_input(
        "Nama Aplikasi Baru",
        placeholder="Contoh: Instagram, Spotify, TikTok",
        key=f"new_app_input_{st.session_state['input_key']}"
    )

    if st.button("Tambah Objek", use_container_width=True, key="btn_add_app", type="primary"):
        if new_app and new_app.strip() not in st.session_state.app_list:
            nama = new_app.strip()
            st.session_state.app_list.append(nama)
            save_app_list(st.session_state.get("current_user", "default"), st.session_state.app_list)
            st.session_state["app_added"] = nama
            st.session_state["input_key"] = st.session_state.get("input_key", 0) + 1
            st.rerun()
        elif new_app and new_app.strip() in st.session_state.app_list:
            st.error("Aplikasi sudah ada dalam daftar!")

    if st.session_state.app_list:
        st.markdown("---")
        st.markdown("""
            <div style="font-size: 12px; font-weight: 700; color: #64748B; margin-bottom: 10px;">
                HAPUS OBJEK
            </div>
        """, unsafe_allow_html=True)
        app_to_delete = st.session_state.get("app_to_delete")

        # Clean up the selectbox key in session state to prevent Streamlit option mismatch crash
        if "del_select" in st.session_state and st.session_state["del_select"] not in st.session_state.app_list:
            if st.session_state.app_list:
                st.session_state["del_select"] = st.session_state.app_list[0]
            else:
                del st.session_state["del_select"]

        # Maintain stable selectbox index when disabled
        default_index = 0
        if app_to_delete and app_to_delete in st.session_state.app_list:
            default_index = st.session_state.app_list.index(app_to_delete)

        app_delete = st.selectbox(
            "Pilih Aplikasi yang Ingin Dihapus",
            st.session_state.app_list,
            key="del_select",
            index=default_index,
            disabled=(app_to_delete is not None)
        )

        if not app_to_delete:
            if st.button("Hapus Objek", use_container_width=True, key="btn_del_app", type="secondary"):
                st.session_state["app_to_delete"] = app_delete
        else:
            st.warning(f"Apakah Anda yakin ingin menghapus objek **'{app_to_delete}'**?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Batal", use_container_width=True, key="btn_cancel_del_app", type="secondary"):
                    st.session_state["app_to_delete"] = None
            with col2:
                if st.button("Ya, Hapus", use_container_width=True, key="btn_confirm_del_app", type="primary"):
                    if app_to_delete in st.session_state.app_list:
                        st.session_state.app_list.remove(app_to_delete)
                        save_app_list(st.session_state.get("current_user", "default"), st.session_state.app_list)
                        st.session_state["app_deleted"] = app_to_delete
                        
                        # Clean up keys immediately to prevent crash
                        if "selected_app_to_delete" in st.session_state:
                            del st.session_state["selected_app_to_delete"]
                        if "del_select" in st.session_state:
                            del st.session_state["del_select"]
                            
                    st.session_state["app_to_delete"] = None
                    st.rerun()

if st.session_state.get("show_manage_objects") == True:
    st.session_state["show_manage_objects"] = False
    st.session_state["app_to_delete"] = None
    manage_objects_dialog()

# ======================
# PATH REFERENSI (tidak digunakan sebagai file lokal)
# ======================
file_tot       = ""
file_error     = ""
file_ueq_light = ""
file_ueq_dark  = ""




# ======================
# ADJUST RESPONDEN
# ======================

def adjust_dataframe(df,n):

    if len(df) < n:

        new_rows = pd.DataFrame({
        "Responden":[f"R{i+1}" for i in range(len(df),n)]
        })

        df = pd.concat([df,new_rows],ignore_index=True)

    if len(df) > n:
        df = df.iloc[:n]

    df["Responden"] = [f"R{i+1}" for i in range(len(df))]

    return df
# ======================
# LOAD DATA TOT
# ======================

columns = ["Responden","Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]

df_tot = load_data("data_tot", current_user, app)
if df_tot.empty:
    df_tot = pd.DataFrame(columns=columns)
df_tot = adjust_dataframe(df_tot, n)
for c in columns[1:]:
    if c not in df_tot:
        df_tot[c] = 0

# ======================
# LOAD DATA ERROR
# ======================

df_error = load_data("data_error", current_user, app)
if df_error.empty:
    df_error = pd.DataFrame(columns=columns)
df_error = adjust_dataframe(df_error, n)
for c in columns[1:]:
    if c not in df_error:
        df_error[c] = 0

# ======================
# LOAD DATA UEQ
# ======================

scales = {
"Daya tarik":[1,12,14,16,24,25],
"Kejelasan":[2,4,13,21],
"Efisiensi":[9,20,22,23],
"Ketepatan":[8,11,17,19],
"Stimulasi":[5,6,7,18],
"Kebaruan":[3,10,15,26]
}

items=[f"I{i}" for i in range(1,27)]

light_df = load_ueq("data_ueq_light", current_user, app, n)
dark_df  = load_ueq("data_ueq_dark",  current_user, app, n)

# ======================
# FIX DATA TYPE UEQ
# ======================

light_df = light_df[items]
dark_df = dark_df[items]

light_df = light_df.apply(pd.to_numeric, errors="coerce")
dark_df = dark_df.apply(pd.to_numeric, errors="coerce")

# ======================
# PREPROCESS UEQ (SAMA SEPERTI UEQ TOOL)
# ======================

# ====================== KONSTANTA UEQ GLOBAL ======================
UEQ_REVERSE_ITEMS = {3, 4, 5, 9, 10, 12, 17, 18, 19, 21, 23, 24, 25}

UEQ_SKALA_MAP = {
    "Daya tarik":  [1, 12, 14, 16, 24, 25],
    "Kejelasan":   [2, 4, 13, 21],
    "Efisiensi":   [9, 20, 22, 23],
    "Ketepatan":   [8, 11, 17, 19],
    "Stimulasi":   [5, 6, 7, 18],
    "Kebaruan":    [3, 10, 15, 26],
}

def ueq_transform_global(df_raw):
    """Transformasi UEQ: raw (1-7) → skala -3 s.d. +3, dengan reverse."""
    dt = df_raw.copy().apply(pd.to_numeric, errors="coerce") - 4
    for i in UEQ_REVERSE_ITEMS:
        col = f"I{i}"
        if col in dt.columns:
            dt[col] = -dt[col]
    return dt

def ueq_scale_mean_global(df_raw):
    """
    Hitung mean per skala sesuai UEQ Tools V13:
    1. Transform raw → -3..+3 dengan reverse
    2. Per responden: mean item dalam skala
    3. Scale mean = mean dari per-responden mean
    """
    dt = ueq_transform_global(df_raw)
    results = []
    for sk, items in UEQ_SKALA_MAP.items():
        cols = [f"I{i}" for i in items]
        per_person = dt[cols].mean(axis=1).dropna()
        n = len(per_person)
        mean = float(per_person.mean()) if n > 0 else 0.0
        var  = float(per_person.var(ddof=1)) if n > 1 else 0.0
        results.append({"Scale": sk, "Mean": round(mean, 4), "Variance": round(var, 4)})
    return pd.DataFrame(results)




# ======================
# FUNCTION PAIRED T TEST
# ======================

def paired_test_spss(light, dark):

    light = pd.to_numeric(light, errors="coerce")
    dark = pd.to_numeric(dark, errors="coerce")

    diff = np.array(light) - np.array(dark)

    mean = np.mean(diff)
    std = np.std(diff, ddof=1)

    n = len(diff)

    se = std / np.sqrt(n)

    t, p_two = stats.ttest_rel(light, dark)

    df = n - 1

    p_one = p_two / 2

    ci_low, ci_up = stats.t.interval(
        0.95,
        df,
        loc=mean,
        scale=se
    )

    return mean, std, se, ci_low, ci_up, t, df, p_one, p_two


if menu == "Home":

    # ======================
    # HERO SECTION (Visi Platform Masa Depan)
    # ======================
    st.markdown(f"""
    <div style="
    background: linear-gradient(135deg,#4f46e5,#6366f1);
    padding:40px;
    border-radius:20px;
    color:white;
    margin-bottom:30px;
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    ">
        <div style="font-size:28px;font-weight:800;letter-spacing:-0.5px;">
            Dashboard Analitik UX — Light Mode vs Dark Mode 
        </div>
        <div style="font-size:14px;margin-top:12px;max-width:700px;line-height:1.7;opacity:0.9;">
            Platform analitik berbasis web untuk penelitian perbandingan pengalaman pengguna (UX) antara 
            Light Mode dan Dark Mode pada aplikasi mobile. Dikembangkan menggunakan Python Streamlit 
            dan Supabase dengan metodologi Within-Subject Design — otomatis, akurat, dan interaktif.
        </div>
        <div style="margin-top:20px; display: flex; gap: 15px;">
            <div style="background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 30px; font-size: 11px; font-weight: 600;">
                Current Object: {app if app else "None"}
            </div>
            <div style="background: rgba(255,255,255,0.2); padding: 8px 15px; border-radius: 30px; font-size: 11px; font-weight: 600;">
                Sample Size: {n}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ======================
    # VISI & TUJUAN PLATFORM
    # ======================
    st.markdown(f'<div style="font-size: 22px; font-weight: 700; color:{text_main}; margin-top: 20px; margin-bottom: 20px;">Tentang Platform</div>', unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div class="card" style="padding: 28px; margin-bottom: 15px;">
            <div style="font-size:18px; font-weight:700; color:#6366f1; margin-bottom:12px;">Analisis Statistik Otomatis</div>
            <div style="font-size:15px; line-height:1.6; color:{text_main};">
                Sistem secara otomatis melakukan uji normalitas Shapiro-Wilk dan menentukan metode uji 
                yang sesuai — Paired T-Test (parametrik) atau Wilcoxon Signed Ranks Test (non-parametrik) — 
                dengan output berformat SPSS untuk Time on Task dan Error Rate.
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with c2:
        st.markdown(f"""
        <div class="card" style="padding: 28px; margin-bottom: 15px;">
            <div style="font-size:18px; font-weight:700; color:#6366f1; margin-bottom:12px;">Interactivity & Visual Insight</div>
            <div style="font-size:15px; line-height:1.6; color:{text_main};">
                Menyediakan grafik interaktif, tabel perbandingan, serta kesimpulan otomatis untuk 
                mempermudah interpretasi perbedaan UX antara Light Mode dan Dark Mode pada 
                aplikasi mobile.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ======================
    # INTEGRATED METRICS
    # ======================
    st.markdown(f'<div style="font-size: 22px; font-weight: 700; color:{text_main}; margin-top: 35px; margin-bottom: 20px;">Modul Analisis Terintegrasi</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    
    modules = [
        ("Time on Task", "Mengukur efisiensi waktu penyelesaian tugas pada light mode vs dark mode (detik)."),
        ("Error Rate", "Mengukur jumlah kesalahan yang dilakukan responden selama menyelesaikan tugas pengujian."),
        ("UEQ Standard", "Evaluasi 6 dimensi UX: Daya Tarik, Kejelasan, Efisiensi, Ketepatan, Stimulasi, Kebaruan."),
        ("Preference", "Analisis kecenderungan pilihan pengguna pada 6 aspek via Mean Preference Analysis.")
    ]

    for col, (title, desc) in zip([col1, col2, col3, col4], modules):
        col.markdown(f"""
        <div class="card" style="text-align:center; padding: 26px 20px; margin-bottom: 15px;">
            <div style="font-size:16px; font-weight:700; color:{text_main}; margin-bottom:10px;">{title}</div>
            <div style="font-size:13px; line-height:1.5; color:{text_soft};">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    # ======================
    # RESEARCH FOOTER
    # ======================
    st.markdown("<br>", unsafe_allow_html=True)
    st.info(f"""
    Panduan Penggunaan:
    1. Pilih atau tambahkan objek penelitian (aplikasi) melalui sidebar — saat ini: {app}.
    2. Input data Time on Task dan Error Rate per responden pada menu yang tersedia.
    3. Input data kuesioner UEQ (Light Mode & Dark Mode) pada menu UEQ Analysis.
    4. Input data preferensi responden pada menu Preferensi Responden.
    5. Lihat ringkasan, grafik, dan kesimpulan otomatis pada menu Overview.
    """)


# ======================
# OVERVIEW
# ======================

if menu == "Overview":

    # ======================
    # HITUNG SEMUA METRICS DULU
    # ======================
    avg_light_tot = df_tot[["Light_T1","Light_T2","Light_T3"]].mean().mean()
    avg_dark_tot  = df_tot[["Dark_T1","Dark_T2","Dark_T3"]].mean().mean()
    avg_light_err = df_error[["Light_T1","Light_T2","Light_T3"]].mean().mean()
    avg_dark_err  = df_error[["Dark_T1","Dark_T2","Dark_T3"]].mean().mean()

    light_ueq_mean = ueq_scale_mean_global(light_df)["Mean"].mean()
    dark_ueq_mean  = ueq_scale_mean_global(dark_df)["Mean"].mean()


    aspek = {
        "Readability": ["R1","R2","R3","R4"],
        "Eye Strain":  ["ES1","ES2","ES3","ES4"],
        "Usability":   ["U1","U2","U3","U4"],
        "Battery":     ["B1","B2","B3","B4"],
        "Efficiency":  ["E1","E2","E3","E4"],
        "Aesthetic":   ["ED1","ED2","ED3","ED4"],
    }

    aspek_result = []
    df_pos_ov = load_pref("data_pref_pos", current_user, app, n).fillna(0)
    df_neg_ov = load_pref("data_pref_neg", current_user, app, n).fillna(0)
    if df_pos_ov[columns_pref[1:] if 'columns_pref' in dir() else list(aspek.values())[0]].sum().sum() > 0: # type: ignore
        df_pos = df_pos_ov
        df_neg = df_neg_ov
        for a, cols in aspek.items():
            pos_val = df_pos[cols].mean().mean()
            neg_val = (8 - df_neg[cols]).mean().mean()
            if pd.isna(pos_val) or pd.isna(neg_val):
                continue
            aspek_result.append("Light Mode" if (pos_val + neg_val) / 2 < 4 else "Dark Mode")

    light_pref = aspek_result.count("Light Mode")
    dark_pref  = aspek_result.count("Dark Mode")
    best_pref  = "Light Mode" if light_pref >= dark_pref else "Dark Mode"

    # ======================
    # HEADER
    # ======================
    st.markdown(f"""
    <div style="margin-bottom:28px;">
        <div style="font-size:24px;font-weight:700;color:{text_main};letter-spacing:-0.3px;">
            Research Overview
        </div>
        <div style="font-size:13px;color:{text_soft};margin-top:3px;">
            {app} &nbsp;·&nbsp; {n} responden &nbsp;·&nbsp; Within-Subject Design
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ======================
    # KPI CARDS — 4 METRIK + 1 KESIMPULAN
    # ======================
    def _winner_badge(wins):
        if wins:
            return '<span class="pref-badge" style="margin-left:5px;vertical-align:middle;background:rgba(99,102,241,0.2);color:#6366F1 !important;border:1px solid rgba(99,102,241,0.3);">BEST</span>'
        return ""

    def _kpi(title, l_val, d_val, unit, lower_is_better=False):
        l_wins = (l_val < d_val) if lower_is_better else (l_val > d_val)
        d_wins = not l_wins
        return f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div style="display:flex;flex-direction:column;gap:10px;">
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div class="kpi-label">
                        <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                            background:#6366F1;flex-shrink:0;"></span>Light
                    </div>
                    <div class="kpi-value-light">
                        {round(l_val, 2)}{unit}{_winner_badge(l_wins)}
                    </div>
                </div>
                <div class="kpi-divider"></div>
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <div class="kpi-label">
                        <span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                            background:#a78bfa;flex-shrink:0;"></span>Dark
                    </div>
                    <div class="kpi-value-dark">
                        {round(d_val, 2)}{unit}{_winner_badge(d_wins)}
                    </div>
                </div>
            </div>
        </div>"""

    col_a, col_b, col_c, col_d, col_e = st.columns(5)

    with col_a:
        st.markdown(_kpi("UEQ Score", light_ueq_mean, dark_ueq_mean, ""), unsafe_allow_html=True)
    with col_b:
        st.markdown(_kpi("Time on Task", avg_light_tot, avg_dark_tot, "s", lower_is_better=True), unsafe_allow_html=True)
    with col_c:
        st.markdown(_kpi("Error Rate", avg_light_err, avg_dark_err, " ksl", lower_is_better=True), unsafe_allow_html=True)
    with col_d:
        pref_color = "#6366F1" if best_pref == "Light Mode" else "#a78bfa"
        pref_bg    = "rgba(99,102,241,0.15)" if best_pref == "Light Mode" else "rgba(167,139,250,0.15)"
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">Best Preference</div>
            <div class="pref-value-text" style="color:{pref_color} !important;">
                {best_pref}
            </div>
            <div class="pref-badge" style="background:{pref_bg}; color:{pref_color} !important;">
                {light_pref} Light &nbsp;·&nbsp; {dark_pref} Dark
            </div>
        </div>
        """, unsafe_allow_html=True)
    with col_e:
        st.markdown(f"""
        <div class="kpi-card" style="background: linear-gradient(135deg, #6366F1, #4f46e5) !important; color: white !important;">
            <div style="font-size:10px;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:16px;opacity:0.7;color: white !important;">Objek Studi</div>
            <div style="font-size:20px;font-weight:700;margin-bottom:6px;color: white !important;">{app}</div>
            <div style="font-size:11px;opacity:0.7;color: white !important;">N = {n} responden</div>
            <div style="font-size:11px;opacity:0.7;color: white !important;">3 tugas per mode</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ======================
    # CHART ROW — ToT, Error, UEQ side by side (Plotly, bersih)
    # ======================
    st.markdown(f"""
    <div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;
        letter-spacing:0.08em;margin-bottom:12px;">Perbandingan Metrik</div>
    """, unsafe_allow_html=True)

    col_g1, col_g2, col_g3 = st.columns(3)

    def _bar_chart(title, l_val, d_val, unit):
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Light", "Dark"],
            y=[l_val, d_val],
            marker_color=["#6366F1", "#a78bfa"],
            text=[f"{round(l_val,1)}{unit}", f"{round(d_val,1)}{unit}"],
            textposition="outside",
            textfont=dict(size=12, color=["#6366F1", "#a78bfa"]),
            width=0.45,
        ))
        fig.update_layout(
            title=dict(text=title, font=dict(size=12, color="#94A3B8"), x=0, xanchor="left"),
            yaxis=dict(showgrid=True, gridcolor="rgba(128, 128, 128, 0.15)", zeroline=False,
                       tickfont=dict(size=10, color="#94A3B8"), showline=False),
            xaxis=dict(tickfont=dict(size=11, color="#94A3B8"), showline=False),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=36, b=16, l=8, r=8),
            height=220,
            showlegend=False,
        )
        return fig

    with col_g1:
        st.plotly_chart(_bar_chart("Time on Task (detik)", avg_light_tot, avg_dark_tot, "s"),
                        use_container_width=True, config={"displayModeBar": False})
    with col_g2:
        st.plotly_chart(_bar_chart("Error Rate (kesalahan)", avg_light_err, avg_dark_err, ""),
                        use_container_width=True, config={"displayModeBar": False})
    with col_g3:
        st.plotly_chart(_bar_chart("UEQ Score", light_ueq_mean, dark_ueq_mean, ""),
                        use_container_width=True, config={"displayModeBar": False})

    st.markdown("<div style='margin-top:24px;'></div>", unsafe_allow_html=True)

    # ======================
    # PREFERENSI DONUT — POSITIF & NEGATIF
    # ======================
    pos_percent = {a: 0.0 for a in aspek.keys()}
    neg_percent = {a: 0.0 for a in aspek.keys()}

    df_pos_raw = load_pref("data_pref_pos", current_user, app, n).fillna(0)
    raw_p = {}
    for a, cols in aspek.items():
        ec = [c for c in cols if c in df_pos_raw.columns]
        if ec:
            v = df_pos_raw[ec].apply(pd.to_numeric, errors="coerce").mean().mean()
            raw_p[a] = v if not pd.isna(v) and v > 0 else 0
    tot = sum(raw_p.values())
    if tot > 0:
        pos_percent = {k: (v / tot) * 100 for k, v in raw_p.items()}

    df_neg_raw = load_pref("data_pref_neg", current_user, app, n).fillna(0)
    raw_n = {}
    for a, cols in aspek.items():
        ec = [c for c in cols if c in df_neg_raw.columns]
        if ec:
            v = df_neg_raw[ec].apply(pd.to_numeric, errors="coerce").mean().mean()
            raw_n[a] = v if not pd.isna(v) and v > 0 else 0
    tot = sum(raw_n.values())
    if tot > 0:
        neg_percent = {k: (v / tot) * 100 for k, v in raw_n.items()}

    st.markdown(f"""
    <div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;
        letter-spacing:0.08em;margin-bottom:12px;">Distribusi Preferensi</div>
    """, unsafe_allow_html=True)

    col_p1, col_p2 = st.columns(2)

    def _donut_section(col, label, percent_dict, palette):
        with col:
            with st.container(border=True):
                st.markdown(f"""
                <div style="font-size:13px;font-weight:600;color:{text_main};
                    margin-bottom:12px;">{label}</div>
                """, unsafe_allow_html=True)
                if any(v > 0 for v in percent_dict.values()):
                    c_left, c_right = st.columns([1, 1.3])
                    with c_left:
                        fig = go.Figure(data=[go.Pie(
                            labels=list(percent_dict.keys()),
                            values=list(percent_dict.values()),
                            hole=0.62,
                            marker=dict(colors=palette, line=dict(color="#FFFFFF", width=2)),
                            textinfo="none",
                            showlegend=False,
                            hoverinfo="label+percent",
                        )])
                        fig.update_layout(
                            margin=dict(t=0, b=0, l=0, r=0),
                            height=160,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                        )
                        st.plotly_chart(fig, use_container_width=True,
                                        config={"displayModeBar": False})
                    with c_right:
                        legend = ""
                        for i, (name, val) in enumerate(percent_dict.items()):
                            c = palette[i % len(palette)]
                            legend += f"""
                            <div style="display:flex;justify-content:space-between;
                                align-items:center;margin-bottom:7px;">
                                <div style="display:flex;align-items:center;gap:7px;">
                                    <div style="width:7px;height:7px;border-radius:50%;
                                        background:{c};flex-shrink:0;"></div>
                                    <span style="font-size:11px;color:{text_soft};">{name}</span>
                                </div>
                                <span style="font-size:11px;font-weight:600;color:{text_main};">
                                    {round(val,1)}%
                                </span>
                            </div>"""
                        st.markdown(legend, unsafe_allow_html=True)
                else:
                    st.caption("Data belum tersedia.")

    _donut_section(col_p1, "Preferensi Positif",
                   pos_percent,
                   ["#4338CA","#4F46E5","#6366F1","#818CF8","#A5B4FC","#C7D2FE"])
    _donut_section(col_p2, "Preferensi Negatif",
                   neg_percent,
                   ["#1E3A8A","#1E40AF","#1D4ED8","#2563EB","#3B82F6","#60A5FA"])

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ======================
    # STATISTICAL SIGNIFICANCE
    # ======================
    st.markdown(f"""
    <div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;
        letter-spacing:0.08em;margin-bottom:12px;">Signifikansi Statistik</div>
    """, unsafe_allow_html=True)

    tot_empty = df_tot[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    err_empty = df_error[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    ueq_empty = light_df.replace(4, np.nan).dropna(how="all").empty and dark_df.replace(4, np.nan).dropna(how="all").empty

    p_tot = np.nan
    if not tot_empty:
        try:
            from scipy.stats import wilcoxon as _wilcoxon
            _l = df_tot[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
            _d = df_tot[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
            _res = _wilcoxon(_l, _d, zero_method='wilcox', correction=False,
                             alternative='two-sided', method='approx')
            p_tot = float(_res.pvalue)
        except Exception:
            _, p_tot = stats.ttest_rel(
                df_tot[["Light_T1","Light_T2","Light_T3"]].mean(axis=1),
                df_tot[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
            )

    p_err = np.nan
    if not err_empty:
        try:
            from scipy.stats import wilcoxon as _wilcoxon
            _l = df_error[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
            _d = df_error[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
            _res = _wilcoxon(_l, _d, zero_method='wilcox', correction=False,
                             alternative='two-sided', method='approx')
            p_err = float(_res.pvalue)
        except Exception:
            _, p_err = stats.ttest_rel(
                df_error[["Light_T1","Light_T2","Light_T3"]].mean(axis=1),
                df_error[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
            )

    p_ueq = np.nan
    if not ueq_empty:
        _, p_ueq = stats.ttest_rel(
            ueq_transform_global(light_df).mean(axis=1),   # ✅
            ueq_transform_global(dark_df).mean(axis=1)
        )

    pref_diff = []
    _df_pos_sig = load_pref("data_pref_pos", current_user, app, n).fillna(0)
    _df_neg_sig = load_pref("data_pref_neg", current_user, app, n).fillna(0)
    cols_all = [c for cols in aspek.values() for c in cols]
    ep = [c for c in cols_all if c in _df_pos_sig.columns]
    en = [c for c in cols_all if c in _df_neg_sig.columns]
    if ep and en:
        pv = _df_pos_sig[ep].apply(pd.to_numeric, errors="coerce").mean(axis=1)
        nv = (8 - _df_neg_sig[en].apply(pd.to_numeric, errors="coerce")).mean(axis=1)
        pref_diff = (pv - nv).dropna().tolist()

    p_pref = np.nan
    if len(pref_diff) > 1:
        _, p_pref = stats.ttest_1samp(pref_diff, 0)

    grand_p = np.nanmean([p_tot, p_err, p_ueq, p_pref])
    p_val_final = grand_p

    is_sig       = not pd.isna(grand_p) and grand_p < 0.05
    grand_color  = "#166534" if is_sig else "#92400E"
    grand_bg     = "#F0FDF4" if is_sig else "#FFFBEB"
    grand_border = "#BBF7D0" if is_sig else "#FDE68A"
    grand_label  = "Signifikan" if is_sig else "Tidak Signifikan"

    stats_rows = [
        ("Time on Task",        "Wilcoxon / Paired T-Test",   p_tot),
        ("Error Rate",          "Wilcoxon / Paired T-Test",   p_err),
        ("UEQ Analysis",        "Paired T-Test",   p_ueq),
        ("Preferensi Subjektif","Mean Preference Analysis", p_pref),
    ]

    col_grand, col_detail = st.columns([1, 2.6])

    with col_grand:
        p_display = f"{round(grand_p, 4)}" if not pd.isna(grand_p) else "—"
        st.markdown(f"""
        <div style="background:{grand_bg};border:1px solid {grand_border};border-radius:14px;
            padding:28px 20px;text-align:center;height:100%;display:flex;flex-direction:column;
            justify-content:center;align-items:center;min-height:200px;margin-bottom:20px;">
            <div style="font-size:10px;font-weight:700;color:{grand_color};text-transform:uppercase;
                letter-spacing:0.08em;margin-bottom:10px;">Overall p-value</div>
            <div style="font-size:38px;font-weight:700;color:{grand_color};line-height:1;">
                {p_display}
            </div>
            <div style="margin-top:14px;display:inline-block;font-size:11px;font-weight:600;
                background:{grand_color};color:white;padding:5px 16px;border-radius:20px;">
                {grand_label}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_detail:
        rows_html = ""
        for label, method, pv in stats_rows:
            if pd.isna(pv):
                sig_color = "#94A3B8"
                p_text    = "&#8212;"
                sig_text  = "Belum ada data"
                dot_bg    = "#E2E8F0"
            elif pv < 0.05:
                sig_color = "#166534"
                p_text    = str(round(pv, 4))
                sig_text  = "Signifikan"
                dot_bg    = "#86EFAC"
            else:
                sig_color = "#94A3B8"
                p_text    = str(round(pv, 4))
                sig_text  = "Tidak Signifikan"
                dot_bg    = "#E2E8F0"

            rows_html += (
                '<div style="display:flex;justify-content:space-between;align-items:center;'
                'padding:11px 0;border-bottom:1px solid #F8FAFC;">'
                  '<div style="display:flex;align-items:center;gap:10px;">'
                    '<div style="width:7px;height:7px;border-radius:50%;'
                    'background:' + dot_bg + ';flex-shrink:0;"></div>'
                    '<div>'
                      f'<div style="font-size:13px;font-weight:600;color:{text_main};">' + label + '</div>'
                      '<div style="font-size:10px;color:#6366F1;margin-top:1px;">' + method + '</div>'
                     '</div>'
                  '</div>'
                  '<div style="text-align:right;">'
                    '<div style="font-size:14px;font-weight:700;color:' + sig_color + ';">' + 'p = ' + p_text + '</div>'
                    '<div style="font-size:9px;color:' + sig_color + ';font-weight:600;'
                    'text-transform:uppercase;margin-top:1px;">' + sig_text + '</div>'
                  '</div>'
                '</div>'
            )

        card_html = (
            f'<div style="border:1px solid rgba(128,128,128,0.2);border-radius:14px;padding:20px 22px;height:100%;margin-bottom:20px;">'
              f'<div style="font-size:12px;font-weight:600;color:{text_main};margin-bottom:12px;">'
                'Rincian Metode Analisis'
              '</div>'
            + rows_html +
            '</div>'
        )
        st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)

    # ======================
    # KESIMPULAN AKHIR
    # ======================
    data_tot_empty = df_tot[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    data_err_empty = df_error[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].sum().sum() == 0
    data_ueq_empty = light_df.sum().sum() == 0 and dark_df.sum().sum() == 0
    _pref_pos_check = load_pref("data_pref_pos", current_user, app, n).fillna(0)
    _cols_check = [c for c in _pref_pos_check.columns if c != "Responden"]
    _pref_neg_check = load_pref("data_pref_neg", current_user, app, n).fillna(0)
    _cols_neg_check = [c for c in _pref_neg_check.columns if c != "Responden"]
    pref_empty = (_pref_pos_check[_cols_check].sum().sum() == 0) or (_pref_neg_check[_cols_neg_check].sum().sum() == 0)

    if data_tot_empty or data_err_empty or data_ueq_empty or pref_empty:
        st.info("Silakan input semua data penelitian terlebih dahulu untuk menampilkan kesimpulan.")
    else:
        result_light   = ueq_scale_mean_global(light_df)
        result_dark    = ueq_scale_mean_global(dark_df)
        ueq_scale_m    = {result_light.loc[i,"Scale"]: {"l": result_light.loc[i,"Mean"], "d": result_dark.loc[i,"Mean"]} for i in range(len(result_light))}
        best_ueq_scale = max(ueq_scale_m, key=lambda s: max(ueq_scale_m[s]["l"], ueq_scale_m[s]["d"]))

        win_ueq = "Light" if light_ueq_mean > dark_ueq_mean else "Dark"
        win_tot = "Light" if avg_light_tot < avg_dark_tot else "Dark"
        win_err = "Light" if avg_light_err < avg_dark_err else "Dark"

        pref_scores = {}
        df_pos_r = load_pref("data_pref_pos", current_user, app, n).fillna(0)
        df_neg_r = load_pref("data_pref_neg", current_user, app, n).fillna(0)
        for a, cols in aspek.items():
            pv2 = df_pos_r[cols].apply(pd.to_numeric, errors="coerce").mean().mean()
            nv2 = (8 - df_neg_r[cols].apply(pd.to_numeric, errors="coerce")).mean().mean()
            pref_scores[a] = (pv2 + nv2) / 2

        best_pref_aspect  = max(pref_scores, key=pref_scores.get) if pref_scores else "—"
        worst_pref_aspect = min(pref_scores, key=pref_scores.get) if pref_scores else "—"

        aspect_scores = {}
        if pref_scores:
            for a, score in pref_scores.items():
                aspect_scores[a] = {"score": score, "mode": "LIGHT" if score < 4 else "DARK"}
        best_aspect       = max(aspect_scores, key=lambda x: aspect_scores[x]["score"]) if aspect_scores else "—"
        best_aspect_mode  = aspect_scores[best_aspect]["mode"] if aspect_scores else "—"
        worst_aspect      = min(aspect_scores, key=lambda x: aspect_scores[x]["score"]) if aspect_scores else "—"
        worst_aspect_mode = aspect_scores[worst_aspect]["mode"] if aspect_scores else "—"

        sig_label  = "Signifikan" if p_val_final < 0.05 else "Tidak Signifikan"
        sig_color  = "#22c55e" if p_val_final < 0.05 else "#f59e0b"
        sig_bg     = "rgba(34,197,94,0.1)" if p_val_final < 0.05 else "rgba(245,158,11,0.1)"
        rec_color  = "#6366f1" if best_pref == "Light Mode" else "#a78bfa"
        rec_bg     = "rgba(99,102,241,0.1)" if best_pref == "Light Mode" else "rgba(167,139,250,0.1)"
        rec_border = "rgba(99,102,241,0.3)" if best_pref == "Light Mode" else "rgba(167,139,250,0.3)"

        # ── build grid cards ──────────────────────────────────────────
        def _grid_card(subtitle, body):
            return (
                f'<div style="background:var(--secondary-background-color);border:1px solid rgba(128,128,128,0.2);padding:14px 16px;border-radius:10px;">'
                  f'<div style="font-size:11px;font-weight:600;color:{text_soft};margin-bottom:4px;">'
                    + subtitle +
                  '</div>'
                  f'<div style="font-size:13px;color:{text_main};line-height:1.5;">'
                    + body +
                  '</div>'
                '</div>'
            )

        grid_html = (
            _grid_card("User Experience (UEQ)",
                       "Mode <strong>" + win_ueq + "</strong> lebih unggul pada UEQ, "
                       "skor tertinggi pada skala <strong>" + best_ueq_scale + "</strong>.") +
            _grid_card("Time on Task",
                       "Responden lebih cepat menggunakan mode <strong>" + win_tot + "</strong>.") +
            _grid_card("Error Rate",
                       "Tingkat kesalahan lebih rendah pada mode <strong>" + win_err + "</strong>.") +
            _grid_card("Preferensi Positif",
                       "Skor tertinggi pada aspek <strong>" + best_pref_aspect + "</strong> "
                       "(mode <strong>" + best_aspect_mode + "</strong>).") +
            _grid_card("Preferensi Negatif",
                       "Skor tertinggi pada aspek <strong>" + worst_aspect + "</strong> "
                       "(mode <strong>" + worst_aspect_mode + "</strong>).")
        )

        kesimpulan_html = (
            '<div style="font-size:11px;font-weight:700;color:#94A3B8;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:12px;">Kesimpulan Akhir Penelitian</div>'

            '<div style="border:1px solid #E2E8F0;border-radius:16px;padding:28px;">'

              '<div style="background:' + rec_bg + ';border:1px solid ' + rec_border + ';border-radius:12px;'
              'padding:20px;text-align:center;margin-bottom:24px;">'
                '<div style="font-size:10px;font-weight:700;color:' + rec_color + ';text-transform:uppercase;'
                'letter-spacing:0.08em;margin-bottom:6px;">Rekomendasi Antarmuka</div>'
                '<div style="font-size:28px;font-weight:700;color:' + rec_color + ';">' + best_pref + '</div>'
              '</div>'

              '<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:20px;">'
                + grid_html +
              '</div>'

              '<div style="font-size:13px;color:#475569;line-height:1.7;text-align:center;'
              'padding-top:16px;border-top:1px solid #F1F5F9;">'
                'Secara keseluruhan, <strong>' + best_pref + '</strong> memberikan pengalaman pengguna '
                'yang lebih optimal berdasarkan evaluasi UEQ, Time on Task, Error Rate, '
                'dan preferensi responden pada enam aspek.'
              '</div>'

              '<div style="text-align:center;margin-top:16px;">'
                '<span style="display:inline-block;font-size:11px;font-weight:600;'
                'background:' + sig_bg + ';color:' + sig_color + ';'
                'padding:5px 16px;border-radius:20px;">'
                  + sig_label + ' (p = ' + str(round(grand_p, 4)) + ')'
                '</span>'
              '</div>'

            '</div>'
        )

        st.markdown(kesimpulan_html, unsafe_allow_html=True)
    

# ======================
# TIME ON TASK (UI BARU - SAMA SEPERTI UEQ)
# ======================

if menu == "Time on Task":

    st.markdown(f"""
    <div style="font-size:28px;font-weight:700;color:{text_main};margin-bottom:10px;">
    Time on Task Analysis
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="font-size:14px;color:{text_soft};">
    Uji normalitas Shapiro-Wilk otomatis · Rekomendasi metode: Paired T-Test atau Wilcoxon Signed Ranks Test
    </div>
    """, unsafe_allow_html=True)

    # ======================
    # DATASET MANAGER
    # ======================
    with st.expander("Dataset Manager", expanded=False):
        dataset_manager(
            df_tot,
            columns,
            file_tot,
            "Dataset Time on Task",
            f"time_on_task_{app}"
        )

    # ======================
    # DATA EDITOR
    # ======================
    st.markdown("### Dataset Input")
    
    df_edit = st.data_editor(
        df_tot, 
        key="tot_editor", 
        use_container_width=True,
        column_config={
            "Responden": st.column_config.TextColumn("Responden"),
            "Light_T1": st.column_config.NumberColumn("Light T1 (detik)", min_value=0, step=0.1),
            "Light_T2": st.column_config.NumberColumn("Light T2 (detik)", min_value=0, step=0.1),
            "Light_T3": st.column_config.NumberColumn("Light T3 (detik)", min_value=0, step=0.1),
            "Dark_T1": st.column_config.NumberColumn("Dark T1 (detik)", min_value=0, step=0.1),
            "Dark_T2": st.column_config.NumberColumn("Dark T2 (detik)", min_value=0, step=0.1),
            "Dark_T3": st.column_config.NumberColumn("Dark T3 (detik)", min_value=0, step=0.1),
        }
    )
    
    # Save button
    if st.button("Simpan Data Time on Task", type="primary", use_container_width=True):
        save_data("data_tot", current_user, app, df_edit)
        st.session_state["saved_tot"] = True
        st.rerun()

    if st.session_state.get("saved_tot"):
        st.success("Data Time on Task berhasil disimpan!")
        st.session_state["saved_tot"] = False

    # --- HAPUS DATA ---
    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    render_delete_button(
        file_path=file_tot,
        label="Time on Task",
        columns=columns[1:],  # skip kolom Responden
        default_value=0,
        key_suffix="tot"
    )

    # ======================
    # ANALYSIS BUTTON (WILCOXON)
    # ======================
    # ... bagian kode sebelumnya ...
    data_kosong = df_edit[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].replace(0, pd.NA).dropna(how="all").empty

    if st.button("ANALISIS DATA", type="secondary", key="analyze_tot"):
        task_cols = ["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]
        df_numeric = df_edit[task_cols].apply(pd.to_numeric, errors="coerce")
        baris_ada = df_numeric.replace(0, np.nan).dropna(how="all")
        
        if baris_ada.empty:
            st.warning("Data masih kosong. Silakan isi data terlebih dahulu.")
            st.stop()
        
        # Cek baris yang tidak lengkap (ada kolom kosong/0 di baris yang sudah diisi)
        baris_tidak_lengkap = baris_ada.isnull().any(axis=1) | (baris_ada == 0).any(axis=1)
        jumlah_tidak_lengkap = baris_tidak_lengkap.sum()
        
        if jumlah_tidak_lengkap > 0:
            idx_tidak_lengkap = baris_ada[baris_tidak_lengkap].index.tolist()
            responden_list = [f"R{i+1}" for i in idx_tidak_lengkap]
            st.warning(
                f"Data belum lengkap! {jumlah_tidak_lengkap} responden belum mengisi semua task: "
                f"**{', '.join(responden_list)}**. "
                f"Setiap responden harus mengisi Light T1, T2, T3 dan Dark T1, T2, T3."
            )
            st.stop()
 
        st.markdown("---")
 
        # Hitung mean per user (dipakai berulang)
        light_per_user = df_edit[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
        dark_per_user  = df_edit[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
 
        # ============================================================
        # 1. UJI NORMALITAS — Shapiro-Wilk pada SELISIH (Dark − Light)
        # ============================================================
        st.markdown("### Uji Normalitas Selisih (Dark − Light)")
 
        norm_results = []
        for i in range(1, 4):
            r = shapiro_and_ks(
                df_edit[f"Light_T{i}"], df_edit[f"Dark_T{i}"],
                label=f"Dark_T{i} − Light_T{i}"
            )
            norm_results.append(r)
 
        r_overall = shapiro_and_ks(
            light_per_user, dark_per_user,
            label="Dark (mean) − Light (mean)"
        )
        norm_results.append(r_overall)
 
        render_normality_table(norm_results)
 
        # Tampilkan rekomendasi (tidak memaksa, hanya saran)
        rec = render_normality_recommendation(norm_results)
 
        # ============================================================
        # 2. PILIHAN METODE MANUAL
        # ============================================================
        st.markdown("#### Pilih Metode Uji Statistik")
        default_idx = 0 if rec == "t-test" else 1
        method_choice = st.radio(
            "Metode yang akan digunakan:",
            ["Paired Samples T-Test (Parametrik)",
             "Wilcoxon Signed Ranks Test (Non-Parametrik)"],
            index=default_idx,
            horizontal=True,
            key="method_choice_tot"
        )
        use_ttest = method_choice.startswith("Paired")
 
        # ============================================================
        # 3. OVERALL METRICS
        # ============================================================
        st.markdown("---")
        st.markdown("### Overall Metrics")
 
        avg_light_err = light_per_user.mean()
        avg_dark_err  = dark_per_user.mean()
 
        task_avgs = pd.DataFrame({
            "Task":       ["T1", "T2", "T3"],
            "Light Mode": [df_edit[f"Light_T{i}"].mean() for i in range(1, 4)],
            "Dark Mode":  [df_edit[f"Dark_T{i}"].mean()  for i in range(1, 4)],
        })
 
        col1, col2, col3 = st.columns(3)
        with col1:
            better_mode = "Light" if avg_light_err < avg_dark_err else "Dark"
            dc = "normal" if avg_light_err < avg_dark_err else "inverse"
            st.metric("Lowest Time on Task", better_mode,
                      f"{abs(avg_light_err - avg_dark_err):.1f}s", delta_color=dc)
        with col2:
            st.metric("Light Mode Avg", f"{avg_light_err:.1f}s")
        with col3:
            st.metric("Dark Mode Avg", f"{avg_dark_err:.1f}s")
 
        st.markdown("### Task Results")
        st.dataframe(task_avgs.round(2), use_container_width=True)
 
        # ============================================================
        # 4. UJI STATISTIK SESUAI PILIHAN
        # ============================================================
        p_values      = []
        z_or_t_values = []
 
        if use_ttest:
            st.markdown("### Paired Samples T-Test — Per Task")
            pairs_per_task = []
            for i in range(1, 4):
                light = pd.to_numeric(df_edit[f"Light_T{i}"], errors="coerce")
                dark  = pd.to_numeric(df_edit[f"Dark_T{i}"],  errors="coerce")
                item  = compute_paired_ttest_pair(light, dark, f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item)
                p_values.append(item["p_two"])
                z_or_t_values.append(item["t"])
            render_spss_paired_ttest(pairs_per_task)
 
            st.markdown("### Overall Paired T-Test (Mean per User)")
            overall_pair = compute_paired_ttest_pair(
                light_per_user, dark_per_user, "Light (mean)", "Dark (mean)"
            )
            render_spss_paired_ttest([overall_pair])
            overall_stat  = overall_pair["t"]
            overall_p     = overall_pair["p_two"]
            stat_label    = "t"
 
        else:
            st.markdown("### Wilcoxon Signed Ranks Test — Per Task")
            pairs_per_task = []
            for i in range(1, 4):
                light = pd.to_numeric(df_edit[f"Light_T{i}"], errors="coerce")
                dark  = pd.to_numeric(df_edit[f"Dark_T{i}"],  errors="coerce")
                item  = compute_wilcoxon_pair(light, dark, f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item)
                p_values.append(item["p_val"])
                z_or_t_values.append(item["z_val"])
            render_spss_wilcoxon(pairs_per_task)
 
            st.markdown("### Overall Wilcoxon Test (Mean per User)")
            overall_item = compute_wilcoxon_pair(
                light_per_user, dark_per_user, "Light (mean)", "Dark (mean)"
            )
            render_spss_wilcoxon([overall_item])
            overall_stat  = overall_item["z_val"]
            overall_p     = overall_item["p_val"]
            stat_label    = "Z"
 
        # ============================================================
        # 5. VISUALIZATION
        # ============================================================
        st.markdown("### Visual Comparison")
 
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle("Time on Task Analysis", fontsize=16, fontweight='bold')
 
        x, width = np.arange(3), 0.35
        ax1.bar(x - width/2, task_avgs["Light Mode"], width, label='Light', color="#6366f1", alpha=0.8)
        ax1.bar(x + width/2, task_avgs["Dark Mode"],  width, label='Dark',  color="#1e293b", alpha=0.8)
        ax1.set_title("Per Task Comparison")
        ax1.set_xticks(x); ax1.set_xticklabels(["T1","T2","T3"])
        ax1.set_ylabel("Time (detik)"); ax1.legend(); ax1.grid(True, alpha=0.3)
 
        ax2.hist(light_per_user.dropna(), bins=15, alpha=0.7, color="#6366f1", label='Light', density=True)
        ax2.hist(dark_per_user.dropna(),  bins=15, alpha=0.7, color="#1e293b", label='Dark',  density=True)
        ax2.set_title("Distribution (Mean per User)")
        ax2.set_xlabel("Time (detik)"); ax2.legend(); ax2.grid(True, alpha=0.3)
 
        tasks = [f"T{i}" for i in range(1, 4)]
        colors_sig = ["#10b981" if p < 0.05 else "#ef4444" for p in p_values]
        ax3.bar(tasks, z_or_t_values, color=colors_sig, alpha=0.8)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title("Paired T-Test t-values" if use_ttest else "Wilcoxon Z-Scores")
        ax3.grid(True, alpha=0.3)
 
        ax4.bar(tasks, p_values, color=colors_sig, alpha=0.8)
        ax4.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='α=0.05')
        ax4.set_title("P-Values")
        ax4.set_ylim(0, max(0.3, max(p_values) * 1.1))
        ax4.legend(); ax4.grid(True, alpha=0.3)
 
        plt.tight_layout()
        st.pyplot(fig)
 
        # ============================================================
        # 6. BENCHMARK CARDS
        # ============================================================
        st.markdown("### Benchmark Results")
        col_b1, col_b2 = st.columns(2)
        for i, (avg_time, label, color) in enumerate([
            (avg_light_err, "Light Mode", "#6366f1"),
            (avg_dark_err,  "Dark Mode",  "#1e293b"),
        ]):
            col = col_b1 if i == 0 else col_b2
            with col:
                st.markdown(f"""
                <div style="display:flex;flex-direction:column;align-items:center;
                  padding:25px;background:{bg_card};color:{text_main};border-radius:16px;
                  border:2px solid {color}20;box-shadow:0 4px 12px rgba(0,0,0,0.08);
                  height:140px;justify-content:center;">
                  <div style="font-size:32px;font-weight:900;color:{color};margin-bottom:8px;">
                    {avg_time:.1f}s</div>
                  <div style="font-size:14px;color:{color};font-weight:600;">{label}</div>
                  <div style="margin-top:12px;font-size:12px;color:#10b981;font-weight:700;">
                    {'FASTEST' if avg_time == min(avg_light_err, avg_dark_err) else 'Slower'}
                  </div>
                </div>""", unsafe_allow_html=True)
 
        # ============================================================
        # 7. STATISTICAL SUMMARY
        # ============================================================
        significant_tasks = sum(p < 0.05 for p in p_values)
        overall_sig  = "Signifikan" if overall_p < 0.05 else "Tidak Signifikan"
        method_name  = "Paired T-Test" if use_ttest else "Wilcoxon Signed Ranks"
 
        st.markdown("### Statistical Summary")
        st.markdown(f"""
        <div style="background:var(--secondary-background-color);padding:24px;border-radius:12px;
          border-left:4px solid #6366f1;">
          <div style="font-size:16px;font-weight:700;color:{text_main};margin-bottom:12px;">
            Overall Findings</div>
          <ul style="font-size:14px;color:{text_main};line-height:1.8;margin:0;">
            <li>Metode yang digunakan: <b>{method_name}</b></li>
            <li><b>{significant_tasks}/3 tasks</b> menunjukkan perbedaan signifikan (p &lt; 0.05)</li>
            <li><b>Overall {method_name}:</b> {stat_label}={overall_stat:.3f}, p={overall_p:.3f} — {overall_sig}</li>
            <li>Mean Light Mode: <b>{avg_light_err:.1f}s</b></li>
            <li>Mean Dark Mode: <b>{avg_dark_err:.1f}s</b></li>
            <li>{'Light Mode lebih cepat' if avg_light_err < avg_dark_err else 'Dark Mode lebih cepat'} secara deskriptif</li>
          </ul>
        </div>""", unsafe_allow_html=True)
 
        st.markdown("---")
        cap = "Paired Samples T-Test (Parametrik)" if use_ttest else "Wilcoxon Signed Ranks Test (Non-Parametrik)"
        st.caption(f"*{cap} · SPSS Compatible Output · Mean per User*")

# ======================
# ERROR RATE (WILCOXON - FIXED)
# ======================

if menu == "Error Rate":

    st.markdown(f"""
    <div style="font-size:28px;font-weight:700;color:{text_main};margin-bottom:10px;">
    Error Rate Analysis
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div style="font-size:14px;color:{text_soft};">
    Uji normalitas Shapiro-Wilk otomatis · Rekomendasi metode: Paired T-Test atau Wilcoxon Signed Ranks Test
    </div>
    """, unsafe_allow_html=True)

    # ======================
    # DATASET MANAGER
    # ======================
    with st.expander("Dataset Manager", expanded=False):
        dataset_manager(
            df_error,
            columns,
            file_error,
            "Dataset Error Rate",
            f"error_rate_{app}"
        )

    # ======================
    # DATA EDITOR
    # ======================
    st.markdown("### Dataset Input")
    
    df_edit = st.data_editor(
        df_error, 
        key="error_editor", 
        use_container_width=True,
        column_config={
            "Responden": st.column_config.TextColumn("Responden"),
            "Light_T1": st.column_config.NumberColumn("Light T1 (kesalahan)", min_value=0, step=1),
            "Light_T2": st.column_config.NumberColumn("Light T2 (kesalahan)", min_value=0, step=1),
            "Light_T3": st.column_config.NumberColumn("Light T3 (kesalahan)", min_value=0, step=1),
            "Dark_T1":  st.column_config.NumberColumn("Dark T1 (kesalahan)",  min_value=0, step=1),
            "Dark_T2":  st.column_config.NumberColumn("Dark T2 (kesalahan)",  min_value=0, step=1),
            "Dark_T3":  st.column_config.NumberColumn("Dark T3 (kesalahan)",  min_value=0, step=1),
        }
    )
    
    # Save button - FIXED WITH UNIQUE KEY
    if st.button("Simpan Data Error rate", type="primary", use_container_width=True):
        save_data("data_error", current_user, app, df_edit)
        st.session_state["saved_error"] = True
        st.rerun()

    if st.session_state.get("saved_error"):
        st.success("Data Error Rate berhasil disimpan!")
        st.session_state["saved_error"] = False

    # --- HAPUS DATA ---
    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)
    render_delete_button(
        file_path=file_error,
        label="Error Rate",
        columns=columns[1:],
        default_value=0,
        key_suffix="error"
    )


    # ======================
    # ANALYSIS BUTTON - FIXED WITH UNIQUE KEY
    # ======================
    data_kosong_err = df_edit[["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]].dropna(how="all").empty

    if st.button("ANALISIS DATA", type="secondary", key="analyze_error_rate"):
        task_cols_err = ["Light_T1","Light_T2","Light_T3","Dark_T1","Dark_T2","Dark_T3"]
        df_numeric_err = df_edit[task_cols_err].apply(pd.to_numeric, errors="coerce")
        baris_ada_err = df_numeric_err.dropna(how="all")

        if baris_ada_err.empty:
            st.warning("Data masih kosong. Silakan isi data terlebih dahulu.")
            st.stop()

        baris_tidak_lengkap_err = baris_ada_err.isnull().any(axis=1)
        jumlah_tidak_lengkap_err = baris_tidak_lengkap_err.sum()

        if jumlah_tidak_lengkap_err > 0:
            idx_err = baris_ada_err[baris_tidak_lengkap_err].index.tolist()
            responden_err = [f"R{i+1}" for i in idx_err]
            st.warning(
                f"Data belum lengkap! {jumlah_tidak_lengkap_err} responden belum mengisi semua task: "
                f"**{', '.join(responden_err)}**. "
                f"Setiap responden harus mengisi Light T1, T2, T3 dan Dark T1, T2, T3."
            )
            st.stop()
 
        st.markdown("---")
 
        # Hitung mean per user
        light_per_user = df_edit[["Light_T1","Light_T2","Light_T3"]].mean(axis=1)
        dark_per_user  = df_edit[["Dark_T1","Dark_T2","Dark_T3"]].mean(axis=1)
 
        # ============================================================
        # 1. UJI NORMALITAS — Shapiro-Wilk pada SELISIH (Dark − Light)
        # ============================================================
        st.markdown("### Uji Normalitas Selisih (Dark − Light)")
 
        norm_results = []
        for i in range(1, 4):
            r = shapiro_and_ks(
                df_edit[f"Light_T{i}"], df_edit[f"Dark_T{i}"],
                label=f"Dark_T{i} − Light_T{i}"
            )
            norm_results.append(r)
 
        r_overall = shapiro_and_ks(
            light_per_user, dark_per_user,
            label="Dark (mean) − Light (mean)"
        )
        norm_results.append(r_overall)
 
        render_normality_table(norm_results)
 
        rec = render_normality_recommendation(norm_results)
 
        # ============================================================
        # 2. PILIHAN METODE MANUAL
        # ============================================================
        st.markdown("#### Pilih Metode Uji Statistik")
        default_idx = 0 if rec == "t-test" else 1
        method_choice = st.radio(
            "Metode yang akan digunakan:",
            ["Paired Samples T-Test (Parametrik)",
             "Wilcoxon Signed Ranks Test (Non-Parametrik)"],
            index=default_idx,
            horizontal=True,
            key="method_choice_error"
        )
        use_ttest = method_choice.startswith("Paired")
 
        # ============================================================
        # 3. OVERALL METRICS
        # ============================================================
        st.markdown("---")
        st.markdown("### Overall Metrics")
 
        avg_light_err = light_per_user.mean()
        avg_dark_err  = dark_per_user.mean()
 
        task_avgs = pd.DataFrame({
            "Task":       ["T1", "T2", "T3"],
            "Light Mode": [df_edit[f"Light_T{i}"].mean() for i in range(1, 4)],
            "Dark Mode":  [df_edit[f"Dark_T{i}"].mean()  for i in range(1, 4)],
        })
 
        col1, col2, col3 = st.columns(3)
        with col1:
            better_mode = "Light" if avg_light_err < avg_dark_err else "Dark"
            dc = "normal" if avg_light_err < avg_dark_err else "inverse"
            st.metric("Lowest Error Rate", better_mode, f"{abs(avg_light_err - avg_dark_err):.1f} kesalahan", delta_color=dc)
        with col2:
            st.metric("Light Mode Avg", f"{avg_light_err:.1f} kesalahan")
        with col3:
            st.metric("Dark Mode Avg", f"{avg_dark_err:.1f} kesalahan")
 
        st.markdown("### Task Results")
        st.dataframe(task_avgs.round(2), use_container_width=True)
 
        # ============================================================
        # 4. UJI STATISTIK SESUAI PILIHAN
        # ============================================================
        p_values      = []
        z_or_t_values = []
 
        if use_ttest:
            st.markdown("### Paired Samples T-Test — Per Task")
            pairs_per_task = []
            for i in range(1, 4):
                light = pd.to_numeric(df_edit[f"Light_T{i}"], errors="coerce")
                dark  = pd.to_numeric(df_edit[f"Dark_T{i}"],  errors="coerce")
                item  = compute_paired_ttest_pair(light, dark, f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item)
                p_values.append(item["p_two"])
                z_or_t_values.append(item["t"])
            render_spss_paired_ttest(pairs_per_task)
 
            st.markdown("### Overall Paired T-Test (Mean per User)")
            overall_pair = compute_paired_ttest_pair(
                light_per_user, dark_per_user, "Light (mean)", "Dark (mean)"
            )
            render_spss_paired_ttest([overall_pair])
            overall_stat  = overall_pair["t"]
            overall_p     = overall_pair["p_two"]
            stat_label    = "t"
 
        else:
            st.markdown("### Wilcoxon Signed Ranks Test — Per Task")
            pairs_per_task = []
            for i in range(1, 4):
                light = pd.to_numeric(df_edit[f"Light_T{i}"], errors="coerce")
                dark  = pd.to_numeric(df_edit[f"Dark_T{i}"],  errors="coerce")
                item  = compute_wilcoxon_pair(light, dark, f"Light_T{i}", f"Dark_T{i}")
                pairs_per_task.append(item)
                p_values.append(item["p_val"])
                z_or_t_values.append(item["z_val"])
            render_spss_wilcoxon(pairs_per_task)
 
            st.markdown("### Overall Wilcoxon Test (Mean per User)")
            overall_item = compute_wilcoxon_pair(
                light_per_user, dark_per_user, "Light (mean)", "Dark (mean)"
            )
            render_spss_wilcoxon([overall_item])
            overall_stat  = overall_item["z_val"]
            overall_p     = overall_item["p_val"]
            stat_label    = "Z"
 
        # ============================================================
        # 5. VISUALIZATION
        # ============================================================
        st.markdown("### Visual Comparison")
 
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle("Error Rate Analysis", fontsize=16, fontweight='bold')
 
        x, width = np.arange(3), 0.35
        ax1.bar(x - width/2, task_avgs["Light Mode"], width, label='Light', color="#6366f1", alpha=0.8)
        ax1.bar(x + width/2, task_avgs["Dark Mode"],  width, label='Dark',  color="#1e293b", alpha=0.8)
        ax1.set_title("Per Task Comparison")
        ax1.set_xticks(x); ax1.set_xticklabels(["T1","T2","T3"])
        ax1.set_ylabel("Jumlah Kesalahan"); ax1.legend(); ax1.grid(True, alpha=0.3)
 
        ax2.hist(light_per_user.dropna(), bins=15, alpha=0.7, color="#6366f1", label='Light', density=True)
        ax2.hist(dark_per_user.dropna(),  bins=15, alpha=0.7, color="#1e293b", label='Dark',  density=True)
        ax2.set_title("Distribution (Mean per User)")
        ax2.set_xlabel("Jumlah Kesalahan"); ax2.legend(); ax2.grid(True, alpha=0.3)
 
        tasks = [f"T{i}" for i in range(1, 4)]
        colors_sig = ["#10b981" if p < 0.05 else "#ef4444" for p in p_values]
        ax3.bar(tasks, z_or_t_values, color=colors_sig, alpha=0.8)
        ax3.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax3.set_title("Paired T-Test t-values" if use_ttest else "Wilcoxon Z-Scores")
        ax3.grid(True, alpha=0.3)
 
        ax4.bar(tasks, p_values, color=colors_sig, alpha=0.8)
        ax4.axhline(y=0.05, color='red', linestyle='--', alpha=0.7, label='α=0.05')
        ax4.set_title("P-Values")
        ax4.set_ylim(0, max(0.3, max(p_values) * 1.1))
        ax4.legend(); ax4.grid(True, alpha=0.3)
 
        plt.tight_layout()
        st.pyplot(fig)
 
        # ============================================================
        # 6. BENCHMARK CARDS
        # ============================================================
        st.markdown("### Benchmark Results")
        col_b1, col_b2 = st.columns(2)
        for i, (error_rate, label, color) in enumerate([
            (avg_light_err, "Light Mode", "#6366f1"),
            (avg_dark_err,  "Dark Mode",  "#1e293b"),
        ]):
            col = col_b1 if i == 0 else col_b2
            with col:
                st.markdown(f"""
                <div style="display:flex;flex-direction:column;align-items:center;
                  padding:25px;background:{bg_card};color:{text_main};border-radius:16px;
                  border:2px solid {color}20;box-shadow:0 4px 12px rgba(0,0,0,0.08);
                  height:140px;justify-content:center;">
                  <div style="font-size:32px;font-weight:900;color:{color};margin-bottom:8px;">
                    {error_rate:.1f}</div>
                  <div style="font-size:14px;color:{color};font-weight:600;">{label}</div>
                  <div style="margin-top:12px;font-size:12px;color:#10b981;font-weight:700;">
                    {'LOWEST ERROR' if error_rate == min(avg_light_err, avg_dark_err) else 'Higher Error'}
                  </div>
                </div>""", unsafe_allow_html=True)
 
        # ============================================================
        # 7. STATISTICAL SUMMARY
        # ============================================================
        significant_tasks = sum(p < 0.05 for p in p_values)
        overall_sig  = "Signifikan" if overall_p < 0.05 else "Tidak Signifikan"
        method_name  = "Paired T-Test" if use_ttest else "Wilcoxon Signed Ranks"
 
        st.markdown("### Statistical Summary")
        st.markdown(f"""
        <div style="background:var(--secondary-background-color);padding:24px;border-radius:12px;
          border-left:4px solid #6366f1;">
          <div style="font-size:16px;font-weight:700;color:{text_main};margin-bottom:12px;">
            Overall Findings</div>
          <ul style="font-size:14px;color:{text_main};line-height:1.8;margin:0;">
            <li>Metode yang digunakan: <b>{method_name}</b></li>
            <li><b>{significant_tasks}/3 tasks</b> menunjukkan perbedaan signifikan (p &lt; 0.05)</li>
            <li><b>Overall {method_name}:</b> {stat_label}={overall_stat:.3f}, p={overall_p:.3f} — {overall_sig}</li>
            <li>Mean Light Mode: <b>{avg_light_err:.1f} kesalahan</b></li>
            <li>Mean Dark Mode: <b>{avg_dark_err:.1f} kesalahan</b></li>
            <li>{'Light Mode lebih sedikit kesalahan' if avg_light_err < avg_dark_err else 'Dark Mode lebih sedikit kesalahan'} secara deskriptif</li>
          </ul>
        </div>""", unsafe_allow_html=True)
 
        st.markdown("---")
        cap = "Paired Samples T-Test (Parametrik)" if use_ttest else "Wilcoxon Signed Ranks Test (Non-Parametrik)"
        st.caption(f"*{cap} · SPSS Compatible Output · Mean per User*")

# ==============================================================================
# MENU: UEQ ANALYSIS — STANDAR UEQ DATA ANALYSIS TOOL VERSION 13
# Logika identik dengan UEQ_Data_Analysis_Tool_Version13_Light_FB.xlsx
# Bahasa: Indonesia (sesuai pilihan bahasa di tool)
# ==============================================================================
 
# ==============================================================================
# MENU: UEQ ANALYSIS — STANDAR UEQ DATA ANALYSIS TOOL VERSION 13
# REVERSE_ITEMS terverifikasi langsung dari file Excel asli
# ==============================================================================

if menu == "UEQ Analysis":

    st.markdown(f"""
    <div style="font-size:24px;font-weight:700;color:{text_main};margin-bottom:4px;">
    Analisis UEQ (User Experience Questionnaire) — {app}
    </div>
    <div style="font-size:13px;color:{text_soft};margin-bottom:20px;">
    Logika identik UEQ Data Analysis Tool Version 13
    </div>
    """, unsafe_allow_html=True)

    # =========================================================================
    # KONSTANTA — TERVERIFIKASI DARI FILE EXCEL ASLI V13
    # REVERSE_ITEMS = item yang di-reverse pada sheet DT
    # Dicek satu per satu dari sheet DT: jika raw=7 → DT=+3, berarti TIDAK di-reverse
    #                                    jika raw=7 → DT=-3, berarti DI-REVERSE
    # =========================================================================
    REVERSE_ITEMS = {3, 4, 5, 9, 10, 12, 17, 18, 19, 21, 23, 24, 25}

    SKALA_MAP = {
        "Daya tarik":  [1, 12, 14, 16, 24, 25],
        "Kejelasan":   [2, 4, 13, 21],
        "Efisiensi":   [9, 20, 22, 23],
        "Ketepatan":   [8, 11, 17, 19],
        "Stimulasi":   [5, 6, 7, 18],
        "Kebaruan":    [3, 10, 15, 26],
    }

    LABEL_KIRI = [
        "menyusahkan","tak dapat dipahami","kreatif","mudah dipelajari",
        "bermanfaat","membosankan","tidak menarik","tak dapat diprediksi",
        "cepat","berdaya cipta","menghalangi","baik",
        "rumit","tidak disukai","lazim","tidak nyaman",
        "aman","memotivasi","memenuhi ekspektasi","tidak efisien",
        "jelas","tidak praktis","terorganisasi","atraktif",
        "ramah pengguna","konservatif",
    ]
    LABEL_KANAN = [
        "menyenangkan","dapat dipahami","monoton","sulit dipelajari",
        "kurang bermanfaat","mengasyikkan","menarik","dapat diprediksi",
        "lambat","konvensional","mendukung","buruk",
        "sederhana","menggembirakan","terdepan","nyaman",
        "tidak aman","tidak memotivasi","tidak memenuhi ekspektasi","efisien",
        "membingungkan","praktis","berantakan","tidak atraktif",
        "tidak ramah pengguna","inovatif",
    ]

    BENCHMARK = {
        "Daya tarik": {"Bad": 0.69, "Below Average": 1.18, "Above Average": 1.58, "Good": 1.84},
        "Kejelasan":  {"Bad": 0.72, "Below Average": 1.20, "Above Average": 1.73, "Good": 2.00},
        "Efisiensi":  {"Bad": 0.60, "Below Average": 1.05, "Above Average": 1.50, "Good": 1.88},
        "Ketepatan":  {"Bad": 0.78, "Below Average": 1.14, "Above Average": 1.48, "Good": 1.70},
        "Stimulasi":  {"Bad": 0.50, "Below Average": 1.00, "Above Average": 1.35, "Good": 1.70},
        "Kebaruan":   {"Bad": 0.16, "Below Average": 0.70, "Above Average": 1.12, "Good": 1.60},
    }

    # =========================================================================
    # FUNGSI INTI — TERVERIFIKASI IDENTIK DENGAN UEQ TOOLS V13
    # =========================================================================

    def ueq_transform(df_raw):
        return ueq_transform_global(df_raw)

    def ueq_scale_stats(df_raw):
        """
        Identik Results sheet UEQ Tools V13:
        - Per-person scale mean = mean item dalam skala per responden
        - Scale Mean = mean dari per-person scale means
        - Std Dev scale = std(per-person means, ddof=1)
        - CI = t(0.975, n-1) * std / sqrt(n)
        """
        dt = ueq_transform_global(df_raw)
        results = []
        for sk, items in SKALA_MAP.items():
            cols = [f"I{i}" for i in items]
            per_person = dt[cols].mean(axis=1).dropna()
            n = len(per_person)
            mean = float(per_person.mean())
            var  = float(per_person.var(ddof=1))
            std  = float(per_person.std(ddof=1))
            t_crit = t_dist.ppf(0.975, df=n - 1) if n > 1 else 1.96
            ci = t_crit * std / np.sqrt(n) if n > 0 else np.nan
            results.append({
                "Skala":          sk,
                "N":              n,
                "Mean":           round(mean, 4),
                "Varians":        round(var,  4),
                "Std. Dev.":      round(std,  4),
                "Confidence (±)": round(ci,   4),
                "CI Bawah":       round(mean - ci, 4),
                "CI Atas":        round(mean + ci, 4),
            })
        return pd.DataFrame(results)

    def ueq_item_stats(df_raw):
        dt = ueq_transform(df_raw)
        rows = []
        for i in range(1, 27):
            col  = f"I{i}"
            vals = dt[col].dropna() if col in dt.columns else pd.Series(dtype=float)
            n    = len(vals)
            mean = float(vals.mean()) if n > 0 else np.nan
            var  = float(vals.var(ddof=1)) if n > 1 else 0.0
            std  = var ** 0.5
            t_cr = t_dist.ppf(0.975, df=n - 1) if n > 1 else 1.96
            ci   = t_cr * std / np.sqrt(n) if n > 0 else np.nan
            rows.append({
                "Item":           i,
                "Kiri":           LABEL_KIRI[i - 1],
                "Kanan":          LABEL_KANAN[i - 1],
                "Skala":          next((s for s, it in SKALA_MAP.items() if i in it), "-"),
                "Mean":           round(mean, 2),
                "Varians":        round(var,  2),
                "Std. Dev.":      round(std,  2),
                "N":              n,
                "Confidence (±)": round(ci,   3),
                "CI Bawah":       round(mean - ci, 3),
                "CI Atas":        round(mean + ci, 3),
            })
        return pd.DataFrame(rows)

    def benchmark_kategori(mean, skala):
        b = BENCHMARK[skala]
        if mean >= b["Good"]:           return "Good"
        elif mean >= b["Above Average"]:return "Above Average"
        elif mean >= b["Below Average"]:return "Below Average"
        elif mean >= b["Bad"]:          return "Bad"            # ← benar
        else:                              return "Bad"

    def benchmark_interpretasi(k):
        return {
            "Good":          "25% hasil lebih baik, 75% lebih buruk",
            "Above Average": "25% hasil lebih baik, 50% lebih buruk",
            "Below Average": "50% hasil lebih baik, 25% lebih buruk",
            "Bad":           "75% atau lebih hasil lebih baik",
        }.get(k, "")

    def interpret_category(score):
        if score > 1.5:    return "Excellent"
        elif score > 0.8:  return "Good"
        elif score > 0.0:  return "Above Average"
        elif score > -0.8: return "Below Average"
        else:              return "Bad"

    def inconsistency_check(df_raw):
        dt = ueq_transform(df_raw)
        raw_num = df_raw.apply(pd.to_numeric, errors="coerce")
        hasil = []
        for idx in range(len(dt)):
            row = dt.iloc[idx]
            crit = sum(
                1 for sk, items in SKALA_MAP.items()
                if len(vals := row[[f"I{i}" for i in items]].dropna()) >= 2
                and (vals.max() - vals.min()) > 3
            )
            raw_row = raw_num.iloc[idx] if idx < len(raw_num) else pd.Series()
            same = int(raw_row.value_counts().max()) if len(raw_row) > 0 else 0
            hasil.append({
                "Responden":       f"R{idx + 1}",
                "Skala Kritis":    crit,
                "Perlu Dihapus?":  "Ya" if crit >= 3 else "Tidak",
                "Jawaban Identik": same,
                "Critical Length": "Ya" if same > 15 else "Tidak",
            })
        return pd.DataFrame(hasil)

    # =========================================================================
    # LOAD DATA
    # =========================================================================
    items_label = [f"I{i}" for i in range(1, 27)]

    u_light = load_ueq("data_ueq_light", current_user, app, n)
    u_dark  = load_ueq("data_ueq_dark",  current_user, app, n)

    u_light_disp = u_light.copy()
    u_light_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(u_light_disp))])
    u_dark_disp = u_dark.copy()
    u_dark_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(u_dark_disp))])

    # =========================================================================
    # TAB NAVIGASI
    # =========================================================================
    tab_input, tab_dt, tab_hasil, tab_ci, tab_dist, tab_bench, tab_inkonsisten = st.tabs([
        "Data Mentah", "Data Transformation (DT)", "Hasil Skala",
        "Confidence Interval", "Distribusi Jawaban", "Benchmark", "Deteksi Inkonsistensi",
    ])

    # ------------------------------------------------------------------
    # TAB 1: DATA MENTAH
    # ------------------------------------------------------------------
    with tab_input:
        st.markdown("### Input Data Skor Kuesioner (Skala 1-7)")
        st.caption("1 = alternatif paling kiri, 7 = alternatif paling kanan.")

        with st.expander("Dataset Manager — Light Mode", expanded=False):
            dataset_manager(u_light, items_label, file_ueq_light, "UEQ Light Mode", f"ueq_light_{app}")
        with st.expander("Dataset Manager — Dark Mode", expanded=False):
            dataset_manager(u_dark, items_label, file_ueq_dark, "UEQ Dark Mode", f"ueq_dark_{app}")

        st.markdown("---")
        st.markdown(f"**Light Mode** (n={n})")
        edit_l = st.data_editor(
            u_light_disp, key="ueq_raw_light", use_container_width=True,
            column_config={
                "Responden": st.column_config.TextColumn(disabled=True),
                **{f"I{i}": st.column_config.NumberColumn(f"I{i}", min_value=1, max_value=7, step=1)
                   for i in range(1, 27)}
            }
        )

        st.markdown("---")
        st.markdown(f"**Dark Mode** (n={n})")
        edit_d = st.data_editor(
            u_dark_disp, key="ueq_raw_dark", use_container_width=True,
            column_config={
                "Responden": st.column_config.TextColumn(disabled=True),
                **{f"I{i}": st.column_config.NumberColumn(f"I{i}", min_value=1, max_value=7, step=1)
                   for i in range(1, 27)}
            }
        )

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        if st.button("Simpan Data Kuesioner", type="primary", use_container_width=True):
            save_ueq("data_ueq_light", current_user, app, edit_l[items_label])
            save_ueq("data_ueq_dark",  current_user, app, edit_d[items_label])
            st.session_state["saved_ueq"] = True
            st.rerun()

        if st.session_state.get("saved_ueq"):
            st.success("Data UEQ berhasil disimpan!")
            st.session_state["saved_ueq"] = False

        st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
        col_del_l, col_del_d = st.columns(2)
        with col_del_l:
            render_delete_button(file_path=file_ueq_light, label="UEQ Light Mode",
                                 columns=items_label, default_value=4, key_suffix="ueq_light")
        with col_del_d:
            render_delete_button(file_path=file_ueq_dark, label="UEQ Dark Mode",
                                 columns=items_label, default_value=4, key_suffix="ueq_dark")

    # Compute from edited data
    df_light_clean = edit_l[items_label].apply(pd.to_numeric, errors="coerce")
    df_dark_clean  = edit_d[items_label].apply(pd.to_numeric, errors="coerce")
    dt_light       = ueq_transform(df_light_clean)
    dt_dark        = ueq_transform(df_dark_clean)
    stats_light    = ueq_scale_stats(df_light_clean)
    stats_dark     = ueq_scale_stats(df_dark_clean)
    item_light     = ueq_item_stats(df_light_clean)
    item_dark      = ueq_item_stats(df_dark_clean)

    # ------------------------------------------------------------------
    # TAB 2: DATA TRANSFORMATION (DT)
    # ------------------------------------------------------------------
    with tab_dt:
        st.markdown("### Data Transformation — Identik Sheet DT")
        st.caption("Nilai dikonversi ke rentang -3 s.d. +3 (Nilai - 4). Item negatif di-reverse (x-1).")
        st.caption(f"**Item yang di-reverse:** {sorted(REVERSE_ITEMS)}")

        col_dt1, col_dt2 = st.columns(2)
        with col_dt1:
            st.markdown("**Light Mode**")
            dt_l_disp = dt_light.copy().round(2)
            dt_l_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(dt_l_disp))])
            st.dataframe(dt_l_disp, use_container_width=True)
        with col_dt2:
            st.markdown("**Dark Mode**")
            dt_d_disp = dt_dark.copy().round(2)
            dt_d_disp.insert(0, "Responden", [f"R{i+1}" for i in range(len(dt_d_disp))])
            st.dataframe(dt_d_disp, use_container_width=True)

        # Scale means per person table (seperti di DT sheet Excel)
        st.markdown("#### Scale Means per Person")
        col_sm1, col_sm2 = st.columns(2)
        for col_sm, df_dt, label in [(col_sm1, dt_light, "Light"), (col_sm2, dt_dark, "Dark")]:
            with col_sm:
                st.markdown(f"**{label} Mode**")
                sm_rows = {"Responden": [f"R{i+1}" for i in range(len(df_dt))]}
                for sk, items in SKALA_MAP.items():
                    cols = [f"I{i}" for i in items]
                    sm_rows[sk] = df_dt[cols].mean(axis=1).round(4).values
                st.dataframe(pd.DataFrame(sm_rows), use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # TAB 3: HASIL SKALA
    # ------------------------------------------------------------------
    with tab_hasil:
        st.markdown("### Hasil Analisis Skala UEQ — Identik Sheet Results")

        # Tabel gabungan Light vs Dark
        tabel_gabung = pd.DataFrame({
            "Skala":      stats_light["Skala"],
            "Mean Light": stats_light["Mean"],
            "Var. Light": stats_light["Varians"],
            "Mean Dark":  stats_dark["Mean"],
            "Var. Dark":  stats_dark["Varians"],
        })
        tabel_gabung["Unggul"] = tabel_gabung.apply(
            lambda r: "Light Mode" if r["Mean Light"] > r["Mean Dark"] else
                      ("Dark Mode" if r["Mean Dark"] > r["Mean Light"] else "Seimbang"), axis=1
        )
        st.table(tabel_gabung)

        # Pragmatic & Hedonic Quality
        pq_light = stats_light[stats_light["Skala"].isin(["Kejelasan","Efisiensi","Ketepatan"])]["Mean"].mean()
        pq_dark  = stats_dark [stats_dark ["Skala"].isin(["Kejelasan","Efisiensi","Ketepatan"])]["Mean"].mean()
        hq_light = stats_light[stats_light["Skala"].isin(["Stimulasi","Kebaruan"])]["Mean"].mean()
        hq_dark  = stats_dark [stats_dark ["Skala"].isin(["Stimulasi","Kebaruan"])]["Mean"].mean()
        at_light = float(stats_light[stats_light["Skala"]=="Daya tarik"]["Mean"].values[0])
        at_dark  = float(stats_dark [stats_dark ["Skala"]=="Daya tarik"]["Mean"].values[0])

        st.markdown("#### Pragmatic Quality & Hedonic Quality")
        c1, c2, c3 = st.columns(3)
        for col, title, lv, dv, sub in [
            (c1, "Daya Tarik",        at_light, at_dark, "Attractiveness"),
            (c2, "Kualitas Pragmatis", pq_light, pq_dark, "Kejelasan · Efisiensi · Ketepatan"),
            (c3, "Kualitas Hedonis",   hq_light, hq_dark, "Stimulasi · Kebaruan"),
        ]:
            col.markdown(f"""
            <div class="card" style="text-align:center;">
                <div class="metric-title">{title}</div>
                <div style="font-size:20px;font-weight:700;">
                    <span class="val-light">{lv:.4f}</span>
                    <span class="vs-divider"> | </span>
                    <span class="val-dark">{dv:.4f}</span>
                </div>
                <div style="font-size:11px;color:#6b7280;margin-top:4px;">{sub}</div>
            </div>
            """, unsafe_allow_html=True)

        # Grafik Mean Skala (identik tampilan UEQ Tools Excel)
        st.markdown("#### Grafik Perbandingan Mean Skala (-3 s.d. +3)")
        fig_bar = go.Figure()
        skala_list = list(SKALA_MAP.keys())

        fig_bar.add_trace(go.Bar(
            x=stats_light["Skala"], y=stats_light["Mean"], name="Light Mode",
            marker_color="#6366f1",
            text=[f"{v:.4f}" for v in stats_light["Mean"]],
            textposition="outside",
            error_y=dict(
                type='data',
                array=stats_light["Confidence (±)"].tolist(),
                visible=True,
                color="#6366f1",
                thickness=1.5,
                width=6
            )
        ))
        fig_bar.add_trace(go.Bar(
            x=stats_dark["Skala"], y=stats_dark["Mean"], name="Dark Mode",
            marker_color="#a78bfa",
            text=[f"{v:.4f}" for v in stats_dark["Mean"]],
            textposition="outside",
            error_y=dict(
                type='data',
                array=stats_dark["Confidence (±)"].tolist(),
                visible=True,
                color="#a78bfa",
                thickness=1.5,
                width=6
            )
        ))
        fig_bar.add_hline(y=0.0,  line_color="black",  line_width=1)
        fig_bar.add_hline(y=0.8,  line_dash="dot", line_color="#10b981", line_width=1.5,
                          annotation_text="Batas Positif (0.8)", annotation_position="right")
        fig_bar.add_hline(y=-0.8, line_dash="dot", line_color="#ef4444", line_width=1.5,
                          annotation_text="Batas Negatif (-0.8)", annotation_position="right")
        fig_bar.update_layout(
            yaxis=dict(range=[-3, 3], title="Mean Score", dtick=0.5),
            barmode="group", height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # Versi -2 sampai +2 (untuk presentasi)
        st.markdown("#### Grafik Mean Skala (Skala -2 s.d. +2) — Versi Presentasi")
        fig_bar2 = go.Figure()
        fig_bar2.add_trace(go.Bar(
            x=stats_light["Skala"], y=stats_light["Mean"], name="Light Mode",
            marker_color="#6366f1",
            text=[f"{v:.4f}" for v in stats_light["Mean"]],
            textposition="outside",
        ))
        fig_bar2.add_trace(go.Bar(
            x=stats_dark["Skala"], y=stats_dark["Mean"], name="Dark Mode",
            marker_color="#a78bfa",
            text=[f"{v:.4f}" for v in stats_dark["Mean"]],
            textposition="outside",
        ))
        fig_bar2.add_hline(y=0.0,  line_color="black", line_width=1)
        fig_bar2.add_hline(y=0.8,  line_dash="dot", line_color="#10b981", line_width=1.5,
                           annotation_text="Batas Positif (0.8)", annotation_position="right")
        fig_bar2.add_hline(y=-0.8, line_dash="dot", line_color="#ef4444", line_width=1.5,
                           annotation_text="Batas Negatif (-0.8)", annotation_position="right")
        fig_bar2.update_layout(
            yaxis=dict(range=[-2, 2], title="Mean Score", dtick=0.5),
            barmode="group", height=480,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bar2, use_container_width=True)

        # Interpretasi kategori
        st.markdown("#### Interpretasi Kualitas Skala")
        col_il, col_id = st.columns(2)
        with col_il:
            st.markdown("**Light Mode**")
            cat_l = stats_light.copy()
            cat_l["Kategori"] = cat_l["Mean"].apply(interpret_category)
            st.dataframe(cat_l[["Skala","Mean","Varians","Kategori"]], use_container_width=True, hide_index=True)
        with col_id:
            st.markdown("**Dark Mode**")
            cat_d = stats_dark.copy()
            cat_d["Kategori"] = cat_d["Mean"].apply(interpret_category)
            st.dataframe(cat_d[["Skala","Mean","Varians","Kategori"]], use_container_width=True, hide_index=True)

        # Tabel per item
        st.markdown("#### Analisis Per Item")
        col_il2, col_id2 = st.columns(2)
        with col_il2:
            st.markdown("**Light Mode**")
            st.dataframe(item_light[["Item","Kiri","Kanan","Skala","Mean","Varians","Std. Dev.","N"]],
                         use_container_width=True, hide_index=True)
        with col_id2:
            st.markdown("**Dark Mode**")
            st.dataframe(item_dark[["Item","Kiri","Kanan","Skala","Mean","Varians","Std. Dev.","N"]],
                         use_container_width=True, hide_index=True)

        # Grafik per item (SPSS style error bar)
        st.markdown("#### Grafik Mean Per Item dengan Confidence Interval")
        mode_item = st.radio("Mode:", ["Light Mode","Dark Mode"], horizontal=True, key="item_chart_mode")
        item_stats_sel = item_light if mode_item == "Light Mode" else item_dark
        color_sel = "#6366f1" if mode_item == "Light Mode" else "#a78bfa"

        fig_item = go.Figure()
        fig_item.add_trace(go.Scatter(
            x=[f"I{i}" for i in item_stats_sel["Item"]],
            y=item_stats_sel["Mean"],
            mode="markers+lines",
            marker=dict(color=color_sel, size=8),
            line=dict(color=color_sel, width=1.5),
            error_y=dict(
                type='data',
                array=item_stats_sel["Confidence (±)"].tolist(),
                visible=True,
                color=color_sel,
                thickness=1.5,
                width=5
            ),
            name=mode_item
        ))
        fig_item.add_hline(y=0, line_color="gray", line_dash="dot", line_width=1)
        fig_item.add_hline(y=0.8,  line_color="#10b981", line_dash="dot", line_width=1)
        fig_item.add_hline(y=-0.8, line_color="#ef4444", line_dash="dot", line_width=1)

        # Beri warna background per skala
        skala_colors = {
            "Daya tarik": "rgba(99,102,241,0.05)", "Kejelasan": "rgba(16,185,129,0.05)",
            "Efisiensi": "rgba(245,158,11,0.05)", "Ketepatan": "rgba(239,68,68,0.05)",
            "Stimulasi": "rgba(168,85,247,0.05)", "Kebaruan": "rgba(59,130,246,0.05)",
        }
        item_x = [f"I{i}" for i in range(1, 27)]
        for sk, items in SKALA_MAP.items():
            x0 = f"I{min(items)}"
            x1 = f"I{max(items)}"
            fig_item.add_vrect(
                x0=x0, x1=x1,
                fillcolor=skala_colors.get(sk, "rgba(200,200,200,0.05)"),
                layer="below", line_width=0,
                annotation_text=sk, annotation_position="top left",
                annotation_font_size=9
            )

        fig_item.update_layout(
            yaxis=dict(range=[-3, 3], title="Mean Score", dtick=0.5),
            xaxis=dict(title="Item"),
            height=450,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            showlegend=True
        )
        st.plotly_chart(fig_item, use_container_width=True)

        avg_l = stats_light["Mean"].mean()
        avg_d = stats_dark["Mean"].mean()
        unggul = "Light Mode" if avg_l > avg_d else "Dark Mode"
        st.success(
            f"**Kesimpulan:** {unggul} lebih unggul pada aplikasi {app} "
            f"(Light: {avg_l:.4f} | Dark: {avg_d:.4f})."
        )

    # ------------------------------------------------------------------
    # TAB 4: CONFIDENCE INTERVAL
    # ------------------------------------------------------------------
    with tab_ci:
        st.markdown("### Confidence Interval (95%) per Skala")
        st.caption("Semakin kecil CI, semakin tinggi presisi estimasi mean skala.")

        col_ci1, col_ci2 = st.columns(2)
        with col_ci1:
            st.markdown("**Light Mode**")
            st.dataframe(
                stats_light[["Skala","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]],
                use_container_width=True, hide_index=True
            )
        with col_ci2:
            st.markdown("**Dark Mode**")
            st.dataframe(
                stats_dark[["Skala","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]],
                use_container_width=True, hide_index=True
            )

        # Grafik CI per skala (seperti di Confidence_Intervals sheet Excel)
        st.markdown("#### Grafik Confidence Interval per Skala")
        fig_ci = go.Figure()
        skala_names = stats_light["Skala"].tolist()
        x_pos = list(range(len(skala_names)))

        for i, (label, stats_sel, color) in enumerate([
            ("Light Mode", stats_light, "#6366f1"),
            ("Dark Mode",  stats_dark,  "#a78bfa")
        ]):
            offset = -0.15 if i == 0 else 0.15
            fig_ci.add_trace(go.Scatter(
                x=[x + offset for x in x_pos],
                y=stats_sel["Mean"].tolist(),
                error_y=dict(
                    type='data',
                    array=stats_sel["Confidence (±)"].tolist(),
                    visible=True,
                    color=color,
                    thickness=2,
                    width=8
                ),
                mode="markers",
                marker=dict(color=color, size=10, symbol="circle"),
                name=label
            ))

        fig_ci.add_hline(y=0,   line_color="gray",    line_dash="solid", line_width=1)
        fig_ci.add_hline(y=0.8, line_color="#10b981", line_dash="dot",   line_width=1,
                         annotation_text="0.8", annotation_position="right")
        fig_ci.add_hline(y=-0.8,line_color="#ef4444", line_dash="dot",   line_width=1,
                         annotation_text="-0.8", annotation_position="right")
        fig_ci.update_layout(
            xaxis=dict(tickvals=x_pos, ticktext=skala_names, title="Skala"),
            yaxis=dict(range=[-3, 3], title="Mean Score", dtick=0.5),
            height=450,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02)
        )
        st.plotly_chart(fig_ci, use_container_width=True)

        st.markdown("#### CI Per Item")
        col_ci3, col_ci4 = st.columns(2)
        with col_ci3:
            st.markdown("**Light Mode**")
            st.dataframe(
                item_light[["Item","Kiri","Kanan","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]],
                use_container_width=True, hide_index=True
            )
        with col_ci4:
            st.markdown("**Dark Mode**")
            st.dataframe(
                item_dark[["Item","Kiri","Kanan","Mean","Std. Dev.","N","Confidence (±)","CI Bawah","CI Atas"]],
                use_container_width=True, hide_index=True
            )

    # ------------------------------------------------------------------
    # TAB 5: DISTRIBUSI JAWABAN
    # ------------------------------------------------------------------
    with tab_dist:
        st.markdown("### Distribusi Jawaban per Item")
        mode_dist = st.radio("Pilih Mode", ["Light Mode","Dark Mode"], horizontal=True, key="dist_mode")
        df_dist = df_light_clean if mode_dist == "Light Mode" else df_dark_clean

        dist_rows = []
        for i in range(1, 27):
            col = f"I{i}"
            vals = df_dist[col].dropna() if col in df_dist.columns else pd.Series(dtype=float)
            counts = {v: 0 for v in range(1, 8)}
            for v in vals:
                try:
                    counts[int(v)] += 1
                except (ValueError, KeyError):
                    pass
            dist_rows.append({
                "Item":  i,
                "Label": f"{LABEL_KIRI[i-1]} / {LABEL_KANAN[i-1]}",
                "Skala": next((s for s, it in SKALA_MAP.items() if i in it), "-"),
                **{str(k): counts[k] for k in range(1, 8)},
            })
        df_dist_table = pd.DataFrame(dist_rows)
        st.dataframe(df_dist_table, use_container_width=True, hide_index=True)

        # Grafik distribusi stacked bar per item
        st.markdown("#### Grafik Distribusi Jawaban")
        dist_colors = ["#ef4444","#f97316","#eab308","#22c55e","#3b82f6","#6366f1","#8b5cf6"]
        fig_dist = go.Figure()
        for cat in range(1, 8):
            fig_dist.add_trace(go.Bar(
                name=f"Kategori {cat}",
                x=[f"I{i}" for i in range(1, 27)],
                y=df_dist_table[str(cat)].tolist(),
                marker_color=dist_colors[cat-1],
            ))
        fig_dist.update_layout(
            barmode="stack",
            height=400,
            yaxis=dict(title="Jumlah Responden"),
            xaxis=dict(title="Item"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_dist, use_container_width=True)

    # ------------------------------------------------------------------
    # TAB 6: BENCHMARK
    # ------------------------------------------------------------------
    with tab_bench:
        st.markdown("### Benchmark UEQ — Identik Sheet Benchmark")
        st.caption("Benchmark: 468 studi, 21.175 responden.")

        BENCH_RANGES = {
            "Daya tarik": {"p25":0.69,"p50":1.18,"p75":1.58,"p90":1.84},
            "Kejelasan":  {"p25":0.72,"p50":1.20,"p75":1.73,"p90":2.00},
            "Efisiensi":  {"p25":0.60,"p50":1.05,"p75":1.50,"p90":1.88},
            "Ketepatan":  {"p25":0.78,"p50":1.14,"p75":1.48,"p90":1.70},
            "Stimulasi":  {"p25":0.50,"p50":1.00,"p75":1.35,"p90":1.70},
            "Kebaruan":   {"p25":0.16,"p50":0.70,"p75":1.12,"p90":1.60},
        }

        def get_benchmark_cat(mean, skala):
            b = BENCH_RANGES[skala]
            if mean >= b["p90"]:    return "Excellent"
            elif mean >= b["p75"]:  return "Good"
            elif mean >= b["p50"]:  return "Above Average"
            elif mean >= b["p25"]:  return "Below Average"
            else:                   return "Bad"

        def get_bench_interp(kat):
            return {
                "Excellent":     "10% hasil lebih baik, 90% lebih buruk",
                "Good":          "25% hasil lebih baik, 75% lebih buruk",
                "Above Average": "25% hasil lebih baik, 50% lebih buruk",
                "Below Average": "50% hasil lebih baik, 25% lebih buruk",
                "Bad":           "75% atau lebih hasil lebih baik",
            }.get(kat, "")

        bench_rows = []
        for _, row_l in stats_light.iterrows():
            sk    = row_l["Skala"]
            row_d = stats_dark[stats_dark["Skala"] == sk].iloc[0]
            b     = BENCH_RANGES[sk]
            bench_rows.append({
                "Skala":            sk,
                "Mean Light":       row_l["Mean"],
                "Kategori Light":   get_benchmark_cat(row_l["Mean"], sk),
                "Mean Dark":        row_d["Mean"],
                "Kategori Dark":    get_benchmark_cat(row_d["Mean"], sk),
                "Bad (<p25)":       f"< {b['p25']}",
                "Below Avg (p25-p50)": f"{b['p25']} - {b['p50']}",
                "Above Avg (p50-p75)": f"{b['p50']} - {b['p75']}",
                "Good (p75-p90)":   f"{b['p75']} - {b['p90']}",
                "Excellent (>=p90)":f">= {b['p90']}",
            })
        st.dataframe(pd.DataFrame(bench_rows), use_container_width=True, hide_index=True)

        # Grafik Benchmark (identik dengan Excel Benchmark chart)
        st.markdown("#### Grafik Benchmark")
        mode_bench = st.radio("Mode:", ["Light Mode","Dark Mode"], horizontal=True, key="bench_mode")
        stats_bench = stats_light if mode_bench == "Light Mode" else stats_dark
        color_bench = "#6366f1" if mode_bench == "Light Mode" else "#a78bfa"

        COLOR_BENCH = {
            "Excellent":     "#27500A",
            "Good":          "#185FA5",
            "Above Average": "#534AB7",
            "Below Average": "#854F0B",
            "Bad":           "#A32D2D",
        }

        fig_bench = go.Figure()

        # Background zones (Bad/Below/Above/Good/Excellent)
        skala_x = stats_bench["Skala"].tolist()
        for lbl, key_lo, key_hi, color_fill in [
            ("Bad",           None,  "p25", "rgba(220,53,69,0.08)"),
            ("Below Average", "p25", "p50", "rgba(255,165,0,0.08)"),
            ("Above Average", "p50", "p75", "rgba(173,216,230,0.08)"),
            ("Good",          "p75", "p90", "rgba(144,238,144,0.08)"),
            ("Excellent",     "p90", None,  "rgba(0,128,0,0.12)"),
        ]:
            # Use first skala's benchmark as reference y for zone
            ref_skala = skala_x[0] if skala_x else "Daya tarik"
            b_ref = BENCH_RANGES[ref_skala]
            y0 = -3 if key_lo is None else b_ref[key_lo]
            y1 = 3  if key_hi is None else b_ref[key_hi]
            # Not a perfect zone chart but adds reference lines
        
        # Add benchmark reference lines
        for key, style, color_line in [
            ("p25", "dash", "#f97316"),
            ("p50", "dot",  "#eab308"),
            ("p75", "dash", "#22c55e"),
            ("p90", "longdash", "#16a34a"),
        ]:
            y_vals = [BENCH_RANGES[s][key] for s in skala_x]
            fig_bench.add_trace(go.Scatter(
                x=skala_x, y=y_vals, mode="lines",
                name=f"p{key[1:]} benchmark",
                line=dict(dash=style, width=1.5, color=color_line),
                showlegend=True,
            ))

        # Bar per skala dengan warna kategori
        for _, row in stats_bench.iterrows():
            kat = get_benchmark_cat(row["Mean"], row["Skala"])
            fig_bench.add_trace(go.Bar(
                x=[row["Skala"]], y=[row["Mean"]],
                name=f"{row['Skala']} ({kat})",
                marker_color=COLOR_BENCH.get(kat, "#888"),
                text=f"{row['Mean']:.4f}<br>{kat}",
                textposition="outside",
                showlegend=False,
            ))

        # CI error bars on benchmark chart
        fig_bench.add_trace(go.Scatter(
            x=stats_bench["Skala"].tolist(),
            y=stats_bench["Mean"].tolist(),
            mode="markers",
            marker=dict(color=color_bench, size=8, symbol="diamond"),
            error_y=dict(
                type='data',
                array=stats_bench["Confidence (±)"].tolist(),
                visible=True,
                color=color_bench,
                thickness=2,
                width=8
            ),
            name=f"{mode_bench} (dengan CI)",
            showlegend=True,
        ))

        fig_bench.add_hline(y=0, line_color="black", line_width=1)
        fig_bench.update_layout(
            yaxis=dict(range=[-1, 3], title="Mean Score", dtick=0.25),
            barmode="overlay",
            height=520,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bench, use_container_width=True)

        # Interpretasi benchmark
        st.markdown("#### Interpretasi Benchmark")
        interp_rows = []
        for _, row in stats_bench.iterrows():
            kat = get_benchmark_cat(row["Mean"], row["Skala"])
            interp_rows.append({
                "Skala":         row["Skala"],
                "Mean":          row["Mean"],
                "Benchmark":     kat,
                "Interpretasi":  get_bench_interp(kat),
            })
        st.dataframe(pd.DataFrame(interp_rows), use_container_width=True, hide_index=True)

        # Perbandingan Light vs Dark pada benchmark
        st.markdown("#### Perbandingan Light Mode vs Dark Mode pada Benchmark")
        fig_bench_cmp = go.Figure()
        skala_x = stats_light["Skala"].tolist()
        
        for key, color_line, label_line in [
            ("p25", "#f97316", "p25"), ("p50", "#eab308", "p50"),
            ("p75", "#22c55e", "p75"), ("p90", "#16a34a", "p90"),
        ]:
            y_vals = [BENCH_RANGES[s][key] for s in skala_x]
            fig_bench_cmp.add_trace(go.Scatter(
                x=skala_x, y=y_vals, mode="lines",
                name=label_line,
                line=dict(dash="dot", width=1, color=color_line),
            ))

        fig_bench_cmp.add_trace(go.Bar(
            x=stats_light["Skala"].tolist(),
            y=stats_light["Mean"].tolist(),
            name="Light Mode",
            marker_color="rgba(99,102,241,0.7)",
            text=[f"{v:.4f}" for v in stats_light["Mean"]],
            textposition="outside",
        ))
        fig_bench_cmp.add_trace(go.Bar(
            x=stats_dark["Skala"].tolist(),
            y=stats_dark["Mean"].tolist(),
            name="Dark Mode",
            marker_color="rgba(167,139,250,0.7)",
            text=[f"{v:.4f}" for v in stats_dark["Mean"]],
            textposition="outside",
        ))
        fig_bench_cmp.update_layout(
            barmode="group", height=480,
            yaxis=dict(range=[-1, 3], title="Mean Score", dtick=0.25),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bench_cmp, use_container_width=True)

    # ------------------------------------------------------------------
    # TAB 7: DETEKSI INKONSISTENSI
    # ------------------------------------------------------------------
    with tab_inkonsisten:
        st.markdown("### Deteksi Jawaban Tidak Konsisten — Identik Sheet Inconsistencies")
        mode_ink = st.radio("Pilih Mode", ["Light Mode","Dark Mode"], horizontal=True, key="inkons_mode")
        df_ink   = df_light_clean if mode_ink == "Light Mode" else df_dark_clean
        df_check = inconsistency_check(df_ink)

        def highlight_inkons(row):
            if row["Perlu Dihapus?"].startswith("Ya") or row["Critical Length"].startswith("Ya"):
                return ["background-color:rgba(245, 158, 11, 0.2)"] * len(row)
            return [""] * len(row)

        st.dataframe(
            df_check.style.apply(highlight_inkons, axis=1),
            use_container_width=True, hide_index=True
        )

        n_hapus = (df_check["Perlu Dihapus?"].str.startswith("Ya")).sum()
        n_crit  = (df_check["Critical Length"].str.startswith("Ya")).sum()
        if n_hapus > 0 or n_crit > 0:
            st.warning(
                f"Ditemukan {n_hapus} responden dengan 3+ skala kritis "
                f"dan {n_crit} dengan Critical Length."
            )
        else:
            st.success("Tidak ditemukan jawaban yang mencurigakan.")

    st.markdown("---")
    st.caption(
        "UEQ Analysis · Logika identik UEQ Data Analysis Tool Version 13 · "
        "Benchmark: 468 studi, 21.175 responden · Muhammad Farhan, UII 2026"
    )
            

# ==============================================================================
# MENU: PREFERENSI RESPONDEN (TANPA IKON - DENGAN DATASET MANAGER)
# ==============================================================================

if menu == "Preferensi Responden":

    st.markdown(f"""
    <div style="font-size:28px;font-weight:700;color:{text_main};margin-bottom:10px;">
    Preferensi Responden - {app}
    </div>
    """, unsafe_allow_html=True)

    st.info("""
    Metode Analisis: Mean Preference Analysis (Skala Likert 1–7, Bipolar).
    Nilai 1 = kecenderungan Light Mode · Nilai 7 = kecenderungan Dark Mode · Nilai 4 = Netral.
    Sistem otomatis melakukan Reverse Scoring (8 − Nilai Asli) pada pernyataan negatif sebelum 
    digabungkan menjadi Grand Mean per aspek (Keterbacaan, Kelelahan Mata, Usability, 
    Konsumsi Baterai, Efisiensi Kinerja, Estetika & Daya Tarik).
    """)
    
    # Definisi instrumen kolom sesuai metodologi penelitian[cite: 1]
    columns_pref = [
        "Responden",
        "R1","R2","R3","R4",      # Keterbacaan (Readability)
        "ES1","ES2","ES3","ES4",  # Kelelahan Mata (Eye Strain)
        "U1","U2","U3","U4",      # Usability
        "B1","B2","B3","B4",      # Konsumsi Baterai (Battery)
        "E1","E2","E3","E4",      # Efisien Kinerja (Efficiency)
        "ED1","ED2","ED3","ED4"   # Estetika & Daya Tarik (Aesthetic)
    ]

    # File data per aplikasi
    file_pos = os.path.join(USER_DIR, f"preferensi_positif_{app}.csv")
    file_neg = os.path.join(USER_DIR, f"preferensi_negatif_{app}.csv")

    # --- TAB SISTEM ---
    tab_input, tab_analisis = st.tabs(["Input Data Kuesioner", "Hasil Analisis dan Narasi"])

    with tab_input:

        with st.expander("Dataset Manager - Preferensi Positif", expanded=False):
            df_manager_pos = load_pref("data_pref_pos", current_user, app, n)
            dataset_manager(
                df_manager_pos,
                columns_pref,
                file_pos,
                "Dataset Preferensi Positif",
                f"preferensi_positif_{app}"
            )

        with st.expander("Dataset Manager - Preferensi Negatif", expanded=False):
            df_manager_neg = load_pref("data_pref_neg", current_user, app, n)
            dataset_manager(
                df_manager_neg,
                columns_pref,
                file_neg,
                "Dataset Preferensi Negatif",
                f"preferensi_negatif_{app}"
            )

        st.markdown("---")

        st.markdown("### 1. Pernyataan Positif")
        st.caption("Skala 1 (Light) ke 7 (Dark)")
        df_pos = load_pref("data_pref_pos", current_user, app, n)
        df_pos = adjust_dataframe(df_pos, n)

        df_pos_edit = st.data_editor(df_pos, key="pos_editor_final", use_container_width=True)

        st.markdown("---")

        st.markdown("### 2. Pernyataan Negatif")
        st.caption("Skala 1 (Light) ke 7 (Dark)")
        df_neg = load_pref("data_pref_neg", current_user, app, n)
        df_neg = adjust_dataframe(df_neg, n)
        df_neg_edit = st.data_editor(df_neg, key="neg_editor_final", use_container_width=True)

        st.markdown("---")

        # Tombol simpan
        if st.button("Simpan Semua Data Preferensi", type="primary", use_container_width=True):
            save_pref("data_pref_pos", current_user, app, df_pos_edit)
            save_pref("data_pref_neg", current_user, app, df_neg_edit)
            st.session_state["saved_pref"] = True
            st.rerun()

        if st.session_state.get("saved_pref"):
            st.success("Data Preferensi berhasil disimpan!")
            st.session_state["saved_pref"] = False

        # Tombol hapus sejajar (layout seperti UEQ)
        col_del_pos, col_del_neg = st.columns(2)
        with col_del_pos:
            render_delete_button(
                file_path=file_pos,
                label="Preferensi Positif",
                columns=columns_pref[1:],
                default_value=0,
                key_suffix="pref_pos"
            )
        with col_del_neg:
            render_delete_button(
                file_path=file_neg,
                label="Preferensi Negatif",
                columns=columns_pref[1:],
                default_value=0,
                key_suffix="pref_neg"
            )

        

    # --- LOGIKA ANALISIS ---
    # --- LOGIKA ANALISIS ---
    with tab_analisis:

        # ======================
        # CEK DATA DULU SEBELUM ANALISIS
        # ======================

        cols_data_pref = columns_pref[1:]  # skip kolom Responden
        def _cek_supabase(table):
            try:
                df_check = load_pref(table, current_user, app, n)
                cols_only = [c for c in cols_data_pref if c != "Responden"]
                total = df_check[cols_only].apply(pd.to_numeric, errors="coerce").sum().sum()
                return total > 0
            except Exception:
                return False

        pos_terisi = _cek_supabase("data_pref_pos")
        neg_terisi = _cek_supabase("data_pref_neg")

        # ======================
        # TAMPILKAN STATUS DATA
        # ======================
        st.markdown("### Status Data")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if pos_terisi:
                st.success("Data Preferensi Positif sudah terisi.")
            else:
                st.warning("Data Preferensi Positif belum diisi.")
        with col_s2:
            if neg_terisi:
                st.success("Data Preferensi Negatif sudah terisi.")
            else:
                st.warning("Data Preferensi Negatif belum diisi.")

        # ======================
        # BLOKIR ANALISIS JIKA DATA BELUM LENGKAP
        # ======================
        if not pos_terisi or not neg_terisi:
            st.markdown("---")
            st.info("""
            Analisis belum dapat ditampilkan karena data belum lengkap.
            
            Langkah yang perlu dilakukan:
            1. Buka tab **Input Data Kuesioner**
            2. Isi data pada tabel **Pernyataan Positif**
            3. Isi data pada tabel **Pernyataan Negatif**
            4. Klik tombol **Simpan** pada masing-masing bagian
            5. Kembali ke tab ini untuk melihat hasil analisis
            """)
            st.stop()

        # ======================
        # TOMBOL REFRESH (hanya tampil jika data sudah ada)
        # ======================
        if st.button("Refresh Analisis", use_container_width=True):
            st.rerun()

        aspek_map = {
            "Keterbacaan (Readability)": ["R1","R2","R3","R4"],
            "Kelelahan Mata (Eye Strain)": ["ES1","ES2","ES3","ES4"],
            "Usability": ["U1","U2","U3","U4"],
            "Konsumsi Baterai": ["B1","B2","B3","B4"],
            "Efisien Kinerja": ["E1","E2","E3","E4"],
            "Estetika & Daya Tarik": ["ED1","ED2","ED3","ED4"]
        }

        final_data = []
        
        for name, cols in aspek_map.items():
            m_pos = df_pos_edit[cols].apply(pd.to_numeric, errors='coerce').mean().mean()
            m_neg_raw = df_neg_edit[cols].apply(pd.to_numeric, errors='coerce').mean().mean()
            m_neg_rev = 8 - m_neg_raw
            grand_mean = (m_pos + m_neg_rev) / 2
            
            if pd.isna(grand_mean):
                kecenderungan = "Data Kosong"
                color_code = "#94a3b8"
            elif grand_mean < 4:
                kecenderungan = "Light Mode"
                color_code = "#6366f1"
            elif grand_mean > 4:
                kecenderungan = "Dark Mode"
                color_code = "#a78bfa"
            else:
                kecenderungan = "Netral"
                color_code = "#10b981"

            final_data.append({
                "Aspek Pengalaman": name,
                "Mean Positif": round(m_pos, 3),
                "Mean Negatif (Raw)": round(m_neg_raw, 3),
                "Grand Mean": round(grand_mean, 3),
                "Preferensi": kecenderungan,
                "Color": color_code
            })

        res_df = pd.DataFrame(final_data)

        # 1. Tabel Rekapitulasi
        st.markdown("### Tabel Rekapitulasi Preferensi")
        st.table(res_df[["Aspek Pengalaman", "Mean Positif", "Mean Negatif (Raw)", "Grand Mean", "Preferensi"]])

        # 2. Grafik Batang
        st.markdown("### Grafik Kecenderungan Per Aspek")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=res_df["Aspek Pengalaman"],
            y=res_df["Grand Mean"],
            marker_color=res_df["Color"],
            text=res_df["Grand Mean"],
            textposition='auto',
        ))
        fig.add_hline(y=4, line_dash="dash", line_color="red", annotation_text="Titik Netral (4.0)")
        fig.update_layout(yaxis=dict(range=[1, 7], title="Skor Preferensi"), height=450)
        st.plotly_chart(fig, use_container_width=True)

        # 3. Narasi Hasil Detail
        st.markdown("### Analisis Detail Hasil")
        l_aspek = res_df[res_df["Preferensi"] == "Light Mode"]["Aspek Pengalaman"].tolist()
        d_aspek = res_df[res_df["Preferensi"] == "Dark Mode"]["Aspek Pengalaman"].tolist()
        
        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div class="unggul-light-card">
                <b class="unggul-light-title">Unggul Light Mode</b><br>
                <p style="font-size:13px; margin-top:8px;">{", ".join(l_aspek) if l_aspek else "Tidak ada"}</p>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="unggul-dark-card">
                <b class="unggul-dark-title">Unggul Dark Mode</b><br>
                <p style="font-size:13px; margin-top:8px;">{", ".join(d_aspek) if d_aspek else "Tidak ada"}</p>
            </div>
            """, unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom:16px;'></div>", unsafe_allow_html=True)

        aspek_max = res_df.loc[res_df["Grand Mean"].idxmax()]
        aspek_min = res_df.loc[res_df["Grand Mean"].idxmin()]
        
        st.success(f"""
        Kesimpulan Akhir Preferensi:
        - Preferensi Dark Mode terkuat ada pada aspek {aspek_max['Aspek Pengalaman']} (Skor: {aspek_max['Grand Mean']}).
        - Preferensi Light Mode terkuat ada pada aspek {aspek_min['Aspek Pengalaman']} (Skor: {aspek_min['Grand Mean']}).
        - Secara keseluruhan, aplikasi {app} lebih cenderung optimal menggunakan {'Light Mode' if len(l_aspek) > len(d_aspek) else 'Dark Mode'} berdasarkan dominasi jumlah aspek.
        """)
       
if menu == "Settings":
    render_settings_page()