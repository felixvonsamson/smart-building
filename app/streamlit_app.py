import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from smart_building.baseline import compute_baseline_cost
from smart_building.config import load_config
from smart_building.data_loader import compute_grid_flows, load_energy_data, load_ev_sessions
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
    price_import = df[import_col].values
    pe = df[export_price].values if isinstance(export_price, str) else export_price

    baseline_kpis = compute_baseline_cost(df, price_import, pe, _cfg.timestep_minutes)

    m = build_model(df, _cfg, _ev, price_import=price_import, price_export=pe)
    solve_model(m)
    opt = extract_results(m, df, price_import, pe)
    return opt, baseline_kpis


def build_baseline_df(df, price_import, price_export):
    df_grid = compute_grid_flows(df)
    out = pd.DataFrame(index=df.index)
    out["pv_kw"] = df["productPower"].values
    out["base_demand_kw"] = df["base_power"].values
    out["ev_charge_kw"] = df["ev_power"].values
    out["batt_charge_kw"] = df["chargePower"].values
    out["batt_discharge_kw"] = df["dischargePower"].values
    out["grid_import_kw"] = df_grid["grid_import_kw"].values
    out["grid_export_kw"] = df_grid["grid_export_kw"].values
    out["price_import"] = price_import
    if np.isscalar(price_export):
        out["price_export"] = price_export
    else:
        out["price_export"] = price_export
    out["soc_kwh"] = np.nan
    return out


def make_power_chart(view, show_soc=True):
    has_soc = show_soc and view["soc_kwh"].notna().any()
    n_rows = 3 if has_soc else 2
    heights = [0.55, 0.25, 0.20] if has_soc else [0.65, 0.35]
    titles = ["Power flows (kW)", "Battery SOC (kWh)", "Electricity price (CHF/kWh)"] if has_soc else ["Power flows (kW)", "Electricity price (CHF/kWh)"]

    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        vertical_spacing=0.06, row_heights=heights, subplot_titles=titles,
    )

    traces = [
        ("PV", view["pv_kw"], "rgba(255,193,7,0.6)"),
        ("Grid import", view["grid_import_kw"], "rgba(244,67,54,0.4)"),
        ("Battery discharge", view["batt_discharge_kw"], "rgba(76,175,80,0.5)"),
    ]
    for name, y, color in traces:
        fig.add_trace(go.Scatter(x=view.index, y=y, name=name, fill="tozeroy", line=dict(width=0), fillcolor=color), row=1, col=1)

    sinks = [
        ("Base demand", -view["base_demand_kw"], "rgba(33,150,243,0.4)"),
        ("EV charging", -view["ev_charge_kw"], "rgba(156,39,176,0.5)"),
        ("Grid export", -view["grid_export_kw"], "rgba(255,87,34,0.4)"),
        ("Battery charge", -view["batt_charge_kw"], "rgba(0,150,136,0.5)"),
    ]
    for name, y, color in sinks:
        fig.add_trace(go.Scatter(x=view.index, y=y, name=name, fill="tozeroy", line=dict(width=0), fillcolor=color), row=1, col=1)

    if has_soc:
        fig.add_trace(go.Scatter(x=view.index, y=view["soc_kwh"], name="SOC", line=dict(color="#4CAF50", width=2)), row=2, col=1)
        fig.add_hline(y=cfg.battery.soc_max_kwh, line_dash="dot", line_color="gray", row=2, col=1)
        fig.add_hline(y=cfg.battery.soc_min_kwh, line_dash="dot", line_color="gray", row=2, col=1)

    price_row = 3 if has_soc else 2
    fig.add_trace(go.Scatter(x=view.index, y=view["price_import"], name="Import price", line=dict(color="#F44336", width=1.5)), row=price_row, col=1)
    fig.add_trace(go.Scatter(x=view.index, y=view["price_export"], name="Export price", line=dict(color="#FF9800", width=1.5)), row=price_row, col=1)

    fig.update_layout(
        height=800, hovermode="x unified", margin=dict(t=60, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )
    fig.update_yaxes(title_text="kW", row=1, col=1)
    if has_soc:
        fig.update_yaxes(title_text="kWh", row=2, col=1)
    fig.update_yaxes(title_text="CHF/kWh", row=price_row, col=1)
    return fig


def daily_cost(view, dt_h):
    import_cost = (view["price_import"] * view["grid_import_kw"] * dt_h).resample("D").sum()
    export_rev = (view["price_export"] * view["grid_export_kw"] * dt_h).resample("D").sum()
    return import_cost - export_rev


# ── Load data ──
df_full, ev_full, cfg = load_data()
dt = cfg.timestep_minutes / 60

# ── Sidebar ──
st.sidebar.title("Settings")

scenario = st.sidebar.radio("Tariff scenario", ["Variable tariff", "Dual tariff"])

q1_only = st.sidebar.checkbox("Q1 only (Jan-Mar)", value=True)
if q1_only:
    df = df_full[df_full.index < "2026-04-01"].copy()
    ev = ev_full[ev_full["departure"] < "2026-04-01"].copy()
else:
    df = df_full.copy()
    ev = ev_full.copy()

display_mode = st.sidebar.radio("Display", ["Optimized", "Baseline", "Both (tabs)"])

min_date = df.index.min().date()
max_date = df.index.max().date()
date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, min(min_date + timedelta(days=6), max_date)),
    min_value=min_date, max_value=max_date,
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date = date_range[0] if isinstance(date_range, tuple) else date_range
    end_date = start_date + timedelta(days=6)

# ── Tariff setup ──
if scenario == "Variable tariff":
    import_col = "integrated_tariff_CHF_kWh"
    export_price = "grid_tariff_CHF_kWh"
    export_label = "grid market price"
else:
    import_col = "dual_tariff_CHF_kWh"
    export_price = 0.11
    export_label = "0.11 CHF/kWh"

price_import_arr = df[import_col].values
price_export_arr = df[export_price].values if isinstance(export_price, str) else np.full(len(df), export_price)

# ── Run optimization ──
with st.spinner(f"Running optimization ({scenario})..."):
    opt, baseline_kpis = run_optimization(df, ev, cfg, import_col, export_price, scenario)

baseline_df = build_baseline_df(df, price_import_arr, price_export_arr)

# ── KPIs ──
opt_import_cost = (opt["price_import"] * opt["grid_import_kw"] * dt).sum()
opt_export_rev = (opt["price_export"] * opt["grid_export_kw"] * dt).sum()
opt_net = opt_import_cost - opt_export_rev
savings = baseline_kpis["net_cost_chf"] - opt_net
savings_pct = savings / baseline_kpis["net_cost_chf"] * 100 if baseline_kpis["net_cost_chf"] else 0

st.title("Smart Building Energy Optimization")
st.markdown(f"**{scenario}** — import: `{import_col}`, export: {export_label}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Baseline cost", f"{baseline_kpis['net_cost_chf']:.0f} CHF")
col2.metric("Optimized cost", f"{opt_net:.0f} CHF")
col3.metric("Savings", f"{savings:.0f} CHF", f"{savings_pct:.1f}%")
total_pv = (opt["pv_kw"] * dt).sum()
pv_self = total_pv - (opt["grid_export_kw"] * dt).sum()
col4.metric("Self-consumption", f"{pv_self / total_pv:.1%}")

# ── Filter to date range ──
date_mask = lambda idx: (idx.date >= start_date) & (idx.date <= end_date)
opt_view = opt.loc[date_mask(opt.index)]
base_view = baseline_df.loc[date_mask(baseline_df.index)]

if len(opt_view) == 0:
    st.warning("No data in selected range.")
    st.stop()

# ── Charts ──
if display_mode == "Optimized":
    st.plotly_chart(make_power_chart(opt_view), use_container_width=True)
elif display_mode == "Baseline":
    st.plotly_chart(make_power_chart(base_view, show_soc=True), use_container_width=True)
else:
    tab_opt, tab_base = st.tabs(["Optimized", "Baseline"])
    with tab_opt:
        st.plotly_chart(make_power_chart(opt_view), use_container_width=True)
    with tab_base:
        st.plotly_chart(make_power_chart(base_view, show_soc=True), use_container_width=True)

# ── Daily summary table ──
st.subheader("Daily summary")

opt_daily_cost = daily_cost(opt_view, dt)
base_daily_cost = daily_cost(base_view, dt)

daily_table = pd.DataFrame({
    "PV (kWh)": opt_view["pv_kw"].resample("D").sum() * dt,
    "Base demand (kWh)": opt_view["base_demand_kw"].resample("D").sum() * dt,
    "EV (kWh)": opt_view["ev_charge_kw"].resample("D").sum() * dt,
    "Grid import (kWh)": opt_view["grid_import_kw"].resample("D").sum() * dt,
    "Grid export (kWh)": opt_view["grid_export_kw"].resample("D").sum() * dt,
    "Batt charge (kWh)": opt_view["batt_charge_kw"].resample("D").sum() * dt,
    "Batt discharge (kWh)": opt_view["batt_discharge_kw"].resample("D").sum() * dt,
    "Baseline cost (CHF)": base_daily_cost,
    "Optimized cost (CHF)": opt_daily_cost,
    "Savings (CHF)": base_daily_cost - opt_daily_cost,
})
daily_table.index = daily_table.index.date
daily_table.index.name = "Date"

st.dataframe(daily_table.round(2), use_container_width=True)
