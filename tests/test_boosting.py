import sys
from pathlib import Path
import types
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_normalizes_and_sorts_candidates(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    entries = [
        {"status": {"created_at": "2024-01-01T00:00:00Z"}, "score": 5, "created_at": datetime(2024, 1, 1)},
        {"status": {"created_at": "2024-01-03T00:00:00Z"}, "score": 15, "created_at": datetime(2024, 1, 3)},
        {"status": {"created_at": "2024-01-02T00:00:00Z"}, "score": 15, "created_at": datetime(2024, 1, 2)},
    ]
    hype._normalize_scores(entries)
    scores = [e["score"] for e in entries]
    assert scores == [0, 100, 100]
    entries.sort(key=lambda e: (e["score"], e["created_at"]), reverse=True)
    ordered = [e["created_at"].day for e in entries]
    assert ordered == [3, 2, 1]


def test_respects_max_boosts_per_run(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.max_boosts_per_run = 1
    inst = types.SimpleNamespace(name="i1", limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    trending = [
        {"uri": "https://a/1", "reblogs_count": 10, "favourites_count": 10, "created_at": "2024-01-02T00:00:00Z"},
        {"uri": "https://a/2", "reblogs_count": 5, "favourites_count": 5, "created_at": "2024-01-01T00:00:00Z"},
    ]
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    client = MagicMock()
    s1 = status_data("1", "https://a/1")
    s1["created_at"] = "2024-01-02T00:00:00Z"
    s2 = status_data("2", "https://a/2")
    s2["created_at"] = "2024-01-01T00:00:00Z"
    client.search_v2.side_effect = [{"statuses": [s1]}, {"statuses": [s2]}]
    hype.client = client
    hype.boost()
    assert client.status_reblog.call_count == 1


def test_equal_score_prefers_newer(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="i1", limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    trending = [
        {
            "uri": "https://a/1",
            "reblogs_count": 5,
            "favourites_count": 5,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://a/2",
            "reblogs_count": 5,
            "favourites_count": 5,
            "created_at": "2024-01-02T00:00:00Z",
        },
    ]
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    client = MagicMock()
    older = status_data("1", "https://a/1")
    older["created_at"] = "2024-01-01T00:00:00Z"
    newer = status_data("2", "https://a/2")
    newer["created_at"] = "2024-01-02T00:00:00Z"

    def search(uri, result_type=None):
        return {"statuses": [newer if uri == "https://a/2" else older]}

    client.search_v2.side_effect = search
    hype.client = client
    hype.boost()
    calls = [c.args[0]["uri"] for c in client.status_reblog.call_args_list]
    assert calls == ["https://a/2", "https://a/1"]


def test_no_activity_without_subscribed_instances(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    hype.client = MagicMock()
    hype.boost()
    hype.client.status_reblog.assert_not_called()
    hype.client.search_v2.assert_not_called()


def test_no_activity_when_public_cap_unavailable(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="i1", limit=1)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    hype._public_cap_available = MagicMock(return_value=False)
    hype.client = MagicMock()
    hype.boost()
    hype.client.status_reblog.assert_not_called()
    hype.client.search_v2.assert_not_called()


def test_skips_empty_filtered_and_blocked_statuses(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="i1", limit=3)
    cfg.subscribed_instances = [inst]
    cfg.filtered_instances = ["bad.instance"]
    cfg.require_media = True
    hype = Hype(cfg)
    trending = [
        {
            "uri": "https://a/1",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://a/2",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://a/3",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    client = MagicMock()
    s2 = status_data("2", "https://a/2")
    s2["account"]["acct"] = "u@bad.instance"
    s3 = status_data("3", "https://a/3")
    s3["media_attachments"] = []
    client.search_v2.side_effect = [
        {"statuses": []},
        {"statuses": [s2]},
        {"statuses": [s3]},
    ]
    hype.client = client
    hype.boost()
    client.status_reblog.assert_not_called()
    assert client.search_v2.call_count == 3


def test_stops_when_hour_cap_reached(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst = types.SimpleNamespace(name="i1", limit=5)
    cfg.subscribed_instances = [inst]
    cfg.per_hour_public_cap = 2
    hype = Hype(cfg)
    trending = [
        {
            "uri": "https://a/1",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://a/2",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
        {
            "uri": "https://a/3",
            "reblogs_count": 1,
            "favourites_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
        },
    ]
    m = MagicMock()
    m.trending_statuses.return_value = trending
    hype.init_client = MagicMock(return_value=m)
    client = MagicMock()
    client.search_v2.side_effect = [
        {"statuses": [status_data("1", "https://a/1")]},
        {"statuses": [status_data("2", "https://a/2")]},
        {"statuses": [status_data("3", "https://a/3")]},
    ]
    hype.client = client
    hype.boost()
    assert client.status_reblog.call_count == 2
    assert client.search_v2.call_count == 2
    assert hype.state["hour_count"] == 2
