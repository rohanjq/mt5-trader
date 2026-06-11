"""Load and validate OHLC data from CSV files."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Accepted column names (case-insensitive mapping → canonical)
_COL_MAP = {
    "time": "time",
    "datetime": "time",
    "date": "time",
    "timestamp": "time",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "tick_volume": "volume",
    "tickvol": "volume",
    "volume": "volume",
    "vol": "volume",
    "real_volume": "real_volume",
    "spread": "spread",
}

REQUIRED = {"time", "open", "high", "low", "close"}


def load_ohlc(
    path: str | Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Load OHLC CSV and return a cleaned DataFrame.

    Returns columns: time (DatetimeIndex), open, high, low, close, volume.
    Sorted by time ascending.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Data file not found: {path}")

    df = pd.read_csv(path, sep=None, engine="python")  # auto-detect delimiter

    # Normalise column names
    rename = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        if key in _COL_MAP:
            rename[col] = _COL_MAP[key]
    df = df.rename(columns=rename)

    # Validate required columns
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Got: {list(df.columns)}")

    # Parse time
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # Ensure volume exists
    if "volume" not in df.columns:
        df["volume"] = 0

    # Filter date range
    if start:
        df = df[df["time"] >= pd.Timestamp(start)]
    if end:
        df = df[df["time"] <= pd.Timestamp(end)]

    df = df.reset_index(drop=True)
    log.info(
        "Loaded %d bars from %s (%s to %s)",
        len(df), path.name,
        df["time"].iloc[0] if len(df) > 0 else "N/A",
        df["time"].iloc[-1] if len(df) > 0 else "N/A",
    )
    return df


def load_ticks(
    path: str | Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """Load tick CSV and return a cleaned DataFrame.

    Returns columns: time (datetime64), bid, ask.
    Sorted by time ascending.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Tick data file not found: {path}")

    df = pd.read_csv(path, sep=None, engine="python")

    # Normalise column names
    rename = {}
    for col in df.columns:
        lc = col.strip().lower()
        if lc in ("time", "datetime", "timestamp"):
            rename[col] = "time"
        elif lc == "bid":
            rename[col] = "bid"
        elif lc == "ask":
            rename[col] = "ask"
    df = df.rename(columns=rename)

    if "bid" not in df.columns or "ask" not in df.columns:
        raise ValueError(f"Tick data must have 'bid' and 'ask' columns. Got: {list(df.columns)}")
    if "time" not in df.columns:
        raise ValueError(f"Tick data must have a 'time' column. Got: {list(df.columns)}")

    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # Filter date range
    if start:
        df = df[df["time"] >= pd.Timestamp(start)]
    if end:
        df = df[df["time"] <= pd.Timestamp(end)]

    df = df[["time", "bid", "ask"]].reset_index(drop=True)
    log.info(
        "Loaded %d ticks from %s (%s to %s)",
        len(df), path.name,
        df["time"].iloc[0] if len(df) > 0 else "N/A",
        df["time"].iloc[-1] if len(df) > 0 else "N/A",
    )
    return df
