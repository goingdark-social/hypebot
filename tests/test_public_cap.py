import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hype.hype import Hype
from tests.test_seen_status import DummyConfig


class FixedDatetime(datetime):
    current = datetime(2024, 1, 1, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.current


def test_public_cap_flips_and_resets(tmp_path):
    cfg = DummyConfig(str(tmp_path / "state.json"))
    cfg.daily_public_cap = 2
    cfg.per_hour_public_cap = 1
    hype = Hype(cfg)
    with patch("hype.hype.datetime", FixedDatetime):
        FixedDatetime.current = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert hype._public_cap_available()
        hype._count_public_boost()
        assert not hype._public_cap_available()
        FixedDatetime.current = FixedDatetime.current + timedelta(hours=1)
        assert hype._public_cap_available()
        assert hype.state["hour_count"] == 0
        assert hype.state["day_count"] == 1
        hype._count_public_boost()
        assert not hype._public_cap_available()
        FixedDatetime.current = FixedDatetime.current + timedelta(days=1)
        assert hype._public_cap_available()
        assert hype.state["hour_count"] == 0
        assert hype.state["day_count"] == 0
