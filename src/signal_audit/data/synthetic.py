"""Seeded synthetic market data for demos and tests.

The generator plants a known, tradable effect so the audit can be checked
against ground truth: a persistent latent "attention" factor per ticker drives
both the number of documents on day T and the open-to-open return earned by a
position entered at the open of T+1. A signal that counts documents honestly
therefore has a real edge. Because the factor is persistent, prices trend
slightly, so momentum has a weak indirect edge. Random scores have none.

Some documents arrive late (their ``knowledge_time`` is days after their
``event_time``), which is what makes event-time bucketing a detectable leak.

Each document is also treated as a post with engagement (a score such as
Reddit upvotes), stored as point-in-time snapshots. The first snapshot is
taken at the document's own ``knowledge_time``; later ones at 1 h, 6 h, 36 h
and 7 days after ``event_time`` (ages earlier than the first snapshot are
skipped). The score of a snapshot taken ``a`` hours after posting is::

    score(a) = base * (1 - exp(-a / tau)) * exp(gamma * R(a))

``base`` is a lognormal draw per post (log-mean 3, log-sd 1), ``tau`` is the
growth time scale (6 h by default) and ``R(a)`` is the ticker's log
open-to-open return over the sessions that have fully completed after the
post's session: from the open of the next session to the latest open at or
before the snapshot. So engagement partly reacts to later price moves, as
real engagement does. The default ``gamma`` of 30 makes the week-old archive
value carry a strong, tradable echo of the returns that follow the decision,
which is the look-ahead that ``leak_archived_engagement`` exploits. Snapshots
visible by the close of the post's session have ``R = 0``, since no
open-to-open return after that session has completed yet.

Engagement is drawn from its own generator, ``default_rng([seed, 1])``, so
turning it on or off leaves prices and documents unchanged.

This data says nothing about real markets.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from signal_audit.data.market import MarketData
from signal_audit.data.pit import PointInTimeStore
from signal_audit.sessions import assign_sessions, session_opens_utc

DEFAULT_TICKERS = ("AAA", "BBB", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH")
SNAPSHOT_AGES = tuple(pd.Timedelta(hours=h) for h in (1, 6, 36, 7 * 24))


def synthetic_market(
    n_days: int = 750,
    tickers: tuple[str, ...] = DEFAULT_TICKERS,
    seed: int = 7,
    start: str = "2021-01-04",
    beta: float = 0.003,
    noise: float = 0.015,
    persistence: float = 0.9,
    docs_per_day: float = 6.0,
    late_fraction: float = 0.2,
    engagement: bool = True,
    engagement_gamma: float = 30.0,
    engagement_tau_hours: float = 6.0,
) -> MarketData:
    """Build a synthetic market with a planted attention effect.

    ``beta`` is the daily return per unit of the latent factor; set it to 0 for
    a market with no exploitable structure at all. ``engagement`` adds
    engagement snapshots for every document; ``engagement_gamma`` sets how
    strongly they react to later returns (see the module docstring).
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, periods=n_days)
    n_tickers = len(tickers)

    # Persistent latent factor (AR(1), unit variance).
    shocks = rng.standard_normal((n_days, n_tickers))
    latent = np.empty_like(shocks)
    latent[0] = shocks[0]
    scale = np.sqrt(1.0 - persistence**2)
    for t in range(1, n_days):
        latent[t] = persistence * latent[t - 1] + scale * shocks[t]

    # open_to_open[t] is the return from the open of t to the open of t+1.
    # A decision at the close of t is filled at the open of t+1 and earns
    # open_to_open[t+1], so that is where latent[t] shows up.
    open_to_open = rng.normal(0.0, noise, (n_days, n_tickers))
    open_to_open[1:] += beta * latent[:-1]

    growth = np.vstack([np.ones((1, n_tickers)), 1.0 + open_to_open[:-1]])
    opens = 100.0 * np.cumprod(growth, axis=0)
    closes = opens * (1.0 + rng.normal(0.0, noise * 0.6, (n_days, n_tickers)))

    documents = _synthetic_documents(rng, dates, tickers, latent, docs_per_day, late_fraction)
    snapshots = None
    if engagement:
        snapshots = _synthetic_engagement(
            np.random.default_rng([seed, 1]),
            documents,
            dates,
            pd.DataFrame(opens, index=dates, columns=list(tickers)),
            gamma=engagement_gamma,
            tau_hours=engagement_tau_hours,
        )
    return MarketData(
        opens=pd.DataFrame(opens, index=dates, columns=list(tickers)),
        closes=pd.DataFrame(closes, index=dates, columns=list(tickers)),
        documents=documents,
        engagement=snapshots,
    )


def _synthetic_documents(
    rng: np.random.Generator,
    dates: pd.DatetimeIndex,
    tickers: tuple[str, ...],
    latent: np.ndarray,
    docs_per_day: float,
    late_fraction: float,
) -> PointInTimeStore:
    counts = rng.poisson(docs_per_day * np.exp(0.5 * latent))
    day_idx, ticker_idx = np.nonzero(counts)
    repeats = counts[day_idx, ticker_idx]
    day_idx = np.repeat(day_idx, repeats)
    ticker_idx = np.repeat(ticker_idx, repeats)
    n_docs = len(day_idx)

    # Posted during the session, comfortably before the close.
    opens_utc = session_opens_utc(dates)
    offset_s = rng.uniform(0, 6 * 3600, n_docs)
    event_time = opens_utc[day_idx] + pd.to_timedelta(offset_s, unit="s")

    # Most documents are seen within minutes; some only arrive days later.
    late = rng.random(n_docs) < late_fraction
    delay_s = np.where(
        late, rng.uniform(1 * 86400, 3 * 86400, n_docs), rng.uniform(0, 20 * 60, n_docs)
    )
    knowledge_time = event_time + pd.to_timedelta(delay_s, unit="s")

    frame = pd.DataFrame(
        {
            "ticker": np.asarray(tickers, dtype=object)[ticker_idx],
            "event_time": event_time,
            "knowledge_time": knowledge_time,
            "post_id": [f"syn{i:07d}" for i in range(n_docs)],
        }
    )
    return PointInTimeStore(frame)


def _synthetic_engagement(
    rng: np.random.Generator,
    documents: PointInTimeStore,
    dates: pd.DatetimeIndex,
    opens: pd.DataFrame,
    gamma: float,
    tau_hours: float,
) -> PointInTimeStore:
    """Engagement snapshots for every document, following the module docstring."""
    posts = documents.frame
    n_posts = len(posts)
    n_days = len(dates)
    base = rng.lognormal(mean=3.0, sigma=1.0, size=n_posts)

    event = pd.DatetimeIndex(posts["event_time"]).as_unit("ns").asi8
    first = pd.DatetimeIndex(posts["knowledge_time"]).as_unit("ns").asi8
    later = [event + age.value for age in SNAPSHOT_AGES]
    times = np.column_stack([first, *later])
    keep = np.column_stack([np.ones(n_posts, dtype=bool), *(t > first for t in later)])
    post_idx = np.nonzero(keep)[0]
    snap_ns = times[keep]

    # R: log open-to-open return from the open after the post's session to the
    # latest open at or before the snapshot (0 if no such session has completed).
    session = np.minimum(assign_sessions(posts["event_time"], dates), n_days - 1)[post_idx]
    column = opens.columns.get_indexer(pd.Index(posts["ticker"]))[post_idx]
    start = np.minimum(session + 1, n_days - 1)
    opens_ns = session_opens_utc(dates).as_unit("ns").asi8
    latest = np.searchsorted(opens_ns, snap_ns, side="right") - 1
    end = np.maximum(latest, start)
    log_open = np.log(opens.to_numpy())
    realised = log_open[end, column] - log_open[start, column]

    age_hours = (snap_ns - event[post_idx]) / 3.6e12
    score = base[post_idx] * -np.expm1(-age_hours / tau_hours) * np.exp(gamma * realised)

    frame = pd.DataFrame(
        {
            "ticker": posts["ticker"].to_numpy()[post_idx],
            "event_time": pd.DatetimeIndex(posts["event_time"])[post_idx],
            "knowledge_time": pd.to_datetime(snap_ns, utc=True),
            "post_id": posts["post_id"].to_numpy()[post_idx],
            "score": score,
        }
    )
    return PointInTimeStore(frame)
