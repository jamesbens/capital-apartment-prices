"""Extract layer: pull raw CSVs from public SDMX APIs into a local landing zone (data/raw/).

Every raw response is persisted before parsing, so a failed transform can be re-run offline
and any published number can be traced back to the exact bytes the API returned.
"""

from __future__ import annotations

import io
import logging
import time
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

BIS_URL = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_SPP/1.0/Q.{codes}.N.628"
ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/M.{codes}.EUR.SP00.A"


def _get(url: str, params: dict, retries: int = 4, timeout: int = 60) -> str:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout, headers={"Accept": "text/csv"})
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            if attempt == retries:
                raise
            wait = 2**attempt
            log.warning("GET %s failed (%s); retry in %ds", url, exc, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")


def _land(text: str, raw_dir: Path, name: str) -> pd.DataFrame:
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / name).write_text(text, encoding="utf-8")
    return pd.read_csv(io.StringIO(text))


def fetch_bis_price_index(country_codes: list[str], start_year: int, raw_dir: Path) -> pd.DataFrame:
    """BIS selected residential property prices: nominal index, 2010 = 100, quarterly.

    Returns tidy columns: country_code, period (e.g. '2024-Q3'), index_value.
    """
    url = BIS_URL.format(codes="+".join(sorted(country_codes)))
    text = _get(url, {"format": "csv", "startPeriod": f"{start_year}-Q1"})
    df = _land(text, raw_dir, "bis_ws_spp.csv")
    return df.rename(columns={"REF_AREA": "country_code", "TIME_PERIOD": "period", "OBS_VALUE": "index_value"})[
        ["country_code", "period", "index_value"]
    ]


def fetch_ecb_fx(currencies: list[str], start_year: int, raw_dir: Path) -> pd.DataFrame:
    """ECB reference rates, monthly averages, expressed as units of currency per 1 EUR.

    Returns tidy columns: currency, period (e.g. '2024-07'), per_eur.
    """
    currencies = sorted(set(currencies) - {"EUR"})
    url = ECB_URL.format(codes="+".join(currencies))
    text = _get(url, {"format": "csvdata", "startPeriod": f"{start_year}-01"})
    df = _land(text, raw_dir, "ecb_exr.csv")
    return df.rename(columns={"CURRENCY": "currency", "TIME_PERIOD": "period", "OBS_VALUE": "per_eur"})[
        ["currency", "period", "per_eur"]
    ]
