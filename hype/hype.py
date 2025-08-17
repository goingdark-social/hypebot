import json
import logging
import os.path
import time
from collections import deque
from datetime import datetime, timezone

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
        self.instance_index = 0
        self.state = self._load_state()
        self._seen = deque(self.state.get("seen_status_ids", []), maxlen=6000)
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
        self.state["last_instance_index"] = self.instance_index
        self._save_state()

    def _load_state(self):
        try:
            if os.path.isfile(self.config.state_path):
                with open(self.config.state_path, "r") as handle:
                    data = json.load(handle)
                    data.setdefault("seen_status_ids", [])
                    return data
        except Exception:
            pass
        return {
            "seen_status_ids": [],
            "last_instance_index": 0,
            "day": "",
            "day_count": 0,
            "hour": "",
            "hour_count": 0,
        }

    def _save_state(self):
        self.state["seen_status_ids"] = list(self._seen)
        try:
            with open(self.config.state_path, "w") as handle:
                json.dump(self.state, handle)
        except Exception as err:
            self.log.error(f"could not persist state: {err}")

    def _tick_counters(self):
        now = datetime.now(timezone.utc)
        day_key = now.strftime("%Y-%m-%d")
        hour_key = now.strftime("%Y-%m-%dT%H")
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
        return sid in self._seen or url in self._seen or status.get("reblogged")

    def _remember_status(self, status: dict):
        sid = status["id"]
        url = status.get("url") or status.get("uri")
        self._seen.append(sid)
        if url:
            self._seen.append(url)

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
        return False

    def boost(self):
        self.log.info("Run boost")
        if not self.config.subscribed_instances:
            self.log.warning("No subscribed instances configured.")
            return
        instances = self.config.subscribed_instances
        if self.config.rotate_instances:
            self.instance_index = self.state.get("last_instance_index", 0) % len(
                instances
            )
            target = instances[self.instance_index]
            self._boost_instance(target)
            self.instance_index = (self.instance_index + 1) % len(instances)
            self.state["last_instance_index"] = self.instance_index
            self._save_state()
        else:
            for inst in instances:
                self._boost_instance(inst)

    def _boost_instance(self, instance):
        try:
            if not self._public_cap_available():
                self.log.info("Public cap reached. Skipping boosting this cycle.")
                return
            mastodon_client = self.init_client(instance.name)
            trending_statuses = mastodon_client.trending_statuses()[: instance.limit]
            total = len(trending_statuses)
            processed = 0
            for trending_status in trending_statuses:
                result = self.client.search_v2(
                    trending_status["uri"], result_type="statuses"
                ).get("statuses", [])
                if not result:
                    self.log.info(f"{instance.name}: skip, not found")
                    continue
                status = result[0]
                if self._seen_status(status):
                    self.log.info(f"{instance.name}: already boosted, skip")
                    continue
                acct = status["account"]["acct"].split("@")
                server = acct[-1] if len(acct) > 1 else ""
                if server in self.config.filtered_instances:
                    self.log.info(
                        f"{instance.name}: filtered instance {server}, skip"
                    )
                    continue
                if self._should_skip_status(status):
                    self.log.info(f"{instance.name}: filtered by rules, skip")
                    continue
                if not self._public_cap_available():
                    self.log.info("Public cap reached before boost. Stopping.")
                    break
                self.client.status_reblog(status)
                self._count_public_boost()
                self._remember_status(status)
                self._save_state()
                processed += 1
                self.log.info(f"{instance.name}: boosted {processed}/{total}")
                if self.state["hour_count"] >= self.config.per_hour_public_cap:
                    self.log.info("Per-hour public cap reached, stopping early.")
                    break
        except Exception as err:
            self.log.error(f"{instance.name}: error - {err}")

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

