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
        
        # Set up logging with file handler if logfile_path is specified
        handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        )
        handlers.append(console_handler)
        
        # File handler if logfile_path is configured
        if self.config.logfile_path:
            try:
                # Ensure the directory exists
                import os
                logfile_dir = os.path.dirname(self.config.logfile_path)
                if logfile_dir and not os.path.exists(logfile_dir):
                    os.makedirs(logfile_dir, exist_ok=True)
                    
                file_handler = logging.FileHandler(self.config.logfile_path)
                file_handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s %(levelname)-8s %(name)s - %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S"
                    )
                )
                handlers.append(file_handler)
            except Exception as e:
                print(f"Warning: Could not set up log file {self.config.logfile_path}: {e}")
        
        # Configure logging
        logging.basicConfig(
            handlers=handlers,
            level=logging.getLevelName(self.config.log_level),
            force=True  # Override any existing logging configuration
        )
        
        self.log = logging.getLogger("hype")
        
        # Set up debug logger for detailed decision tracing
        self.debug_log = logging.getLogger("hype.decisions")
        if self.config.debug_decisions:
            self.debug_log.setLevel(logging.DEBUG)
        else:
            self.debug_log.setLevel(logging.INFO)
            
        self.state = self._load_state()
        self._seen = deque(
            self.state.get("seen_status_ids", []),
            maxlen=self.config.seen_cache_size,
        )
        self._boosted_today = self.state.get("authors_boosted_today", {})
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
                    return data
        except Exception:
            pass
        return {
            "seen_status_ids": [],
            "authors_boosted_today": {},
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
        if self.state.get("day") != day_key:
            self.state["day"] = day_key
            self.state["day_count"] = 0
            self.state["authors_boosted_today"] = {}
            self._boosted_today = self.state["authors_boosted_today"]
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
        sid = status.get("id", "unknown")
        url = status.get("url") or status.get("uri")
        author = status.get("account", {}).get("acct", "unknown")
        
        # Check various conditions for seen status
        sid_seen = sid in self._seen
        url_seen = url in self._seen if url else False
        already_reblogged = status.get("reblogged", False)
        author_limit_hit = (
            self.config.author_diversity_enforced
            and self._boosted_today.get(author, 0)
            >= self.config.max_boosts_per_author_per_day
        )
        
        is_seen = sid_seen or url_seen or already_reblogged or author_limit_hit
        
        # Debug logging for seen status decision
        if self.config.debug_decisions:
            sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
            self.debug_log.debug(f"STATUS {sid_display} | SEEN CHECK: {is_seen}")
            self.debug_log.debug(f"  Author: {author}")
            self.debug_log.debug(f"  ID seen: {sid_seen}")
            self.debug_log.debug(f"  URL seen: {url_seen}")
            self.debug_log.debug(f"  Already reblogged: {already_reblogged}")
            if self.config.author_diversity_enforced:
                self.debug_log.debug(f"  Author boosts today: {self._boosted_today.get(author, 0)}/{self.config.max_boosts_per_author_per_day}")
                self.debug_log.debug(f"  Author limit hit: {author_limit_hit}")
        
        return is_seen

    def _remember_status(self, status: dict):
        sid = status.get("id", "unknown")
        url = status.get("url") or status.get("uri")
        author = status.get("account", {}).get("acct", "unknown")
        self._seen.append(sid)
        if url:
            self._seen.append(url)
        self._boosted_today[author] = self._boosted_today.get(author, 0) + 1
        self.state["authors_boosted_today"] = self._boosted_today

    def _should_skip_status(self, status: dict) -> bool:
        sid = status.get("id", "unknown")
        
        # Check media requirement
        has_media = bool(status.get("media_attachments"))
        skip_no_media = self.config.require_media and not has_media
        
        # Check sensitive content without content warning
        is_sensitive = status.get("sensitive", False)
        spoiler_text = (status.get("spoiler_text") or "").strip()
        skip_sensitive = (
            self.config.skip_sensitive_without_cw
            and is_sensitive
            and not spoiler_text
        )
        
        # Check language allowlist
        lang = (status.get("language") or "").lower()
        skip_language = (
            self.config.languages_allowlist
            and lang not in self.config.languages_allowlist
        )
        
        # Check minimum engagement
        reblogs_count = status.get("reblogs_count", 0)
        favourites_count = status.get("favourites_count", 0)
        skip_low_reblogs = reblogs_count < self.config.min_reblogs
        skip_low_favourites = favourites_count < self.config.min_favourites
        
        should_skip = (
            skip_no_media
            or skip_sensitive
            or skip_language
            or skip_low_reblogs
            or skip_low_favourites
        )
        
        # Debug logging for filtering decision
        if self.config.debug_decisions:
            sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
            self.debug_log.debug(f"STATUS {sid_display} | FILTER CHECK: {'SKIP' if should_skip else 'KEEP'}")
            self.debug_log.debug(f"  Media attachments: {len(status.get('media_attachments', []))}")
            self.debug_log.debug(f"  Skip no media: {skip_no_media} (require_media: {self.config.require_media})")
            self.debug_log.debug(f"  Sensitive: {is_sensitive}, CW: '{spoiler_text}'")
            self.debug_log.debug(f"  Skip sensitive: {skip_sensitive}")
            self.debug_log.debug(f"  Language: '{lang}', allowlist: {self.config.languages_allowlist}")
            self.debug_log.debug(f"  Skip language: {skip_language}")
            self.debug_log.debug(f"  Reblogs: {reblogs_count} (min: {self.config.min_reblogs})")
            self.debug_log.debug(f"  Skip low reblogs: {skip_low_reblogs}")
            self.debug_log.debug(f"  Favourites: {favourites_count} (min: {self.config.min_favourites})")
            self.debug_log.debug(f"  Skip low favourites: {skip_low_favourites}")
        
        return should_skip

    def score_status(self, status: dict) -> float:
        sid = status.get("id", "unknown")
        
        # Calculate hashtag score
        hashtags = status.get("tags", [])
        tag_scores = [
            self.config.hashtag_scores.get(t.get("name", "").lower(), 0)
            for t in hashtags
        ]
        tag_score = sum(tag_scores)
        
        # Calculate engagement scores
        reblogs_count = status.get("reblogs_count", 0)
        favourites_count = status.get("favourites_count", 0)
        reblogs = math.log1p(reblogs_count) * 2
        favourites = math.log1p(favourites_count)
        
        # Calculate media bonus
        has_media = bool(status.get("media_attachments"))
        media_bonus = self.config.prefer_media if has_media else 0
        
        total_score = tag_score + reblogs + favourites + media_bonus
        
        # Debug logging for scoring decision
        if self.config.debug_decisions:
            sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
            self.debug_log.debug(f"STATUS {sid_display} | SCORING: {total_score:.2f}")
            self.debug_log.debug(f"  Hashtags: {[t.get('name', '') for t in hashtags]}")
            self.debug_log.debug(f"  Tag scores: {tag_scores} = {tag_score}")
            self.debug_log.debug(f"  Reblogs: {reblogs_count} -> {reblogs:.2f}")
            self.debug_log.debug(f"  Favourites: {favourites_count} -> {favourites:.2f}")
            self.debug_log.debug(f"  Media bonus: {media_bonus} (has_media: {has_media})")
            self.debug_log.debug(f"  Total: {tag_score} + {reblogs:.2f} + {favourites:.2f} + {media_bonus} = {total_score:.2f}")
        
        return total_score

    def _normalize_scores(self, entries):
        if not entries:
            return
        scores = [e["score"] for e in entries]
        lo = min(scores)
        hi = max(scores)
        if hi == lo:
            for e in entries:
                e["score"] = 100
            return
        span = hi - lo
        for e in entries:
            e["score"] = (e["score"] - lo) / span * 100

    def _created_at(self, status):
        value = status.get("created_at")
        if isinstance(value, datetime):
            return value
        if not value:
            return datetime.fromtimestamp(0, timezone.utc)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def boost(self):
        self.log.info("Run boost")
        
        # Debug: Log boost cycle start
        if self.config.debug_decisions:
            self.debug_log.info("=== BOOST CYCLE START ===")
            self.debug_log.info(f"Daily cap: {self.state.get('day_count', 0)}/{self.config.daily_public_cap}")
            self.debug_log.info(f"Hourly cap: {self.state.get('hour_count', 0)}/{self.config.per_hour_public_cap}")
            self.debug_log.info(f"Max boosts per run: {self.config.max_boosts_per_run}")
        
        if not self.config.subscribed_instances:
            self.log.warning("No subscribed instances configured.")
            return
        if not self._public_cap_available():
            self.log.info("Public cap reached. Skipping boosting this cycle.")
            return
            
        # Debug: Log instance fetching
        if self.config.debug_decisions:
            self.debug_log.info(f"Fetching from {len(self.config.subscribed_instances)} instances:")
            for inst in self.config.subscribed_instances:
                self.debug_log.info(f"  - {inst.name} (limit: {inst.limit})")
                
        collected = []
        for inst in self.config.subscribed_instances:
            statuses = self._fetch_trending_statuses(inst)
            if self.config.debug_decisions:
                self.debug_log.info(f"Instance {inst.name}: fetched {len(statuses)} statuses")
            for entry in statuses:
                s = entry["status"]
                entry["score"] = self.score_status(s)
                collected.append(entry)
                
        # Debug: Log collection results
        if self.config.debug_decisions:
            self.debug_log.info(f"Total collected statuses: {len(collected)}")
        
        self._normalize_scores(collected)
        collected.sort(
            key=lambda e: (e["score"], self._created_at(e["status"])),
            reverse=True,
        )
        
        # Debug: Log top candidates after sorting
        if self.config.debug_decisions:
            self.debug_log.info("=== TOP CANDIDATES AFTER SCORING ===")
            for i, entry in enumerate(collected[:10]):  # Show top 10
                status = entry["status"]
                sid = status.get("id", "unknown")
                author = status.get("account", {}).get("acct", "unknown")
                score = entry["score"]
                sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
                self.debug_log.info(f"#{i+1}: {sid_display} by {author} - score: {score:.2f}")
        
        total = len(collected)
        boosted = 0
        
        # Debug: Log boost decision loop start
        if self.config.debug_decisions:
            self.debug_log.info("=== BOOST DECISION LOOP ===")
        
        for entry in collected:
            if boosted >= self.config.max_boosts_per_run or not self._public_cap_available():
                if self.config.debug_decisions:
                    reason = "max boosts reached" if boosted >= self.config.max_boosts_per_run else "public cap reached"
                    self.debug_log.info(f"Breaking early: {reason}")
                break
                
            trending = entry["status"]
            sid = trending.get("id", "unknown")
            instance_name = entry["instance"]
            score = entry["score"]
            
            # Debug: Log candidate evaluation
            if self.config.debug_decisions:
                sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
                self.debug_log.info(f"--- EVALUATING STATUS {sid_display} ---")
                self.debug_log.info(f"From: {instance_name}, Score: {score:.2f}")
                
            result = self.client.search_v2(
                trending["uri"], result_type="statuses"
            ).get("statuses", [])
            
            if not result:
                self.log.info(f"{instance_name}: skip, not found")
                if self.config.debug_decisions:
                    self.debug_log.info(f"DECISION: SKIP - Status not found on our instance")
                continue
                
            status = result[0]
            
            if self._seen_status(status):
                self.log.info(f"{instance_name}: already boosted, skip")
                if self.config.debug_decisions:
                    self.debug_log.info(f"DECISION: SKIP - Already seen/boosted")
                continue
                
            acct = status.get("account", {}).get("acct", "").split("@")
            server = acct[-1] if len(acct) > 1 else ""
            if server in self.config.filtered_instances:
                self.log.info(f"{instance_name}: filtered instance {server}, skip")
                if self.config.debug_decisions:
                    self.debug_log.info(f"DECISION: SKIP - Instance {server} is filtered")
                continue
                
            if self._should_skip_status(status):
                self.log.info(f"{instance_name}: filtered by rules, skip")
                if self.config.debug_decisions:
                    self.debug_log.info(f"DECISION: SKIP - Filtered by content rules")
                continue
                
            # We're going to boost this status
            if self.config.debug_decisions:
                self.debug_log.info(f"DECISION: BOOST - Status passes all checks")
                author = status.get("account", {}).get("acct", "unknown")
                content_preview = (status.get("content", "") or "").strip()[:100]
                if len(content_preview) > 97:
                    content_preview = content_preview[:97] + "..."
                self.debug_log.info(f"  Author: {author}")
                self.debug_log.info(f"  Content: {content_preview}")
                
            self.client.status_reblog(status)
            self._count_public_boost()
            self._remember_status(status)
            self._save_state()
            boosted += 1
            self.log.info(f"{instance_name}: boosted {boosted}/{total}")
            
            if self.state["hour_count"] >= self.config.per_hour_public_cap:
                self.log.info("Per-hour public cap reached, stopping early.")
                if self.config.debug_decisions:
                    self.debug_log.info("EARLY STOP: Per-hour cap reached")
                break
        
        # Debug: Log boost cycle summary
        if self.config.debug_decisions:
            self.debug_log.info("=== BOOST CYCLE COMPLETE ===")
            self.debug_log.info(f"Boosted: {boosted} posts")
            self.debug_log.info(f"Daily count: {self.state.get('day_count', 0)}/{self.config.daily_public_cap}")
            self.debug_log.info(f"Hourly count: {self.state.get('hour_count', 0)}/{self.config.per_hour_public_cap}")

    def _fetch_trending_statuses(self, instance):
        try:
            if self.config.debug_decisions:
                self.debug_log.debug(f"Fetching trending statuses from {instance.name} (limit: {instance.limit})")
            client = self.init_client(instance.name)
            statuses = client.trending_statuses()[: instance.limit]
            result = [{"instance": instance.name, "status": s} for s in statuses]
            if self.config.debug_decisions:
                self.debug_log.debug(f"Successfully fetched {len(result)} statuses from {instance.name}")
            return result
        except Exception as err:
            self.log.error(f"{instance.name}: error - {err}")
            if self.config.debug_decisions:
                self.debug_log.error(f"Failed to fetch from {instance.name}: {err}")
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

