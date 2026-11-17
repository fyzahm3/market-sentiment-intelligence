from __future__ import annotations

import numpy as np
import pandas as pd

from signal_audit.data.synthetic import synthetic_market


def test_engagement_leaves_prices_and_documents_unchanged() -> None:
    with_engagement = synthetic_market(n_days=150, seed=3)
    without = synthetic_market(n_days=150, seed=3, engagement=False)

    assert without.engagement is None
    assert with_engagement.engagement is not None
    pd.testing.assert_frame_equal(with_engagement.opens, without.opens)
    pd.testing.assert_frame_equal(with_engagement.closes, without.closes)
    assert with_engagement.documents is not None and without.documents is not None
    pd.testing.assert_frame_equal(with_engagement.documents.frame, without.documents.frame)


def test_engagement_is_seeded() -> None:
    a = synthetic_market(n_days=120, seed=5).engagement
    b = synthetic_market(n_days=120, seed=5).engagement
    c = synthetic_market(n_days=120, seed=6).engagement
    assert a is not None and b is not None and c is not None
    pd.testing.assert_frame_equal(a.frame, b.frame)
    assert not a.frame["score"].equals(c.frame["score"])


def test_engagement_snapshots_follow_each_document() -> None:
    data = synthetic_market(n_days=120, seed=5)
    assert data.documents is not None and data.engagement is not None
    docs = data.documents.frame.set_index("post_id")
    snaps = data.engagement.frame

    assert docs.index.is_unique
    assert set(snaps["post_id"]) == set(docs.index)

    first = snaps.sort_values("knowledge_time", kind="stable").groupby("post_id").head(1)
    first = first.set_index("post_id").loc[docs.index]
    # The first snapshot is taken when the post itself became known.
    assert (first["knowledge_time"] == docs["knowledge_time"]).all()
    assert (first["event_time"] == docs["event_time"]).all()
    assert (first["ticker"] == docs["ticker"]).all()

    # The last snapshot is the week-old archive value.
    last = snaps.groupby("post_id")["knowledge_time"].max()
    age = last - snaps.groupby("post_id")["event_time"].first()
    assert (age == pd.Timedelta(days=7)).all()

    counts = snaps.groupby("post_id").size()
    assert counts.min() >= 2 and counts.max() <= 5
    assert np.isfinite(snaps["score"]).all() and (snaps["score"] >= 0).all()
