import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype


class DummyConfig:
    def __init__(self, path):
        self.bot_account = types.SimpleNamespace(server="s", access_token="t")
        self.log_level = "ERROR"
        self.debug_decisions = False
        self.logfile_path = ""
        self.subscribed_instances = []
        self.filtered_instances = []
        self.profile_prefix = ""
        self.fields = {}
        self.daily_public_cap = 10
        self.per_hour_public_cap = 10
        self.max_boosts_per_run = 10
        self.max_boosts_per_author_per_day = 10
        self.author_diversity_enforced = True
        self.prefer_media = False
        self.require_media = False
        self.skip_sensitive_without_cw = False
        self.min_reblogs = 0
        self.min_favourites = 0
        self.min_replies = 0
        self.languages_allowlist = []
        self.state_path = path
        self.seen_cache_size = 6000
        self.hashtag_scores = {}
        # Add new configuration attributes
        self.age_decay_enabled = False
        self.age_decay_half_life_hours = 24.0
        self.hashtag_diversity_enforced = False
        self.max_boosts_per_hashtag_per_run = 1
        # Spam detection configuration
        self.spam_emoji_penalty = 0
        self.spam_emoji_threshold = 2
        self.spam_link_penalty = 0
        # Quality threshold configuration
        self.min_score_threshold = 0
        # Related hashtag scoring configuration
        self.related_hashtags = {}
        # Local timeline configuration
        self.local_timeline_enabled = False
        self.local_timeline_fetch_limit = 20
        self.local_timeline_boost_limit = 2
        self.local_timeline_min_engagement = 1



def status_data(i, u):
    return {
        "id": i,
        "url": u,
        "uri": u,
        "reblogged": False,
        "account": {"acct": "a@b"},
        "media_attachments": [1],
        "sensitive": False,
        "spoiler_text": "",
        "language": "en",
        "content": "",  # Add content field for spam detection tests
    }


def test_skips_duplicates_across_instances(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    inst1 = types.SimpleNamespace(name="i1", limit=1)
    inst2 = types.SimpleNamespace(name="i2", limit=1)
    cfg.subscribed_instances = [inst1, inst2]
    hype = Hype(cfg)
    client = MagicMock()
    client.search_v2.side_effect = [
        {"statuses": [status_data("1", "https://a/1")]},
        {"statuses": [status_data("2", "https://a/1")]},
    ]
    hype.client = client
    m1 = MagicMock()
    m1.trending_statuses.return_value = [{"uri": "https://a/1"}]
    m2 = MagicMock()
    m2.trending_statuses.return_value = [{"uri": "https://a/1"}]
    hype.init_client = MagicMock(side_effect=[m1, m2])
    hype.boost()
    assert client.status_reblog.call_count == 1
    assert list(hype._seen).count("https://a/1") == 1


def test_seen_cache_respects_size(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.seen_cache_size = 2
    hype = Hype(cfg)
    hype._remember_status(status_data("1", "https://a/1"))
    hype._remember_status(status_data("2", "https://a/2"))
    assert list(hype._seen) == ["2", "https://a/2"]


def test_respects_author_daily_limit(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.max_boosts_per_author_per_day = 1
    hype = Hype(cfg)
    hype._remember_status(status_data("1", "https://a/1"))
    assert hype._seen_status(status_data("2", "https://a/2"))


def test_can_disable_author_limit(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.max_boosts_per_author_per_day = 1
    cfg.author_diversity_enforced = False
    hype = Hype(cfg)
    hype._remember_status(status_data("1", "https://a/1"))
    assert not hype._seen_status(status_data("2", "https://a/2"))


def test_seen_status_duplicate_url(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    first = status_data("1", "https://a/1")
    second = status_data("2", "https://a/1")
    hype._remember_status(first)
    assert hype._seen_status(second)


def test_seen_status_duplicate_id(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    first = status_data("1", "https://a/1")
    second = status_data("1", "https://b/1")
    hype._remember_status(first)
    assert hype._seen_status(second)

