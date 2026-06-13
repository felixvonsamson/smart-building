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

## Phase 1 — Inputs & data ingestion
- [ ] Pydantic config schema (`config.py`): PV, battery, EV, tank, heat pump,
      annual demand targets, location, price zone
- [ ] Example house config (`config/house_default.yaml`)
- [ ] PV generation profile via `pvlib.iotools.get_pvgis_hourly` (per-kWp,
      scaled by installed capacity), plus ambient temperature series
- [ ] Electricity price series from Open Power System Data (day-ahead, by
      bidding zone)
- [ ] Synthetic electricity demand profile (standard load profile, scaled to
      annual consumption)
- [ ] Heating/DHW demand model (heating-degree based + stylized DHW profile,
      scaled to annual heat demand)
- [ ] Assemble aligned full-year hourly DataFrame (demand, heat demand, PV/kWp,
      T_amb, price import/export)
- [ ] Notebook: sanity-check annual sums and profile shapes

## Phase 2 — Representative days (tsam)
- [ ] Cluster full-year DataFrame into ~8-12 typical days with weights
- [ ] Validate against duration curves of original series
- [ ] Persist representative days to `data/processed/`

## Phase 3 — Core optimization model (Pyomo)
- [ ] COP(t) curve from ambient temperature
- [ ] Tank energy capacity/bounds from volume + temperature range
- [ ] Pyomo model: sets, parameters, variables, constraints (electrical
      balance, thermal balance, battery/EV/tank dynamics + cyclic SOC, EV
      availability, HP capacity, grid limits)
- [ ] Objective: weighted annual cost across representative days
- [ ] Solve with HiGHS, extract results to tidy DataFrame
- [ ] Toy validation case (e.g. battery-only price arbitrage)

## Phase 4 — Baseline rule-based controller
- [ ] Greedy self-consumption + thermostatic HP + immediate EV charging
- [ ] Produces baseline cost per representative day for savings comparison

## Phase 5 — Scenarios & KPIs
- [ ] Scenario matrix: tariff type x assets present x control strategy
- [ ] Batch runner across representative days, scale to annual via weights
- [ ] KPIs: annual cost, savings %, self-consumption/self-sufficiency, peak
      grid power
- [ ] Persist scenario results to `data/processed/` (parquet)

## Phase 6 — Streamlit dashboard
- [ ] Overview page: config + annual input profiles
- [ ] Representative days page: clustering results
- [ ] Daily detail page: stacked-area energy flows + Sankey "real-time flow"
      diagram with time slider
- [ ] Scenario comparison page: KPI table + bar charts

## Phase 7 — Extensions (optional)
- [ ] Battery degradation cost term
- [ ] Demand/peak-power charges
- [ ] Sensitivity sweeps on system sizing (PV/battery/EV size)
