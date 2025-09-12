import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


def test_prioritizes_weighted_hashtags(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.hashtag_scores = {"python": 10}
    hype = Hype(cfg)
    hype.client = MagicMock()
    hype.client.search_v2.side_effect = [
        {"statuses": [status_data("1", "https://a/1")]},
        {"statuses": [status_data("2", "https://a/2")]},
    ]
    m = MagicMock()
    m.trending_statuses.return_value = [
        {"uri": "https://a/2", "tags": [{"name": "rust"}]},
        {"uri": "https://a/1", "tags": [{"name": "python"}]},
    ]
    hype.init_client = MagicMock(return_value=m)
    inst = types.SimpleNamespace(name="i", limit=2)
    hype._boost_instance(inst)
    first_search = hype.client.search_v2.call_args_list[0][0][0]
    assert first_search == "https://a/1"
