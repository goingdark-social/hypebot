import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig, status_data


@pytest.mark.parametrize(
    "cfg_updates,status_updates,expected",
    [
        ({"require_media": True}, {"media_attachments": []}, True),
        ({"require_media": True}, {"media_attachments": [1]}, False),
        (
            {"skip_sensitive_without_cw": True},
            {"sensitive": True, "spoiler_text": ""},
            True,
        ),
        (
            {"skip_sensitive_without_cw": True},
            {"sensitive": True, "spoiler_text": "cw"},
            False,
        ),
        ({"languages_allowlist": ["en"]}, {"language": "fr"}, True),
        ({"languages_allowlist": ["en"]}, {"language": "en"}, False),
        ({"min_reblogs": 3}, {"reblogs_count": 2}, True),
        ({"min_reblogs": 3}, {"reblogs_count": 3}, False),
        ({"min_favourites": 4}, {"favourites_count": 3}, True),
        ({"min_favourites": 4}, {"favourites_count": 4}, False),
    ],
)
def test_should_skip_status(tmp_path, cfg_updates, status_updates, expected):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    for k, v in cfg_updates.items():
        setattr(cfg, k, v)
    hype = Hype(cfg)
    s = status_data("1", "https://a/1")
    s.update(status_updates)
    assert hype._should_skip_status(s) is expected
