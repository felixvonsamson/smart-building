import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from smart_building.baseline import compute_baseline_cost
from smart_building.config import load_config
from smart_building.data_loader import load_energy_data, load_ev_sessions
from smart_building.model import build_model, extract_results, solve_model

st.set_page_config(page_title="Smart Building Energy", layout="wide")


@st.cache_data
def load_data():
    cfg = load_config(Path("config/house_default.yaml"))
    df = load_energy_data(cfg)
    ev = load_ev_sessions(cfg)
    return df, ev, cfg


@st.cache_data
def run_optimization(_df, _ev, _cfg, import_col, export_price, label):
    df = _df.copy()
    cfg = _cfg
    price_import = df[import_col].values
    if isinstance(export_price, str):
        pe = df[export_price].values
    else:
        pe = export_price

    baseline = compute_baseline_cost(df, price_import, pe, cfg.timestep_minutes)

    m = build_model(df, cfg, _ev, price_import=price_import, price_export=pe)
    solve_model(m)
    res = extract_results(m, df, price_import, pe)
    return res, baseline


df_full, ev_full, cfg = load_data()

# --- Sidebar ---
st.sidebar.title("Settings")

scenario = st.sidebar.radio(
    "Tariff scenario",
    ["Variable tariff", "Dual tariff"],
)

q1_only = st.sidebar.checkbox("Q1 only (Jan-Mar)", value=True)

if q1_only:
    df = df_full[df_full.index < "2026-04-01"].copy()
    ev = ev_full[ev_full["departure"] < "2026-04-01"].copy()
else:
    df = df_full.copy()
    ev = ev_full.copy()

min_date = df.index.min().date()
max_date = df.index.max().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, min(min_date + timedelta(days=6), max_date)),
    min_value=min_date,
    max_value=max_date,
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0] if isinstance(date_range, tuple) else date_range
    end_date = start_date + timedelta(days=6)

# --- Run optimization ---
if scenario == "Variable tariff":
    import_col = "integrated_tariff_CHF_kWh"
    export_price = "grid_tariff_CHF_kWh"
    export_label = "grid market price"
else:
    import_col = "dual_tariff_CHF_kWh"
    export_price = 0.11
    export_label = "0.11 CHF/kWh"

with st.spinner(f"Running optimization ({scenario})..."):
    res, baseline = run_optimization(df, ev, cfg, import_col, export_price, scenario)

# --- KPIs ---
dt = cfg.timestep_minutes / 60
opt_import_cost = (res["price_import"] * res["grid_import_kw"] * dt).sum()
opt_export_rev = (res["price_export"] * res["grid_export_kw"] * dt).sum()
opt_net = opt_import_cost - opt_export_rev
savings = baseline["net_cost_chf"] - opt_net
savings_pct = savings / baseline["net_cost_chf"] * 100 if baseline["net_cost_chf"] else 0

st.title("Smart Building Energy Optimization")
st.markdown(f"**{scenario}** — import: `{import_col}`, export: {export_label}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Baseline cost", f"{baseline['net_cost_chf']:.0f} CHF")
col2.metric("Optimized cost", f"{opt_net:.0f} CHF")
col3.metric("Savings", f"{savings:.0f} CHF", f"{savings_pct:.1f}%")
total_pv = (res["pv_kw"] * dt).sum()
pv_self = total_pv - (res["grid_export_kw"] * dt).sum()
col4.metric("Self-consumption", f"{pv_self / total_pv:.1%}")

# --- Filter to selected date range ---
mask = (res.index.date >= start_date) & (res.index.date <= end_date)
view = res.loc[mask]

if len(view) == 0:
    st.warning("No data in selected range.")
    st.stop()

# --- Power flows chart ---
fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.06,
    row_heights=[0.55, 0.25, 0.20],
    subplot_titles=("Power flows (kW)", "Battery SOC (kWh)", "Electricity price (CHF/kWh)"),
)

# Sources (positive)
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["pv_kw"], name="PV",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(255,193,7,0.6)",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["grid_import_kw"], name="Grid import",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(244,67,54,0.4)",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["batt_discharge_kw"], name="Battery discharge",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(76,175,80,0.5)",
    ),
    row=1, col=1,
)

# Sinks (negative)
fig.add_trace(
    go.Scatter(
        x=view.index, y=-view["base_demand_kw"], name="Base demand",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(33,150,243,0.4)",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=-view["ev_charge_kw"], name="EV charging",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(156,39,176,0.5)",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=-view["grid_export_kw"], name="Grid export",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(255,87,34,0.4)",
    ),
    row=1, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=-view["batt_charge_kw"], name="Battery charge",
        fill="tozeroy", line=dict(width=0), fillcolor="rgba(0,150,136,0.5)",
    ),
    row=1, col=1,
)

# SOC
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["soc_kwh"], name="SOC",
        line=dict(color="#4CAF50", width=2), showlegend=True,
    ),
    row=2, col=1,
)
fig.add_hline(y=cfg.battery.soc_max_kwh, line_dash="dot", line_color="gray", row=2, col=1)
fig.add_hline(y=cfg.battery.soc_min_kwh, line_dash="dot", line_color="gray", row=2, col=1)

# Price
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["price_import"], name="Import price",
        line=dict(color="#F44336", width=1.5),
    ),
    row=3, col=1,
)
fig.add_trace(
    go.Scatter(
        x=view.index, y=view["price_export"], name="Export price",
        line=dict(color="#FF9800", width=1.5),
    ),
    row=3, col=1,
)

fig.update_layout(
    height=800,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    margin=dict(t=60, b=30),
    hovermode="x unified",
)
fig.update_yaxes(title_text="kW", row=1, col=1)
fig.update_yaxes(title_text="kWh", row=2, col=1)
fig.update_yaxes(title_text="CHF/kWh", row=3, col=1)

st.plotly_chart(fig, use_container_width=True)

# --- Daily breakdown table ---
st.subheader("Daily summary")
daily = view.resample("D").apply(lambda x: (x * dt).sum() if x.name != "soc_kwh" else x.mean())
daily_table = pd.DataFrame({
    "PV (kWh)": view["pv_kw"].resample("D").sum() * dt,
    "Base demand (kWh)": view["base_demand_kw"].resample("D").sum() * dt,
    "EV (kWh)": view["ev_charge_kw"].resample("D").sum() * dt,
    "Grid import (kWh)": view["grid_import_kw"].resample("D").sum() * dt,
    "Grid export (kWh)": view["grid_export_kw"].resample("D").sum() * dt,
    "Batt charge (kWh)": view["batt_charge_kw"].resample("D").sum() * dt,
    "Batt discharge (kWh)": view["batt_discharge_kw"].resample("D").sum() * dt,
})
daily_table.index = daily_table.index.date
st.dataframe(daily_table.round(2), use_container_width=True)
