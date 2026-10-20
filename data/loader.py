import pandas as pd
import numpy as np
import requests


def load_csv(file):
    df = pd.read_csv(file)
    df.columns = [str(c).lower().strip() for c in df.columns]
    required = {"time", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        raise ValueError(f"Missing columns. Found: {sorted(df.columns.tolist())}")
    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    if df["time"].isna().any():
        raise ValueError("Invalid timestamps.")
    df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)
    if (df["high"] < df["low"]).any():
        raise ValueError("Rows where high < low detected.")
    if "volume" not in df.columns:
        df["volume"] = 0.0
    return df


def load_binance(symbol="BTCUSDT", interval="1h", limit=1000):
    url = "https://api.binance.com/api/v3/klines"
    r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": int(limit)}, timeout=20)
    r.raise_for_status()
    raw = r.json()
    if not raw:
        raise ValueError("Empty response from Binance.")
    df = pd.DataFrame(raw, columns=["time","open","high","low","close","volume",
                                     "ct","qav","trades","tbb","tbq","ig"])
    df = df[["time","open","high","low","close","volume"]].copy()
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    for c in ["open","high","low","close","volume"]:
        df[c] = df[c].astype(float)
    return df


def synthetic_data(n=2000, seed=42):
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, 0.001, n)
    close = 100 * np.exp(np.cumsum(rets))
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.0005, n)))
    low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.0005, n)))
    times = pd.date_range("2023-01-01", periods=n, freq="1h", tz="UTC")
    return pd.DataFrame({"time": times, "open": open_, "high": high,
                         "low": low, "close": close,
                         "volume": rng.uniform(100, 1000, n)})
