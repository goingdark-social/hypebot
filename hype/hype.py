import json
import logging
import os.path
import time
from collections import deque
from datetime import datetime, timezone
import math

import schedule
from mastodon import Mastodon

from .config import Config


class Hype:
    def __init__(self, config: Config) -> None:
        self.config = config
        logging.basicConfig(
            format="%(asctime)s %(levelname)-8s %(message)s",
            level=logging.getLevelName(self.config.log_level),
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.log = logging.getLogger("hype")
        self.state = self._load_state()
        self._seen = deque(
            self.state.get("seen_status_ids", []),
            maxlen=self.config.seen_cache_size,
        )
        self._boosted_today = self.state.get("authors_boosted_today", [])
        self.log.info("Config loaded")

    def login(self):
        self.log.info(f"Logging in to {self.config.bot_account.server}")
        self.client = Mastodon(
            api_base_url=self.config.bot_account.server,
            access_token=self.config.bot_account.access_token,
        )

    def update_profile(self):
        self.log.info("Update bot profile")
        subscribed_instances_list = "\n".join(
            [f"- {instance}" for instance in self.config.subscribed_instances]
        )
        note = f"""{self.config.profile_prefix}
{subscribed_instances_list}
"""
        fields = [(key, value) for key, value in self.config.fields.items()]
        self.client.account_update_credentials(
            note=note, bot=True, discoverable=True, fields=fields
        )
        self._save_state()

    def _load_state(self):
        try:
            if os.path.isfile(self.config.state_path):
                with open(self.config.state_path, "r") as handle:
                    data = json.load(handle)
                    data.setdefault("seen_status_ids", [])
                    data.setdefault("authors_boosted_today", [])
                    data.setdefault("last_seen_day", "")
                    return data
        except Exception:
            pass
        return {
            "seen_status_ids": [],
            "authors_boosted_today": [],
            "last_seen_day": "",
            "day": "",
            "day_count": 0,
            "hour": "",
            "hour_count": 0,
        }

    def _save_state(self):
        self.state["seen_status_ids"] = list(self._seen)
        self.state["authors_boosted_today"] = self._boosted_today
        try:
            with open(self.config.state_path, "w") as handle:
                json.dump(self.state, handle)
        except Exception as err:
            self.log.error(f"could not persist state: {err}")

    def _tick_counters(self):
        now = datetime.now(timezone.utc)
        day_key = now.strftime("%Y-%m-%d")
        hour_key = now.strftime("%Y-%m-%dT%H")
        if self.state.get("last_seen_day") != day_key:
            self.state["last_seen_day"] = day_key
            self.state["authors_boosted_today"] = []
            self._boosted_today = self.state["authors_boosted_today"]
        if self.state.get("day") != day_key:
            self.state["day"] = day_key
            self.state["day_count"] = 0
        if self.state.get("hour") != hour_key:
            self.state["hour"] = hour_key
            self.state["hour_count"] = 0

    def _public_cap_available(self) -> bool:
        self._tick_counters()
        return (
            self.state["day_count"] < self.config.daily_public_cap
            and self.state["hour_count"] < self.config.per_hour_public_cap
        )

    def _count_public_boost(self):
        self._tick_counters()
        self.state["day_count"] += 1
        self.state["hour_count"] += 1

    def _seen_status(self, status: dict) -> bool:
        sid = status["id"]
        url = status.get("url") or status.get("uri")
        author = status["account"]["acct"]
        return (
            sid in self._seen
            or url in self._seen
            or status.get("reblogged")
            or self._boosted_today.count(author)
            >= self.config.max_boosts_per_author_per_day
        )

    def _remember_status(self, status: dict):
        sid = status["id"]
        url = status.get("url") or status.get("uri")
        author = status["account"]["acct"]
        self._seen.append(sid)
        if url:
            self._seen.append(url)
        self._boosted_today.append(author)
        self.state["authors_boosted_today"] = self._boosted_today

    def _should_skip_status(self, status: dict) -> bool:
        if self.config.require_media and not status.get("media_attachments"):
            return True
        if (
            self.config.skip_sensitive_without_cw
            and status.get("sensitive")
            and not (status.get("spoiler_text") or "").strip()
        ):
            return True
        if self.config.languages_allowlist:
            lang = (status.get("language") or "").lower()
            if lang not in self.config.languages_allowlist:
                return True
        if status.get("reblogs_count", 0) < self.config.min_reblogs:
            return True
        if status.get("favourites_count", 0) < self.config.min_favourites:
            return True
        return False

    def score_status(self, status: dict) -> float:
        tag_score = sum(
            self.config.hashtag_scores.get(t.get("name", "").lower(), 0)
            for t in status.get("tags", [])
        )
        reblogs = math.log1p(status.get("reblogs_count", 0)) * 2
        favourites = math.log1p(status.get("favourites_count", 0))
        media_bonus = (
            1
            if self.config.prefer_media and status.get("media_attachments")
            else 0
        )
        return tag_score + reblogs + favourites + media_bonus

    def boost(self):
        self.log.info("Run boost")
        if not self.config.subscribed_instances:
            self.log.warning("No subscribed instances configured.")
            return
        if not self._public_cap_available():
            self.log.info("Public cap reached. Skipping boosting this cycle.")
            return
        collected = []
        for inst in self.config.subscribed_instances:
            collected.extend(self._fetch_trending_statuses(inst))
        collected.sort(
            key=lambda s: self.score_status(s["status"]),
            reverse=True,
        )
        total = len(collected)
        processed = 0
        for entry in collected:
            if not self._public_cap_available():
                self.log.info("Public cap reached before boost. Stopping.")
                break
            trending = entry["status"]
            result = self.client.search_v2(
                trending["uri"], result_type="statuses"
            ).get("statuses", [])
            if not result:
                self.log.info(f"{entry['instance']}: skip, not found")
                continue
            status = result[0]
            if self._seen_status(status):
                self.log.info(f"{entry['instance']}: already boosted, skip")
                continue
            acct = status["account"]["acct"].split("@")
            server = acct[-1] if len(acct) > 1 else ""
            if server in self.config.filtered_instances:
                self.log.info(f"{entry['instance']}: filtered instance {server}, skip")
                continue
            if self._should_skip_status(status):
                self.log.info(f"{entry['instance']}: filtered by rules, skip")
                continue
            self.client.status_reblog(status)
            self._count_public_boost()
            self._remember_status(status)
            self._save_state()
            processed += 1
            self.log.info(f"{entry['instance']}: boosted {processed}/{total}")
            if self.state["hour_count"] >= self.config.per_hour_public_cap:
                self.log.info("Per-hour public cap reached, stopping early.")
                break

    def _fetch_trending_statuses(self, instance):
        try:
            client = self.init_client(instance.name)
            statuses = client.trending_statuses()[: instance.limit]
            return [{"instance": instance.name, "status": s} for s in statuses]
        except Exception as err:
            self.log.error(f"{instance.name}: error - {err}")
            return []

    def start(self):
        self.boost()
        self.log.info(f"Schedule run every {self.config.interval} minutes")
        schedule.every(self.config.interval).minutes.do(self.boost)
        while True:
            schedule.run_pending()
            time.sleep(1)

    def init_client(self, instance_name: str) -> Mastodon:
        secret_path = f"secrets/{instance_name}_clientcred.secret"
        if not os.path.isfile(secret_path):
            self.log.info(f"Initialize client for {instance_name}")
            Mastodon.create_app(
                instance_name,
                api_base_url=f"https://{instance_name}",
                to_file=secret_path,
            )
        else:
            self.log.info(f"Client for {instance_name} is already initialized.")
        return Mastodon(
            client_id=secret_path,
            ratelimit_method="pace",
        )

