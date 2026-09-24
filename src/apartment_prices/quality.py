"""Data-quality gates. The pipeline refuses to publish if any check fails."""

from __future__ import annotations

import pandas as pd


class DataQualityError(Exception):
    pass


def check_seeds(cities: pd.DataFrame, factors: pd.DataFrame) -> None:
    if cities["city"].duplicated().any():
        raise DataQualityError("duplicate city in seeds/cities.csv")
    if (cities["anchor_local_per_m2"] <= 0).any():
        raise DataQualityError("non-positive anchor price")
    if sorted(factors["bedrooms"]) != [1, 2, 3]:
        raise DataQualityError("bedroom factors must cover exactly 1, 2 and 3 bedrooms")


def check_output(df: pd.DataFrame, cities: pd.DataFrame, years: list[int]) -> None:
    expected = len(cities) * len(years) * 3
    if len(df) != expected:
        missing = set(cities["city"]) - set(df["city"])
        raise DataQualityError(f"expected {expected} rows, got {len(df)}; cities without data: {sorted(missing)}")
    if df["eur_per_m2"].isna().any():
        bad = df.loc[df["eur_per_m2"].isna(), ["city", "year"]].drop_duplicates()
        raise DataQualityError(f"null prices (missing index or FX?):\n{bad.to_string(index=False)}")
    if not df["eur_per_m2"].between(300, 50_000).all():
        raise DataQualityError("price per m2 outside plausible 300-50,000 EUR range")
    # Year-over-year swing larger than 35% in a national index would indicate a data break.
    yoy = df.sort_values("year").groupby(["city", "bedrooms"])["local_per_m2"].pct_change().abs()
    if (yoy > 0.35).any():
        raise DataQualityError("implausible year-over-year move > 35%")
