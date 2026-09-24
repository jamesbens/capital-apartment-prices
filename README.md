# Capital-City Apartment Prices per m² (10 years)

[![monthly-pipeline](https://github.com/jamesbens/capital-apartment-prices/actions/workflows/pipeline.yml/badge.svg)](https://github.com/jamesbens/capital-apartment-prices/actions/workflows/pipeline.yml)

**Live chart:** https://jamesbens.github.io/capital-apartment-prices/ · **Portfolio:** https://jamesbens.github.io/

An automated pipeline that combines two public statistical APIs with a curated seed table. It produces
**price per m² for 1-, 2- and 3-bedroom apartments in 17 capital cities over the last 10 years**. The
interactive chart lets you **pick up to two capitals** and **choose which apartment sizes** to compare,
in EUR or USD, as a chart or a table.

## Architecture

```
 BIS SDMX API ─────┐                                   seeds/cities.csv ──────┐
 (house-price       │   data/raw/  (landing zone,      seeds/bedroom_factors ─┤
  index, quarterly) ├─► raw API bytes kept for  ──► annualize ──► model ──► split by ──► quality ──► docs/data/
 ECB SDMX API ─────┘    lineage & offline replay)   (staging)   (city)     bedrooms    gates       JSON + CSV (mart)
 (FX, monthly)                                                                                        │
                                          GitHub Actions: 3rd of each month · tests first · auto-commit ▼
                                                                                    GitHub Pages chart (ECharts)
```

## Method (read this before quoting a number)

Free, consistent, city-level price-per-m² series **by bedroom count** don't exist across countries.
This project therefore builds a **transparent, documented model**:

1. **Anchor:** each city has an indicative **2025 average apartment price per m²** in local currency
   (`seeds/cities.csv`, rounded, compiled from public listing and notary sources).
2. **Trend:** the anchor is moved back in time with the country's **BIS residential property price index**
   (nominal, 2010 = 100, quarterly → annual mean).
   `price[y] = anchor × index[y] / index[2025]`
3. **Currency:** converted to EUR with **ECB annual-average reference rates**; USD view uses EUR/USD.
4. **Bedrooms:** a size-premium factor (`seeds/bedroom_factors.csv`: 1 BR ×1.10, 2 BR ×1.00, 3 BR ×0.92)
   reflects that smaller units cost more per m².

Known limitation: the national index is a proxy for the capital's trend. The design isolates this in one join,
so a city-level source (e.g. Notaires-INSEE for Paris, ONS for London) can replace it without touching the rest.

> Modeled estimates for a portfolio demonstration, not transaction data.

## Data quality gates

The run **refuses to publish** if any of these fail:
seed uniqueness and positivity · exact row count (cities × years × 3) with the missing cities named ·
no null prices (missing index or FX) · plausible range 300–50,000 €/m² · no year-over-year jump > 35%.

## Run locally

```bash
pip install -r requirements.txt
pytest -q                                            # offline unit tests
PYTHONPATH=src python -m apartment_prices.pipeline   # calls BIS + ECB, writes docs/data/
python -m http.server -d docs 8000
```

Add a city by adding one row to `seeds/cities.csv` (any country BIS covers).

## Layout

```
src/apartment_prices/  extract.py (APIs + landing) · transform.py (pure) · quality.py · pipeline.py
seeds/                 cities.csv · bedroom_factors.csv  (version-controlled reference data, like dbt seeds)
tests/                 offline unit tests for every transform and gate
docs/                  GitHub Pages chart + data/ (published mart)
```

---
Built by [James Bensoussan](https://www.linkedin.com/in/james-bensoussan/), Data Engineer.
