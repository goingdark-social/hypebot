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
    inst = types.SimpleNamespace(name="i", limit=2)
    cfg.subscribed_instances = [inst]
    hype = Hype(cfg)
    hype.client = MagicMock()
    m = MagicMock()
    
    # Trending returns full status objects
    s1 = status_data("1", "https://a/1")
    s1["tags"] = [{"name": "python"}]
    s2 = status_data("2", "https://a/2")
    s2["tags"] = [{"name": "rust"}]
    
    # s2 comes first in trending, but s1 should be boosted first due to python hashtag weight
    m.trending_statuses.return_value = [s2, s1]
    hype.init_client = MagicMock(return_value=m)
    hype.boost()
    
    # Verify s1 (python) was boosted first
    first_reblog = hype.client.status_reblog.call_args_list[0][0][0]
    assert first_reblog["uri"] == "https://a/1"
