"""End-to-end run: seeds + BIS + ECB -> docs/data/apartment_prices.json (+ tidy CSV).

    python -m apartment_prices.pipeline
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from .extract import fetch_bis_price_index, fetch_ecb_fx
from .quality import check_output, check_seeds
from .transform import annualize_fx, annualize_index, model_city_prices, split_by_bedrooms

log = logging.getLogger("apartment_prices")
ROOT = Path(__file__).resolve().parents[2]
YEARS_SHOWN = 10


def load_seeds(seed_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    cities = pd.read_csv(seed_dir / "cities.csv")
    factors = pd.read_csv(seed_dir / "bedroom_factors.csv")
    check_seeds(cities, factors)
    return cities, factors


def select_years(index_annual: pd.DataFrame, n: int) -> list[int]:
    """Last n years for which every country has at least one quarter of index data."""
    latest = int(index_annual.groupby("country_code")["year"].max().min())
    return list(range(latest - n + 1, latest + 1))


def to_payload(df: pd.DataFrame, cities: pd.DataFrame, factors: pd.DataFrame, fx: pd.DataFrame, years: list[int]) -> dict:
    partial = sorted(int(y) for y in df.loc[df["quarters"] < 4, "year"].unique())
    usd = fx[(fx["currency"] == "USD") & fx["year"].isin(years)].set_index("year")["per_eur"]
    values: dict[str, dict[str, list[int]]] = {}
    for (city, br), grp in df.groupby(["city", "bedrooms"]):
        values.setdefault(city, {})[str(br)] = [int(round(v)) for v in grp.sort_values("year")["eur_per_m2"]]
    return {
        "meta": {
            "title": "Apartment price per m² in capital cities",
            "unit": "EUR per m²",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "sources": [
                "BIS Selected Residential Property Prices (WS_SPP, nominal, 2010=100)",
                "ECB euro foreign exchange reference rates (EXR, monthly average)",
                "seeds/cities.csv: indicative 2025 city price level per m² (rounded)",
            ],
            "method": "City level is anchored to an indicative 2025 price per m² and moved back in time with the "
            "country's residential property price index, converted at annual average ECB rates. "
            "Bedroom split applies a size premium factor (smaller units cost more per m²). "
            "Modeled estimates for portfolio demonstration, not transaction data.",
            "partial_years": partial,
            "usd_per_eur": {str(y): round(float(v), 4) for y, v in usd.items()},
        },
        "years": years,
        "bedrooms": [{"key": str(r.bedrooms), "label": r.label} for r in factors.itertuples()],
        "cities": [
            {"name": r.city, "country": r.country, "currency": r.currency}
            for r in cities.sort_values("city").itertuples()
        ],
        "values": values,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "data")
    parser.add_argument("--raw", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cities, factors = load_seeds(ROOT / "seeds")
    start_year = date.today().year - YEARS_SHOWN - 2  # include the 2025 anchor + a buffer

    index_q = fetch_bis_price_index(cities["country_code"].tolist(), start_year, args.raw)
    fx_m = fetch_ecb_fx(cities["currency"].tolist() + ["USD"], start_year, args.raw)
    log.info("extracted %d BIS index rows, %d ECB FX rows", len(index_q), len(fx_m))

    index_a, fx_a = annualize_index(index_q), annualize_fx(fx_m)
    years = select_years(index_a, YEARS_SHOWN)
    tidy = split_by_bedrooms(model_city_prices(cities, index_a, fx_a, years), factors)
    check_output(tidy, cities, years)
    log.info("modeled %d rows for %d cities, %d-%d", len(tidy), cities.shape[0], years[0], years[-1])

    args.out.mkdir(parents=True, exist_ok=True)
    payload = to_payload(tidy, cities, factors, fx_a, years)
    target = args.out / "apartment_prices.json"
    target.with_suffix(".tmp").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    target.with_suffix(".tmp").replace(target)
    tidy.round(2).to_csv(args.out / "apartment_prices.csv", index=False)
    log.info("wrote %s", target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
