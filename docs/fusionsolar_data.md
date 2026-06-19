# FusionSolar Data Fetcher

`scripts/fetch_fusionsolar.py` downloads 5-minute-resolution energy data from the Huawei FusionSolar portal API, one day at a time.

## Setup

Create a `.env` file in the project root (gitignored) with your session credentials:

```
FUSIONSOLAR_COOKIE='<Cookie header from browser DevTools>'
FUSIONSOLAR_ROARAND='<roarand header, if present>'
```

To get these values: open the FusionSolar portal in your browser, open DevTools → Network tab, find any `energy-balance` request, and copy the `Cookie` and `Roarand` request headers.

The session cookie expires after a few hours, so refresh it in `.env` if you get 401 errors.

## Usage

```bash
python scripts/fetch_fusionsolar.py --start 2026-05-19 --end 2026-06-17
```

Options:
- `--skip-existing` — don't re-download days that already have a JSON file
- `--delay <seconds>` — pause between requests (default: 1.0)

## Output

**Per-day JSON** in `data/raw/fusionsolar/<YYYY-MM-DD>.json` — full API responses.

**Consolidated CSV** at `data/raw/fusionsolar_energy_balance.csv` (regenerated on each run) with columns:

| Column | Unit | Description |
|---|---|---|
| `timestamp` | — | Local time, 5-min intervals (e.g. `2026-06-17 12:00 DST`) |
| `productPower` | kW | PV generation |
| `usePower` | kW | Total household consumption |
| `selfUsePower` | kW | PV power consumed directly (not exported or stored) |
| `chargePower` | kW | Battery charging power |
| `dischargePower` | kW | Battery discharging power |

Each day has 288 data points (24 h × 12 intervals/h).

The raw JSON also contains daily summary fields (`totalProductPower`, `totalUsePower`, `totalSelfUsePower`, `totalOnGridPower`, `totalBuyPower`, etc.) that are not included in the CSV.
