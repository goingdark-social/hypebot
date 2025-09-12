import sys
import math
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_scores_hashtags_and_engagement(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"python": 10}
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s["tags"] = [{"name": "python"}]
    s["reblogs_count"] = 3
    s["favourites_count"] = 8
    expected = 10 + math.log1p(3) * 2 + math.log1p(8)
    assert hype.score_status(s) == pytest.approx(expected)


def test_media_bonus(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.prefer_media = 0.5
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s["media_attachments"] = [1]
    assert hype.score_status(s) == pytest.approx(0.5)


def test_no_media_bonus_without_preference(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s["media_attachments"] = [1]
    assert hype.score_status(s) == 0
