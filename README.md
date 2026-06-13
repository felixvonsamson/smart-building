# Smart Building Energy Optimization

Simulation and cost-optimization of a house's energy system (PV, battery,
EV, heat pump, hot water thermal storage, grid) under variable electricity
pricing. The project optimizes dispatch over representative days of a year
to estimate cost savings from smart, price-aware control compared to a
naive baseline, and provides an interactive dashboard to explore the
resulting energy flows.

## Documentation

- [docs/stack.md](docs/stack.md) — technology stack and modeling design decisions
- [docs/implementation_plan.md](docs/implementation_plan.md) — phased implementation plan / progress checklist

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Project layout

```
config/             House/system configuration files (YAML)
data/               raw / interim / processed time series data (not versioned)
src/smart_building/ Core package: data sources, model, solver, scenarios, KPIs
app/                Streamlit dashboard
notebooks/          Exploratory notebooks
tests/              Unit tests
```
