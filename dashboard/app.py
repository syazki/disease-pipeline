import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from pipeline.db import get_connection

st.set_page_config(
    page_title="CANWatch",
    page_icon="🦠",
    layout="wide"
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }
    .header-bar {
        background: linear-gradient(135deg, #1B3A6B 0%, #2D6A9F 100%);
        padding: 1.2rem 1.8rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    .header-title { color: white; font-size: 1.5rem; font-weight: 700; margin: 0; }
    .header-sub { color: rgba(255,255,255,0.7); font-size: 0.8rem; margin: 0; }
    .metric-card {
        border-radius: 12px;
        padding: 1.2rem 1.4rem;
        color: white;
        height: 100%;
    }
    .metric-label { font-size: 0.75rem; opacity: 0.85; margin-bottom: 0.3rem; font-weight: 500; letter-spacing: 0.03em; }
    .metric-value { font-size: 2rem; font-weight: 700; line-height: 1; margin-bottom: 0.2rem; }
    .metric-delta { font-size: 0.75rem; opacity: 0.85; }
    .section-title { font-size: 1rem; font-weight: 600; color: #1B3A6B; margin-bottom: 0.5rem; }
    .chart-container {
        background: white;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #f0f0f0;
    }
    div[data-testid="stHorizontalBlock"] { gap: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ── header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-bar">
    <div>
        <p class="header-title">🦠 CANWatch</p>
        <p class="header-sub">Canadian Notifiable Disease Surveillance Pipeline · PHAC/CNDSS 1991–2023</p>
    </div>
    <div style="color:rgba(255,255,255,0.6);font-size:0.75rem;text-align:right">
        Live pipeline · Last ingested today<br>
        Data: PHAC · ERA5 · Statistics Canada
    </div>
</div>
""", unsafe_allow_html=True)

# ── disease selectors ─────────────────────────────────────────────────────
conn = get_connection()
diseases = pd.read_sql(
    "SELECT DISTINCT disease FROM silver_disease_cases ORDER BY disease", conn
)["disease"].tolist()
conn.close()

col1, col2, _ = st.columns([1, 1, 2])
with col1:
    disease_a = st.selectbox("Disease A", diseases,
        index=diseases.index("Hantavirus Pulmonary Syndrome") if "Hantavirus Pulmonary Syndrome" in diseases else 0)
with col2:
    disease_b = st.selectbox("Disease B", diseases,
        index=diseases.index("Lyme Disease") if "Lyme Disease" in diseases else 1)

st.markdown("<br>", unsafe_allow_html=True)

# ── load data ─────────────────────────────────────────────────────────────
conn = get_connection()

def load_trend(d):
    return pd.read_sql("SELECT year, cases, rolling_avg_5yr, yoy_change FROM gold_disease_trend WHERE disease = %s ORDER BY year", conn, params=(d,))

def load_anomaly(d):
    return pd.read_sql("SELECT year, cases, rolling_avg_5yr, is_anomaly FROM gold_anomaly_flag WHERE disease = %s ORDER BY year", conn, params=(d,))

def load_climate(d):
    return pd.read_sql("SELECT year, cases, temperature_anomaly FROM gold_climate_correlation WHERE disease = %s ORDER BY year", conn, params=(d,))

df_a = load_trend(disease_a)
df_b = load_trend(disease_b)
anom_a = load_anomaly(disease_a)
anom_b = load_anomaly(disease_b)
clim_a = load_climate(disease_a)
clim_b = load_climate(disease_b)
conn.close()

# ── correlation scores ────────────────────────────────────────────────────
def correlation(df):
    clean = df.dropna(subset=["cases", "temperature_anomaly"])
    if len(clean) < 3:
        return None
    r, _ = stats.pearsonr(clean["temperature_anomaly"], clean["cases"])
    return round(r, 2)

corr_a = correlation(clim_a)
corr_b = correlation(clim_b)

# ── metric cards ──────────────────────────────────────────────────────────
def safe_delta(df):
    val = df.iloc[-1]["yoy_change"]
    return int(val) if pd.notna(val) else 0

c1, c2, c3, c4, c5, c6 = st.columns(6)

cards = [
    (c1, f"[A] Cases 2023", int(df_a.iloc[-1]["cases"]), f"{'↑' if safe_delta(df_a) > 0 else '↓'} {abs(safe_delta(df_a))} vs 2022", "#1B3A6B"),
    (c2, f"[A] 5-yr avg", float(df_a.iloc[-1]["rolling_avg_5yr"]), "rolling baseline", "#2D6A9F"),
    (c3, f"[A] Climate r", corr_a if corr_a else "N/A", "temp correlation", "#2196A6"),
    (c4, f"[B] Cases 2023", int(df_b.iloc[-1]["cases"]), f"{'↑' if safe_delta(df_b) > 0 else '↓'} {abs(safe_delta(df_b))} vs 2022", "#B5390A"),
    (c5, f"[B] 5-yr avg", float(df_b.iloc[-1]["rolling_avg_5yr"]), "rolling baseline", "#D4501A"),
    (c6, f"[B] Climate r", corr_b if corr_b else "N/A", "temp correlation", "#E07B3A"),
]

for col, label, value, delta, color in cards:
    with col:
        st.markdown(f"""
        <div class="metric-card" style="background:{color}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-delta">{delta}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── chart 1: case trend ───────────────────────────────────────────────────
st.markdown('<p class="section-title">Case trend comparison</p>', unsafe_allow_html=True)

fig1 = go.Figure()
fig1.add_trace(go.Scatter(x=df_a["year"], y=df_a["cases"], mode="lines+markers",
    name=disease_a, line=dict(color="#1B3A6B", width=2.5), marker=dict(size=5)))
fig1.add_trace(go.Scatter(x=df_a["year"], y=df_a["rolling_avg_5yr"], mode="lines",
    name=f"{disease_a} — 5yr avg", line=dict(color="#1B3A6B", width=1.5, dash="dot")))
fig1.add_trace(go.Scatter(x=df_b["year"], y=df_b["cases"], mode="lines+markers",
    name=disease_b, line=dict(color="#B5390A", width=2.5), marker=dict(size=5)))
fig1.add_trace(go.Scatter(x=df_b["year"], y=df_b["rolling_avg_5yr"], mode="lines",
    name=f"{disease_b} — 5yr avg", line=dict(color="#B5390A", width=1.5, dash="dot")))
fig1.update_layout(
    plot_bgcolor="white", paper_bgcolor="white", height=350,
    xaxis=dict(showgrid=False, title="Year"),
    yaxis=dict(showgrid=True, gridcolor="#f5f5f5", title="Reported cases"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(t=40, b=40, l=40, r=20)
)
st.plotly_chart(fig1, use_container_width=True)

# ── chart 2 + 3: anomaly side by side ────────────────────────────────────
st.markdown('<p class="section-title">Anomaly detection — years exceeding 2× rolling average</p>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

def anomaly_chart(df, disease, base_color):
    df = df.copy()
    df["status"] = df["is_anomaly"].map({True: "Anomaly", False: "Normal"})
    fig = px.bar(df, x="year", y="cases", color="status",
        color_discrete_map={"Anomaly": "#E24B4A", "Normal": base_color},
        labels={"cases": "Cases", "year": "Year"}, title=disease)
    fig.update_layout(
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False,
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor="#f5f5f5"),
        margin=dict(t=40, b=40, l=40, r=20), height=280
    )
    return fig

with col1:
    st.plotly_chart(anomaly_chart(anom_a, disease_a, "#1B3A6B"), use_container_width=True)
with col2:
    st.plotly_chart(anomaly_chart(anom_b, disease_b, "#B5390A"), use_container_width=True)

# ── chart 4: climate correlation ─────────────────────────────────────────
st.markdown('<p class="section-title">Cases vs temperature anomaly (°C)</p>', unsafe_allow_html=True)
st.caption("Each dot is one year. Does a warmer year mean more cases?")

fig3 = go.Figure()
fig3.add_trace(go.Scatter(x=clim_a["temperature_anomaly"], y=clim_a["cases"],
    mode="markers+text", name=disease_a, text=clim_a["year"], textposition="top center",
    marker=dict(color="#1B3A6B", size=8)))
fig3.add_trace(go.Scatter(x=clim_b["temperature_anomaly"], y=clim_b["cases"],
    mode="markers+text", name=disease_b, text=clim_b["year"], textposition="top center",
    marker=dict(color="#B5390A", size=8)))
fig3.update_layout(
    plot_bgcolor="white", paper_bgcolor="white", height=350,
    xaxis=dict(showgrid=True, gridcolor="#f5f5f5", title="Temperature anomaly (°C)"),
    yaxis=dict(showgrid=True, gridcolor="#f5f5f5", title="Reported cases"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(t=40, b=40, l=40, r=20)
)
st.plotly_chart(fig3, use_container_width=True)

# ── download button ───────────────────────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns(2)
with col1:
    csv_a = df_a.copy()
    csv_a["disease"] = disease_a
    st.download_button(f"⬇ Download {disease_a} data", csv_a.to_csv(index=False),
        file_name=f"{disease_a.replace(' ', '_')}.csv", mime="text/csv")
with col2:
    csv_b = df_b.copy()
    csv_b["disease"] = disease_b
    st.download_button(f"⬇ Download {disease_b} data", csv_b.to_csv(index=False),
        file_name=f"{disease_b.replace(' ', '_')}.csv", mime="text/csv")

st.caption("Data: PHAC / CNDSS (1991–2023) · Our World in Data / ERA5 · Statistics Canada")

st.markdown("---")
st.markdown("View my GitHub: [Salma Yazki](https://github.com/syazki) · [Source code](https://github.com/syazki/disease-pipeline)")

if disease_a == "Hantavirus Pulmonary Syndrome" or disease_b == "Hantavirus Pulmonary Syndrome":
    st.warning("⚠️ Active outbreak — WHO confirmed Andes virus on MV Hondius cruise ship, May 2026. Data above reflects historical Canadian domestic cases only.")