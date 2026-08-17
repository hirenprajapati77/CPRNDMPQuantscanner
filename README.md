# NDMP OS v6.0 – Quantitative Research Operating System

NDMP OS v6.0 is an institutional quantitative research and execution operating system designed to discover, validate, and exploit directional momentum edges in Indian NSE Futures & Options (F&O) markets.

---

## Repository Architecture

The platform is structured into 4 decoupled sub-modules:

* `ndmp_core/` — Production execution engine, broker integrations (Angel One OI, Fyers), data quality, scanner, and journals.
* `ndmp_research/` — Feature store (`BaseFeature` plugins) and YAML manifests.
* `ndmp_validation/` — 5 governance promotion gates, DSR, and PBO auditing.
* `ndmp_knowledge/` — ADRs, experiment logs, and decision journals.

---

## Current Milestone

**Sprint 1 — Live OI Integration & Production Hardening**

- Angel One EOD open-interest ingestion with dynamic contract selection
- Fyers OI poller with health monitoring and token management
- OI data-integrity guards (reject constant/placeholder OI)
- Prior-session CPR (no same-bar look-ahead)
- UTC-aligned scheduler with journal-based restart protection
- Observation journal for OI scoring validation

---

## Quick Start

```bash
pip install -e ".[dev]"
pytest
python generate_mock_data.py
python run_scanner.py
python status.py
```

Live ingestion (requires network + Angel One OI parquet snapshots):

```bash
python fetch_live_data.py
```

---

## Key Entry Points

| Script | Purpose |
|--------|---------|
| `run_scanner.py` | End-to-end scan, rank, and journal |
| `fetch_live_data.py` | Yahoo Finance + Angel One OI merge |
| `local_scheduler.py` | Daily scan at 15:20 IST (09:50 UTC) |
| `run_angelone_oi_poller.py` | Angel One live OI polling |
| `status.py` | Operational health report |

---

## Configuration

Central config lives in `ndmp_core/src/config.py`. Load overrides from YAML:

```python
from ndmp_core.src.config import SystemConfig
config = SystemConfig.load_from_yaml("config.yaml")
```

Gate thresholds and friction costs share a single source of truth via `DEFAULT_CONFIG`.
