from __future__ import annotations

import datetime as dt
import json
from collections.abc import Sequence
from pathlib import Path

import pandas as pd
import pytest

from signal_audit.data.adapters.prices import (
    PriceCacheError,
    PriceSource,
    load_prices_cached,
    prices_sha256,
)
from signal_audit.data.market import MarketData
from signal_audit.data.synthetic import synthetic_market

START, END = "2021-01-04", "2021-06-30"


class FakeDownload:
    """yfinance-style raw frames built from synthetic prices; counts its calls."""

    def __init__(self, market: MarketData) -> None:
        self.market = market
        self.calls: list[tuple[list[str], str, str]] = []

    def __call__(self, tickers: Sequence[str], start: str, end: str) -> pd.DataFrame:
        self.calls.append((list(tickers), start, end))
        cols = list(tickers)
        return pd.concat(
            {"Open": self.market.opens[cols], "Close": self.market.closes[cols]}, axis=1
        )


@pytest.fixture
def fake() -> FakeDownload:
    return FakeDownload(synthetic_market(n_days=60, seed=3))


TICKERS = ["CCC", "AAA", "BBB"]


def test_cache_miss_downloads_once_and_writes_both_files(
    tmp_path: Path, fake: FakeDownload
) -> None:
    data, source = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    assert fake.calls == [(["AAA", "BBB", "CCC"], START, END)]
    assert data.tickers == ["AAA", "BBB", "CCC"]
    assert source.cache_file.exists()
    assert source.cache_file.with_suffix(".json").exists()
    assert source.cache_file.name.startswith("prices_")
    assert source.sha256 == prices_sha256(data)
    assert source.downloaded_at.tzinfo is not None
    assert source.adjusted


def test_injected_download_is_not_labelled_yfinance(tmp_path: Path, fake: FakeDownload) -> None:
    _, source = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    assert source.provider == "injected"
    assert "yfinance" not in source.describe()


def test_cache_hit_does_not_download(tmp_path: Path, fake: FakeDownload) -> None:
    first, src1 = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    # Same ticker set in a different order hits the same cache.
    second, src2 = load_prices_cached(["BBB", "CCC", "AAA"], START, END, tmp_path, download=fake)
    assert len(fake.calls) == 1
    pd.testing.assert_frame_equal(
        first.opens, second.opens, check_freq=False, check_index_type=False
    )
    pd.testing.assert_frame_equal(
        first.closes, second.closes, check_freq=False, check_index_type=False
    )
    assert src2.sha256 == src1.sha256
    assert src2.downloaded_at == src1.downloaded_at
    assert src2.cache_file == src1.cache_file


def test_different_request_uses_a_different_cache_file(tmp_path: Path, fake: FakeDownload) -> None:
    _, a = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    _, b = load_prices_cached(TICKERS, START, "2021-05-31", tmp_path, download=fake)
    assert a.cache_file != b.cache_file
    assert len(fake.calls) == 2


def test_refresh_downloads_again(tmp_path: Path, fake: FakeDownload) -> None:
    load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    load_prices_cached(TICKERS, START, END, tmp_path, download=fake, refresh=True)
    assert len(fake.calls) == 2


def test_tampered_cache_raises_and_does_not_redownload(tmp_path: Path, fake: FakeDownload) -> None:
    _, source = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    frame = pd.read_parquet(source.cache_file)
    frame.iloc[5, 0] *= 1.01
    frame.to_parquet(source.cache_file)
    with pytest.raises(PriceCacheError, match="sha256"):
        load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    assert len(fake.calls) == 1


def test_tampered_sidecar_raises(tmp_path: Path, fake: FakeDownload) -> None:
    _, source = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    meta_file = source.cache_file.with_suffix(".json")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["sha256"] = "0" * 64
    meta_file.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(PriceCacheError, match="sha256"):
        load_prices_cached(TICKERS, START, END, tmp_path, download=fake)


def test_missing_sidecar_raises(tmp_path: Path, fake: FakeDownload) -> None:
    _, source = load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    source.cache_file.with_suffix(".json").unlink()
    with pytest.raises(PriceCacheError, match="incomplete"):
        load_prices_cached(TICKERS, START, END, tmp_path, download=fake)
    assert len(fake.calls) == 1


def test_sha256_depends_on_content(fake: FakeDownload) -> None:
    market = fake.market
    bumped = market.closes.copy()
    bumped.iloc[0, 0] += 1e-9
    other = MarketData(opens=market.opens, closes=bumped)
    assert prices_sha256(market) == prices_sha256(MarketData(market.opens, market.closes))
    assert prices_sha256(market) != prices_sha256(other)


def test_price_source_requires_utc() -> None:
    with pytest.raises(ValueError, match="UTC"):
        PriceSource(
            provider="x",
            provider_version="1",
            adjusted=True,
            downloaded_at=dt.datetime(2026, 1, 1),
            sha256="a",
            cache_file=Path("x"),
        )


def test_describe_is_one_line() -> None:
    source = PriceSource(
        provider="yfinance",
        provider_version="1.8.0",
        adjusted=True,
        downloaded_at=dt.datetime(2026, 11, 17, 12, 30, tzinfo=dt.UTC),
        sha256="ab" * 32,
        cache_file=Path("prices_x.parquet"),
    )
    assert source.describe() == (
        "yfinance 1.8.0, split/dividend adjusted, downloaded 2026-11-17T12:30:00Z, "
        f"sha256 {'ab' * 32}"
    )
