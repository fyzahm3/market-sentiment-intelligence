"""Daily price loader backed by yfinance (optional dependency), with a local cache.

yfinance is an unofficial client. Its output is checked by
``signal_audit.data.sanity.check_prices`` before any audit on real data.

The cache stores the exact prices an audit used together with where they came
from and a SHA-256 digest of their content, so a report card can name its data
and a later run can prove it used the same numbers.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, cast

import pandas as pd

from signal_audit.data.market import MarketData

Download = Callable[[Sequence[str], str, str], pd.DataFrame]
"""``(tickers, start, end) -> raw frame`` with (field, ticker) columns, like yfinance."""


class PriceCacheError(RuntimeError):
    """The price cache is incomplete, inconsistent or has been altered."""


@dataclass(frozen=True)
class PriceSource:
    """Where a set of cached prices came from, and a digest of their content."""

    provider: str
    provider_version: str
    adjusted: bool
    downloaded_at: dt.datetime
    sha256: str
    cache_file: Path

    def __post_init__(self) -> None:
        offset = self.downloaded_at.utcoffset()
        if offset is None or offset != dt.timedelta(0):
            raise ValueError("downloaded_at must be timezone-aware UTC")

    def describe(self) -> str:
        """One line for a report card."""
        adjusted = "split/dividend adjusted" if self.adjusted else "not adjusted"
        stamp = self.downloaded_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        return (
            f"{self.provider} {self.provider_version}, {adjusted}, "
            f"downloaded {stamp}, sha256 {self.sha256}"
        )


def frame_to_market(raw: pd.DataFrame, tickers: Sequence[str]) -> MarketData:
    """Convert a yfinance-style download (field x ticker columns) to MarketData."""
    if not isinstance(raw.columns, pd.MultiIndex):
        raise ValueError("expected columns indexed by (field, ticker)")

    opens = cast(pd.DataFrame, raw["Open"]).reindex(columns=list(tickers))
    closes = cast(pd.DataFrame, raw["Close"]).reindex(columns=list(tickers))

    empty = [t for t in tickers if opens[t].isna().all()]
    if empty:
        raise ValueError(f"no price data returned for: {empty}")

    keep = ~(opens.isna().all(axis=1) | closes.isna().all(axis=1))
    opens, closes = opens[keep], closes[keep]

    index = pd.DatetimeIndex(opens.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    index = index.normalize()
    opens.index = index
    closes.index = index
    return MarketData(opens=opens.sort_index(), closes=closes.sort_index())


def _yfinance_download(tickers: Sequence[str], start: str, end: str) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError(
            "yfinance is not installed. Install the data extra: uv sync --extra data"
        ) from exc

    raw = yf.download(
        list(tickers),
        start=start,
        end=end,
        auto_adjust=True,
        progress=False,
        group_by="column",
        multi_level_index=True,
    )
    if raw is None or raw.empty:
        raise RuntimeError("price download returned no rows")
    return cast(pd.DataFrame, raw)


def _yfinance_version() -> str:
    try:
        return version("yfinance")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "yfinance is not installed. Install the data extra: uv sync --extra data"
        ) from exc


def load_prices(tickers: Sequence[str], start: str, end: str) -> MarketData:
    """Download split- and dividend-adjusted daily prices (``end`` is exclusive)."""
    return frame_to_market(_yfinance_download(tickers, start, end), tickers)


def prices_sha256(data: MarketData) -> str:
    """SHA-256 of a canonical CSV rendering of the opens and closes."""
    digest = hashlib.sha256()
    for label, frame in (("opens", data.opens), ("closes", data.closes)):
        text = frame.to_csv(float_format="%.17g", date_format="%Y-%m-%d", lineterminator="\n")
        digest.update(f"{label}\n".encode())
        digest.update(text.encode("utf-8"))
    return digest.hexdigest()


def cache_key(tickers: Sequence[str], start: str, end: str) -> str:
    """Short, stable key for a (ticker set, start, end) request."""
    payload = json.dumps([sorted(tickers), start, end], separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_prices_cached(
    tickers: Sequence[str],
    start: str,
    end: str,
    cache_dir: Path,
    *,
    refresh: bool = False,
    download: Download | None = None,
    provider: str | None = None,
    provider_version: str | None = None,
) -> tuple[MarketData, PriceSource]:
    """Load adjusted daily prices from the cache, downloading them on a miss.

    Columns are returned in sorted ticker order, so a cache hit and a fresh
    download give identical data whatever order ``tickers`` came in. ``end`` is
    exclusive, as in yfinance.

    On a hit the stored digest is recomputed; a mismatch, or a cache with only
    one of its two files, raises ``PriceCacheError``. Nothing is re-downloaded
    unless ``refresh`` is set.

    ``download`` replaces the yfinance call (for tests). When it is given,
    ``provider`` and ``provider_version`` name the real source; they default to
    ``"injected"`` and ``"unknown"`` so a substitute is never labelled yfinance.
    """
    wanted = sorted({str(t) for t in tickers})
    if len(wanted) != len(tickers):
        raise ValueError("tickers must be unique")
    if not wanted:
        raise ValueError("no tickers requested")

    key = cache_key(wanted, start, end)
    cache_file = Path(cache_dir) / f"prices_{key}.parquet"
    meta_file = cache_file.with_suffix(".json")

    if not refresh and (cache_file.exists() or meta_file.exists()):
        if not (cache_file.exists() and meta_file.exists()):
            raise PriceCacheError(
                f"incomplete price cache for key {key}: expected both {cache_file.name} and "
                f"{meta_file.name}. Re-run with refresh to download again."
            )
        return _read_cache(cache_file, meta_file, wanted, start, end)

    if download is None:
        fetch: Download = _yfinance_download
        source_name = provider or "yfinance"
        source_version = provider_version or _yfinance_version()
    else:
        fetch = download
        source_name = provider or "injected"
        source_version = provider_version or "unknown"

    data = frame_to_market(fetch(wanted, start, end), wanted)
    source = PriceSource(
        provider=source_name,
        provider_version=source_version,
        adjusted=True,
        downloaded_at=dt.datetime.now(dt.UTC).replace(microsecond=0),
        sha256=prices_sha256(data),
        cache_file=cache_file,
    )
    _write_cache(data, source, meta_file, wanted, start, end)
    return data, source


def _write_cache(
    data: MarketData,
    source: PriceSource,
    meta_file: Path,
    tickers: list[str],
    start: str,
    end: str,
) -> None:
    source.cache_file.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.concat({"Open": data.opens, "Close": data.closes}, axis=1)
    tmp = source.cache_file.with_name(source.cache_file.name + ".tmp")
    frame.to_parquet(tmp)
    os.replace(tmp, source.cache_file)

    meta: dict[str, Any] = {
        "provider": source.provider,
        "provider_version": source.provider_version,
        "adjusted": source.adjusted,
        "downloaded_at": source.downloaded_at.isoformat(),
        "sha256": source.sha256,
        "tickers": tickers,
        "start": start,
        "end": end,
    }
    tmp_meta = meta_file.with_name(meta_file.name + ".tmp")
    tmp_meta.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_meta, meta_file)


def _read_cache(
    cache_file: Path, meta_file: Path, tickers: list[str], start: str, end: str
) -> tuple[MarketData, PriceSource]:
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    request = (meta.get("tickers"), meta.get("start"), meta.get("end"))
    if request != (tickers, start, end):
        raise PriceCacheError(
            f"{meta_file} describes a different request {request!r}; "
            f"expected {(tickers, start, end)!r}"
        )

    frame = pd.read_parquet(cache_file)
    if not isinstance(frame.columns, pd.MultiIndex):
        raise PriceCacheError(f"{cache_file} does not have (field, ticker) columns")
    opens = cast(pd.DataFrame, frame["Open"])
    closes = cast(pd.DataFrame, frame["Close"])
    if [str(c) for c in opens.columns] != tickers:
        raise PriceCacheError(f"{cache_file} holds tickers {list(opens.columns)}, not {tickers}")
    data = MarketData(opens=opens, closes=closes)

    digest = prices_sha256(data)
    if digest != meta["sha256"]:
        raise PriceCacheError(
            f"price cache {cache_file} does not match its recorded sha256 "
            f"(recorded {meta['sha256']}, found {digest}). It has been altered or "
            "corrupted. Re-run with refresh to download again."
        )
    source = PriceSource(
        provider=str(meta["provider"]),
        provider_version=str(meta["provider_version"]),
        adjusted=bool(meta["adjusted"]),
        downloaded_at=dt.datetime.fromisoformat(str(meta["downloaded_at"])),
        sha256=digest,
        cache_file=cache_file,
    )
    return data, source
