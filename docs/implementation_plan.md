# Implementation Plan

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Phase 0 — Scaffolding
- [x] Project layout (`config/`, `data/`, `src/smart_building/`, `app/`, `notebooks/`, `tests/`)
- [x] `pyproject.toml` with dependencies (pyomo, highspy, pandas, pydantic, pvlib, tsam, streamlit, plotly, ...)
- [x] `.gitignore`
- [x] `README.md`
- [x] `docs/stack.md` — stack & modeling design
- [x] `docs/implementation_plan.md` — this file
- [x] Python package skeleton (`src/smart_building/__init__.py`, `data_sources/__init__.py`)
- [x] Virtual environment + install deps; verify Pyomo can call HiGHS on a trivial LP
- [x] `git init` + initial commit

## Phase 1 — Data & config
- [~] Pydantic config schema (`config.py`): battery (20 kWh, 10 kW, ~88% eff),
      EV charging, export tariff (0.14 CHF/kWh)
- [~] Example house config (`config/house_default.yaml`)
- [~] Data loader (`data_loader.py`): load `energy_balance_separated.csv` +
      `ev_sessions.csv`, clean DST markers, coerce types, handle NaNs

Data comes from FusionSolar (Huawei) measured data at 5-min resolution,
2026-01-01 to 2026-06-18. Columns: PV generation, total/base/EV consumption,
battery charge/discharge, variable electricity tariffs (CHF/kWh).

## Phase 2 — Core optimization model (Pyomo)
- [~] Pyomo LP model: optimize battery charge/discharge over full 6-month
      period at 5-min resolution to minimize electricity cost under variable
      import pricing (integrated tariff) and fixed export tariff (0.14 CHF/kWh)
- [ ] Optional EV charging optimization: shift charging within session windows
      (same total energy by departure, flexible timing/power profile)
- [ ] Solve with HiGHS, extract results to tidy DataFrame
- [ ] Sanity-check: battery SOC stays within bounds, energy balance holds

## Phase 3 — Baseline & comparison
- [~] Compute baseline cost from actual FusionSolar dispatch
      (measured chargePower/dischargePower → grid import/export → cost)
- [ ] Compare optimized vs baseline: total cost, savings, self-consumption rate

## Phase 4 — Scenarios & KPIs
- [ ] Scenario matrix: with/without battery optimization, with/without EV
      optimization, flat vs variable tariff
- [ ] KPIs: total cost, savings %, self-consumption rate, self-sufficiency rate,
      peak grid import
- [ ] Persist scenario results (parquet)

## Phase 5 — Streamlit dashboard
- [ ] Overview page: config + input time series profiles
- [ ] Daily detail page: stacked-area energy flows + Sankey "real-time flow"
      diagram with time slider
- [ ] Scenario comparison page: KPI table + bar charts

## Phase 6 — Extensions (optional)
- [ ] Heat pump / thermal storage optimization
- [ ] Representative days (tsam) for full-year scaling
- [ ] Battery degradation cost term
- [ ] Demand/peak-power charges
- [ ] Sensitivity sweeps on system sizing
