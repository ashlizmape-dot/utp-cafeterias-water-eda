"""Shared helpers for the exploratory analysis of the cafeteria water meters.

All notebooks import from here so that the three cafeterias are processed
with exactly the same rules.
"""

from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figures"

CAFETERIAS = ["CAF_C1", "CAF_CENTRAL", "CAF_C3"]
COLORS = {"CAF_C1": "#1f77b4", "CAF_CENTRAL": "#d62728", "CAF_C3": "#2ca02c"}

BIN = "15min"
BIN_SECONDS = 900
# Readings further apart than this are treated as a gap: the volume recorded
# across the gap is not assigned to any 15-min interval.
MAX_GAP_MIN = 60

# Academic calendar used during the internship (classes / vacation).
ACADEMIC_PERIODS = [
    ("2023-08-15", "2023-12-18", "classes"),
    ("2023-12-19", "2024-01-07", "vacation"),
    ("2024-01-08", "2024-03-06", "classes"),
    ("2024-03-07", "2024-03-17", "vacation"),
    ("2024-03-18", "2024-07-20", "classes"),
    ("2024-07-21", "2024-08-04", "vacation"),
    ("2024-08-05", "2024-12-10", "classes"),
    ("2024-12-11", "2025-01-12", "vacation"),
    ("2025-01-13", "2025-03-12", "classes"),
    ("2025-03-13", "2025-03-30", "vacation"),
    ("2025-03-31", "2025-08-02", "classes"),
    ("2025-08-03", "2025-08-17", "vacation"),
    ("2025-08-18", "2025-12-22", "classes"),
]

# Operating periods (decimal hours). CAF_CENTRAL serves breakfast and lunch
# only, so everything after 13:30 is "closed" there.
OPERATING_PERIODS = [
    (0.0, 5.0, "night"),
    (5.0, 7.0, "morning_prep"),
    (7.0, 13.5, "morning_service"),
    (13.5, 16.0, "afternoon_prep"),
    (16.0, 19.5, "evening_service"),
    (19.5, 24.0, "closed"),
]
OPERATING_ORDER = [p[2] for p in OPERATING_PERIODS]


def load_readings(cafeteria):
    """Cumulative meter readings (litres), local time, sorted and unique."""
    df = pd.read_csv(DATA_DIR / f"{cafeteria}_readings.csv", parse_dates=["datetime"])
    return df.set_index("datetime")["volume_L"].sort_index()


def sampling_intervals(readings):
    """Minutes between consecutive readings."""
    return readings.index.to_series().diff().dt.total_seconds().div(60).dropna()


def consumption_15min(readings, max_gap_min=MAX_GAP_MIN):
    """Volume consumed in each 15-min interval (L), without filling gaps.

    The cumulative volume is interpolated linearly in time at each 15-min
    boundary, but only when the boundary falls between two readings that are
    at most ``max_gap_min`` apart. Boundaries inside a longer gap stay empty,
    so the intervals around a gap are NaN instead of receiving an invented,
    evenly spread consumption.
    """
    t = readings.index.values.astype("datetime64[ns]").astype("int64")
    v = readings.values.astype(float)

    start = readings.index.min().ceil(BIN)
    end = readings.index.max().floor(BIN)
    edges = pd.date_range(start, end, freq=BIN)
    e = edges.values.astype("datetime64[ns]").astype("int64")

    j = np.searchsorted(t, e, side="right")  # first reading after the edge
    j = np.clip(j, 1, len(t) - 1)
    t0, t1 = t[j - 1], t[j]
    v0, v1 = v[j - 1], v[j]
    inside = (t0 <= e) & (e <= t1)
    exact = (e == t0) | (e == t1)
    short = (t1 - t0) <= max_gap_min * 60 * 1e9
    frac = np.where(t1 > t0, (e - t0) / np.maximum(t1 - t0, 1), 0.0)
    vol = np.where(exact, v0, v0 + frac * (v1 - v0))
    vol = np.where(inside & (short | exact), vol, np.nan)

    volume = pd.Series(vol, index=edges)
    cons = volume.diff().shift(-1).iloc[:-1]  # interval labelled by its start
    cons.name = "consumption_L"
    return cons


def consumption_15min_unlimited(readings):
    """Original approach (resample + unlimited time interpolation), kept only
    to show what happens across long gaps."""
    vol = readings.resample(BIN).mean().interpolate(method="time")
    cons = vol.diff().shift(-1).iloc[:-1]
    cons.name = "consumption_L"
    return cons


def academic_period(index):
    out = pd.Series("unknown", index=index)
    day = index.normalize()
    for s, e, label in ACADEMIC_PERIODS:
        out[(day >= pd.Timestamp(s)) & (day <= pd.Timestamp(e))] = label
    return out.values


def operating_period(index, cafeteria):
    h = index.hour + index.minute / 60
    out = np.empty(len(index), dtype=object)
    for lo, hi, label in OPERATING_PERIODS:
        out[(h >= lo) & (h < hi)] = label
    if cafeteria == "CAF_CENTRAL":
        out[h >= 13.5] = "closed"
    return out


def panama_holidays(years):
    return pd.to_datetime(list(holidays.country_holidays("PA", years=list(years)).keys()))


def build_dataset(max_gap_min=MAX_GAP_MIN):
    """Long table: one row per cafeteria and 15-min interval with calendar
    labels. Intervals without valid data are kept (consumption_L = NaN)."""
    frames = []
    for caf in CAFETERIAS:
        cons = consumption_15min(load_readings(caf), max_gap_min)
        df = cons.to_frame()
        df["flow_Ls"] = df["consumption_L"] / BIN_SECONDS
        df["cafeteria"] = caf
        frames.append(df)
    df = pd.concat(frames)
    df.index.name = "datetime"

    idx = df.index
    hol = panama_holidays(range(idx.year.min(), idx.year.max() + 1))
    df["date"] = idx.normalize()
    df["hour"] = idx.hour
    df["day_name"] = idx.day_name()
    df["is_weekday"] = idx.dayofweek < 5
    df["is_holiday"] = df["date"].isin(hol)
    df["academic_period"] = academic_period(idx)
    df["operating_period"] = np.concatenate(
        [operating_period(g.index, caf) for caf, g in df.groupby("cafeteria", sort=False)]
    )
    df["day_type"] = np.where(df["is_holiday"], "holiday",
                              np.where(df["is_weekday"], "weekday", "weekend"))
    return df


def daily_totals(df, min_coverage=1.0):
    """Daily volume (L) per cafeteria, only for days whose 96 intervals are
    all valid (``min_coverage`` = share of valid intervals required)."""
    g = df.groupby(["cafeteria", "date"])["consumption_L"]
    out = pd.DataFrame({"volume_L": g.sum(min_count=1), "valid": g.count()})
    out["coverage"] = out["valid"] / 96
    out = out[out["coverage"] >= min_coverage].reset_index()
    return out


def savefig(fig, name):
    FIG_DIR.mkdir(exist_ok=True)
    fig.savefig(FIG_DIR / f"{name}.png", dpi=200, bbox_inches="tight")


def set_style():
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.dpi": 110,
        "font.size": 10,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "legend.frameon": False,
    })
