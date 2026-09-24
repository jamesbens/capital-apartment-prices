"""Offline tests for the transform and quality layers (no API calls)."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from apartment_prices.pipeline import load_seeds, select_years  # noqa: E402
from apartment_prices.quality import DataQualityError, check_output, check_seeds  # noqa: E402
from apartment_prices.transform import (  # noqa: E402
    annualize_fx,
    annualize_index,
    model_city_prices,
    split_by_bedrooms,
)

SEEDS = Path(__file__).resolve().parents[1] / "seeds"


@pytest.fixture
def cities():
    return pd.DataFrame(
        {
            "city": ["Paris", "London"],
            "country": ["France", "United Kingdom"],
            "country_code": ["FR", "GB"],
            "currency": ["EUR", "GBP"],
            "anchor_year": [2025, 2025],
            "anchor_local_per_m2": [10_000, 8_000],
        }
    )


@pytest.fixture
def factors():
    return pd.DataFrame({"bedrooms": [1, 2, 3], "label": ["1", "2", "3"], "factor": [1.1, 1.0, 0.9]})


@pytest.fixture
def index_q():
    rows = []
    for cc, base in [("FR", 100.0), ("GB", 200.0)]:
        for year, level in [(2024, base), (2025, base * 1.1)]:
            for q in range(1, 5):
                rows.append({"country_code": cc, "period": f"{year}-Q{q}", "index_value": level})
    return pd.DataFrame(rows)


@pytest.fixture
def fx_m():
    return pd.DataFrame(
        [{"currency": "GBP", "period": f"{y}-{m:02d}", "per_eur": 0.8} for y in (2024, 2025) for m in range(1, 13)]
    )


def test_annualize_index_counts_quarters(index_q):
    out = annualize_index(index_q.iloc[:-1])  # drop GB 2025-Q4
    gb25 = out[(out.country_code == "GB") & (out.year == 2025)].iloc[0]
    assert gb25.quarters == 3
    assert gb25.index_value == pytest.approx(220.0)


def test_annualize_fx_injects_eur(fx_m):
    out = annualize_fx(fx_m)
    assert set(out.currency) == {"GBP", "EUR"}
    assert out.loc[out.currency == "EUR", "per_eur"].eq(1.0).all()


def test_model_back_casts_along_index_and_converts(cities, index_q, fx_m):
    out = model_city_prices(cities, annualize_index(index_q), annualize_fx(fx_m), [2024, 2025])
    paris = out[out.city == "Paris"].set_index("year")
    assert paris.loc[2025, "eur_per_m2"] == pytest.approx(10_000)  # anchor year returns the anchor
    assert paris.loc[2024, "eur_per_m2"] == pytest.approx(10_000 / 1.1)  # index was 10% lower
    london = out[out.city == "London"].set_index("year")
    assert london.loc[2025, "eur_per_m2"] == pytest.approx(8_000 / 0.8)  # GBP -> EUR


def test_bedroom_split(cities, index_q, fx_m, factors):
    base = model_city_prices(cities, annualize_index(index_q), annualize_fx(fx_m), [2025])
    out = split_by_bedrooms(base, factors)
    paris = out[out.city == "Paris"].set_index("bedrooms")["eur_per_m2"]
    assert paris[1] > paris[2] > paris[3]
    assert len(out) == 2 * 3


def test_select_years_uses_latest_common_year():
    df = pd.DataFrame({"country_code": ["A", "A", "B"], "year": [2025, 2026, 2025]})
    assert select_years(df, 3) == [2023, 2024, 2025]


def test_check_output_rejects_missing_city(cities, index_q, fx_m, factors):
    base = model_city_prices(cities, annualize_index(index_q), annualize_fx(fx_m), [2024, 2025])
    tidy = split_by_bedrooms(base, factors)
    check_output(tidy, cities, [2024, 2025])
    with pytest.raises(DataQualityError, match="London"):
        check_output(tidy[tidy.city != "London"], cities, [2024, 2025])


def test_check_seeds_rejects_duplicates(cities, factors):
    with pytest.raises(DataQualityError, match="duplicate"):
        check_seeds(pd.concat([cities, cities.iloc[:1]]), factors)


def test_committed_seeds_are_valid():
    cities, factors = load_seeds(SEEDS)
    assert len(cities) >= 10
