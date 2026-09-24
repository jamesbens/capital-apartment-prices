"""Transform layer: pure pandas functions, no I/O.

Model (documented in the README):
    price_local[city, year] = anchor_local[city] * index[country, year] / index[country, anchor_year]
    price_eur[city, year]   = price_local[city, year] / fx_per_eur[currency, year]
    price[city, year, br]   = price_eur[city, year] * bedroom_factor[br]
"""

from __future__ import annotations

import pandas as pd


def annualize_index(quarterly: pd.DataFrame) -> pd.DataFrame:
    """Quarterly index -> annual mean, with the number of quarters observed (4 = complete year)."""
    df = quarterly.dropna(subset=["index_value"]).copy()
    df["year"] = df["period"].str[:4].astype(int)
    return (
        df.groupby(["country_code", "year"])
        .agg(index_value=("index_value", "mean"), quarters=("index_value", "size"))
        .reset_index()
    )


def annualize_fx(monthly: pd.DataFrame) -> pd.DataFrame:
    """Monthly FX -> annual mean, and inject EUR = 1.0 so euro-area cities join like any other."""
    df = monthly.dropna(subset=["per_eur"]).copy()
    df["year"] = df["period"].str[:4].astype(int)
    annual = df.groupby(["currency", "year"], as_index=False)["per_eur"].mean()
    eur = pd.DataFrame({"currency": "EUR", "year": annual["year"].unique(), "per_eur": 1.0})
    return pd.concat([annual, eur], ignore_index=True)


def model_city_prices(
    cities: pd.DataFrame, index_annual: pd.DataFrame, fx_annual: pd.DataFrame, years: list[int]
) -> pd.DataFrame:
    """Back-cast each city's anchor price along its national index, then convert to EUR."""
    idx = index_annual[index_annual["year"].isin(years)]
    anchor_idx = index_annual.rename(columns={"year": "anchor_year", "index_value": "anchor_index"})[
        ["country_code", "anchor_year", "anchor_index"]
    ]
    df = (
        cities.merge(idx, on="country_code", how="inner")
        .merge(anchor_idx, on=["country_code", "anchor_year"], how="left")
        .merge(fx_annual, on=["currency", "year"], how="left")
    )
    df["local_per_m2"] = df["anchor_local_per_m2"] * df["index_value"] / df["anchor_index"]
    df["eur_per_m2"] = df["local_per_m2"] / df["per_eur"]
    return df[["city", "country", "currency", "year", "quarters", "local_per_m2", "eur_per_m2"]]


def split_by_bedrooms(city_prices: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    out = city_prices.merge(factors[["bedrooms", "factor"]], how="cross")
    out["eur_per_m2"] = out["eur_per_m2"] * out["factor"]
    out["local_per_m2"] = out["local_per_m2"] * out["factor"]
    return out.drop(columns="factor").sort_values(["city", "bedrooms", "year"]).reset_index(drop=True)
