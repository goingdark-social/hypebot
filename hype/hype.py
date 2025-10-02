import json
import logging
import os.path
import re
import time
from collections import deque
from datetime import datetime, timezone
import math

import schedule
from mastodon import Mastodon
from mastodon.errors import MastodonAPIError, MastodonNotFoundError

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
        # Track hashtags boosted in current run for diversity enforcement
        self._hashtags_boosted_this_run = []
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

    def _hashtag_diversity_hit(self, status: dict) -> bool:
        """Check if hashtag diversity limit is hit for any hashtag in the status."""
        if not self.config.hashtag_diversity_enforced:
            return False
            
        hashtags = status.get("tags", [])
        for tag in hashtags:
            tag_name = tag.get("name", "").lower()
            # Count how many times this hashtag has been boosted this run
            hashtag_count = self._hashtags_boosted_this_run.count(tag_name)
            if hashtag_count >= self.config.max_boosts_per_hashtag_per_run:
                return True
        return False

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
        hashtag_limit_hit = self._hashtag_diversity_hit(status)
        
        is_seen = sid_seen or url_seen or already_reblogged or author_limit_hit or hashtag_limit_hit
        
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
            if self.config.hashtag_diversity_enforced:
                hashtags = [tag.get("name", "").lower() for tag in status.get("tags", [])]
                self.debug_log.debug(f"  Hashtags: {hashtags}")
                self.debug_log.debug(f"  Hashtags boosted this run: {self._hashtags_boosted_this_run}")
                self.debug_log.debug(f"  Hashtag limit hit: {hashtag_limit_hit}")
        
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
        
        # Track hashtags for diversity enforcement in current run
        if self.config.hashtag_diversity_enforced:
            hashtags = status.get("tags", [])
            for tag in hashtags:
                tag_name = tag.get("name", "").lower()
                self._hashtags_boosted_this_run.append(tag_name)

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
        replies_count = status.get("replies_count", 0)
        skip_low_reblogs = reblogs_count < self.config.min_reblogs
        skip_low_favourites = favourites_count < self.config.min_favourites
        skip_low_replies = replies_count < self.config.min_replies
        
        should_skip = (
            skip_no_media
            or skip_sensitive
            or skip_language
            or skip_low_reblogs
            or skip_low_favourites
            or skip_low_replies
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
            self.debug_log.debug(f"  Replies: {replies_count} (min: {self.config.min_replies})")
            self.debug_log.debug(f"  Skip low replies: {skip_low_replies}")
        
        return should_skip

    def _count_emojis(self, text: str) -> int:
        """Count Unicode emojis in text content."""
        if not text:
            return 0
        # Unicode emoji regex pattern - match individual emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"  # dingbats
            "\U000024C2-\U0001F251"
            "]"  # Remove the + to match individual emojis
        )
        matches = emoji_pattern.findall(text)
        return len(matches)
    
    def _has_links(self, text: str) -> bool:
        """Check if text contains URLs."""
        if not text:
            return False
        # Simple URL detection pattern
        url_pattern = re.compile(r'https?://[^\s<>"]+|www\.[^\s<>"]+')
        return bool(url_pattern.search(text))

    def _calculate_related_hashtag_score(self, status: dict) -> float:
        """Calculate bonus score for hashtags related to configured keywords."""
        if not self.config.related_hashtags:
            return 0
        
        # Get post content for analysis
        content = (status.get("content", "") or "").lower()
        # Also check hashtags themselves
        hashtags = status.get("tags", [])
        hashtag_names = [t.get("name", "").lower() for t in hashtags]
        all_text = content + " " + " ".join(hashtag_names)
        
        related_score = 0
        for main_hashtag, related_terms in self.config.related_hashtags.items():
            main_hashtag_lower = main_hashtag.lower()
            # Check if the main hashtag is present
            if main_hashtag_lower in hashtag_names:
                continue  # Already scored in regular hashtag scoring
            
            # Check for related terms in content
            for related_term, multiplier in related_terms.items():
                if related_term.lower() in all_text:
                    # Get the base score for the main hashtag
                    base_score = self.config.hashtag_scores.get(main_hashtag_lower, 0)
                    if base_score > 0:  # Only apply bonus for positive base scores
                        bonus = base_score * float(multiplier)
                        related_score += bonus
                        break  # Only apply one bonus per main hashtag
        
        return related_score

    def score_status(self, status: dict) -> float:
        sid = status.get("id", "unknown")
        
        # Calculate hashtag score (now supports negative values)
        hashtags = status.get("tags", [])
        tag_scores = [
            self.config.hashtag_scores.get(t.get("name", "").lower(), 0)
            for t in hashtags
        ]
        tag_score = sum(tag_scores)
        
        # Calculate related hashtag bonuses
        related_score = self._calculate_related_hashtag_score(status)
        tag_score += related_score
        
        # Calculate engagement scores
        reblogs_count = status.get("reblogs_count", 0)
        favourites_count = status.get("favourites_count", 0)
        replies_count = status.get("replies_count", 0)
        reblogs = math.log1p(reblogs_count) * 2
        favourites = math.log1p(favourites_count)
        replies = math.log1p(replies_count) * 1.5  # Weight replies between favorites and reblogs
        
        # Calculate media bonus
        has_media = bool(status.get("media_attachments"))
        media_bonus = self.config.prefer_media if has_media else 0
        
        # Calculate spam penalties
        content = status.get("content", "") or ""
        spam_penalty = 0
        
        # Emoji spam detection
        emoji_count = self._count_emojis(content)
        if emoji_count > self.config.spam_emoji_threshold:
            excess_emojis = emoji_count - self.config.spam_emoji_threshold
            spam_penalty += excess_emojis * self.config.spam_emoji_penalty
        
        # Link penalty
        if self._has_links(content):
            spam_penalty += self.config.spam_link_penalty
        
        # Calculate base score
        base_score = tag_score + reblogs + favourites + replies + media_bonus - spam_penalty
        
        # Apply age decay if enabled
        age_penalty = 0
        if self.config.age_decay_enabled:
            created_at = self._created_at(status)
            now = datetime.now(timezone.utc)
            age_hours = (now - created_at).total_seconds() / 3600
            
            # Calculate decay factor using half-life formula: decay = 0.5^(age/half_life)
            if age_hours > 0 and self.config.age_decay_half_life_hours > 0:
                decay_factor = 0.5 ** (age_hours / self.config.age_decay_half_life_hours)
                age_penalty = base_score * (1 - decay_factor)
        
        total_score = base_score - age_penalty
        
        # Debug logging for scoring decision
        if self.config.debug_decisions:
            sid_display = sid[:8] + "..." if len(str(sid)) > 8 else str(sid)
            self.debug_log.debug(f"STATUS {sid_display} | SCORING: {total_score:.2f}")
            self.debug_log.debug(f"  Hashtags: {[t.get('name', '') for t in hashtags]}")
            direct_tag_score = sum(tag_scores)
            self.debug_log.debug(f"  Direct tag scores: {tag_scores} = {direct_tag_score}")
            if related_score > 0:
                self.debug_log.debug(f"  Related hashtag bonus: {related_score:.2f}")
            self.debug_log.debug(f"  Total tag score: {tag_score:.2f}")
            self.debug_log.debug(f"  Reblogs: {reblogs_count} -> {reblogs:.2f}")
            self.debug_log.debug(f"  Favourites: {favourites_count} -> {favourites:.2f}")
            self.debug_log.debug(f"  Replies: {replies_count} -> {replies:.2f}")
            self.debug_log.debug(f"  Media bonus: {media_bonus} (has_media: {has_media})")
            if spam_penalty > 0:
                emoji_count = self._count_emojis(content)
                has_links = self._has_links(content)
                self.debug_log.debug(f"  Spam detection: {emoji_count} emojis, has_links: {has_links}, penalty: {spam_penalty:.2f}")
            if self.config.age_decay_enabled:
                created_at = self._created_at(status)
                age_hours = (datetime.now(timezone.utc) - created_at).total_seconds() / 3600
                decay_factor = 0.5 ** (age_hours / self.config.age_decay_half_life_hours) if age_hours > 0 else 1
                self.debug_log.debug(f"  Age: {age_hours:.2f}h, decay factor: {decay_factor:.3f}, penalty: {age_penalty:.2f}")
            self.debug_log.debug(f"  Total: {base_score:.2f} - {age_penalty:.2f} = {total_score:.2f}")
        
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

    def _fetch_status_from_remote(self, status_id: str, instance_name: str) -> dict:
        """
        Fetch a status directly from a remote instance using GET /api/v1/statuses/:id.
        This validates the status exists and returns its canonical data.
        
        Returns the status dict if successful, None otherwise.
        """
        try:
            # Create a client for the remote instance (unauthenticated, public endpoint)
            remote_client = self.init_client(instance_name)
            status = remote_client.status(status_id)
            
            if self.config.debug_decisions:
                sid_display = str(status_id)[:8] + "..." if len(str(status_id)) > 8 else str(status_id)
                self.debug_log.debug(f"Remote fetch successful for {sid_display} from {instance_name}")
            
            return status
        except MastodonNotFoundError:
            if self.config.debug_decisions:
                sid_display = str(status_id)[:8] + "..." if len(str(status_id)) > 8 else str(status_id)
                self.debug_log.info(f"Remote status {sid_display} not found (404) on {instance_name}")
            return None
        except MastodonAPIError as e:
            self.log.warning(f"{instance_name}: Remote fetch error for status {status_id} - {e}")
            if self.config.debug_decisions:
                self.debug_log.warning(f"Remote fetch API error: {e}")
            return None
        except Exception as e:
            self.log.error(f"{instance_name}: Unexpected error fetching status {status_id} - {e}")
            if self.config.debug_decisions:
                self.debug_log.error(f"Remote fetch unexpected error: {e}")
            return None

    def _attempt_reblog_with_federation_fallback(self, status: dict, instance_name: str) -> tuple:
        """
        Attempt to reblog a status with federation fallback if needed.
        
        Correct flow per platform requirements:
        1. Try direct reblog (works if status already in local DB)
        2. If reblog returns 404 and federation enabled, use search(resolve=True) to federate
        3. Retry reblog after successful federation
        
        Returns (success: bool, status_for_tracking: dict or None)
        """
        status_id = status.get("id", "unknown")
        sid_display = str(status_id)[:8] + "..." if len(str(status_id)) > 8 else str(status_id)
        uri = status.get("uri") or status.get("url")
        
        if not uri:
            self.log.warning(f"{instance_name}: Cannot process status {status_id}, missing URI")
            if self.config.debug_decisions:
                self.debug_log.warning(f"DECISION: SKIP - Missing URI")
            return (False, None)
        
        # Attempt 1: Try direct reblog (status may already be in local DB)
        try:
            self.client.status_reblog(status)
            if self.config.debug_decisions:
                self.debug_log.debug(f"Direct reblog successful for {sid_display} (already in local DB)")
            return (True, status)
        except MastodonNotFoundError:
            # Status not in local DB (404 on reblog)
            if self.config.debug_decisions:
                self.debug_log.debug(f"Status {sid_display} not in local DB (404 on reblog attempt)")
            
            # Check if federation is enabled
            if not self.config.federate_missing_statuses:
                self.log.info(f"{instance_name}: skip, not federated (set federate_missing_statuses=true to enable)")
                if self.config.debug_decisions:
                    self.debug_log.info(f"DECISION: SKIP - reblog-404-federation-disabled")
                return (False, None)
            
            # Attempt 2: Try to federate via search with resolve=True
            if self.config.debug_decisions:
                self.debug_log.debug(f"Attempting to federate {sid_display} via search(resolve=True)")
            
            try:
                result = self.client.search_v2(
                    uri, result_type="statuses", resolve=True
                ).get("statuses", [])
                
                if not result:
                    # Search with resolve=True returned empty
                    self.log.info(f"{instance_name}: skip, resolve-empty (status exists remotely but couldn't be federated)")
                    if self.config.debug_decisions:
                        self.debug_log.info(f"DECISION: SKIP - remote-200-local-resolve-empty")
                    return (False, None)
                
                # Federation succeeded, retry reblog with federated status
                federated_status = result[0]
                if self.config.debug_decisions:
                    self.debug_log.debug(f"Federation successful for {sid_display}, retrying reblog")
                
                try:
                    self.client.status_reblog(federated_status)
                    if self.config.debug_decisions:
                        self.debug_log.debug(f"Reblog after federation successful for {sid_display}")
                    return (True, federated_status)
                except MastodonAPIError as reblog_error:
                    self.log.warning(f"{instance_name}: Reblog failed after federation - {reblog_error}")
                    if self.config.debug_decisions:
                        self.debug_log.warning(f"DECISION: SKIP - reblog-404-after-resolve")
                    return (False, None)
                    
            except MastodonAPIError as e:
                self.log.warning(f"{instance_name}: Federation attempt failed - {e}")
                if self.config.debug_decisions:
                    if "401" in str(e) or "Unauthorized" in str(e):
                        self.debug_log.warning(f"DECISION: SKIP - token-scope-missing")
                    else:
                        self.debug_log.warning(f"DECISION: SKIP - resolve-rejected ({e})")
                return (False, None)
            except Exception as e:
                self.log.error(f"{instance_name}: Unexpected error during federation - {e}")
                if self.config.debug_decisions:
                    self.debug_log.error(f"DECISION: SKIP - federation-error ({e})")
                return (False, None)
                
        except MastodonAPIError as e:
            self.log.warning(f"{instance_name}: Reblog attempt failed - {e}")
            if self.config.debug_decisions:
                self.debug_log.warning(f"DECISION: SKIP - reblog-error ({e})")
            return (False, None)
        except Exception as e:
            self.log.error(f"{instance_name}: Unexpected error during reblog - {e}")
            if self.config.debug_decisions:
                self.debug_log.error(f"DECISION: SKIP - reblog-unexpected-error ({e})")
            return (False, None)

    def boost(self):
        self.log.info("Run boost")
        
        # Reset hashtag tracking for current run
        self._hashtags_boosted_this_run = []
        
        # Debug: Log boost cycle start
        if self.config.debug_decisions:
            self.debug_log.info("=== BOOST CYCLE START ===")
            self.debug_log.info(f"Daily cap: {self.state.get('day_count', 0)}/{self.config.daily_public_cap}")
            self.debug_log.info(f"Hourly cap: {self.state.get('hour_count', 0)}/{self.config.per_hour_public_cap}")
            self.debug_log.info(f"Max boosts per run: {self.config.max_boosts_per_run}")
            if self.config.hashtag_diversity_enforced:
                self.debug_log.info(f"Hashtag diversity: max {self.config.max_boosts_per_hashtag_per_run} per hashtag per run")
        
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
        
        # Apply quality threshold filtering on raw scores (before normalization)
        if self.config.min_score_threshold > 0:
            qualified_collected = [
                entry for entry in collected 
                if entry["score"] >= self.config.min_score_threshold
            ]
            if self.config.debug_decisions:
                filtered_count = len(collected) - len(qualified_collected)
                self.debug_log.info(f"Quality threshold filter (raw scores): {filtered_count} posts below {self.config.min_score_threshold} threshold")
            collected = qualified_collected
        
        # Check if we have any qualifying content
        if not collected:
            self.log.info("No posts meet the quality threshold. Skipping boost cycle.")
            if self.config.debug_decisions:
                self.debug_log.info("BOOST CYCLE SKIPPED: No qualifying content")
            return

        self._normalize_scores(collected)
        collected.sort(
            key=lambda e: (e["score"], self._created_at(e["status"])),
            reverse=True,
        )
        
        # Debug: Log top candidates after scoring and filtering
        if self.config.debug_decisions:
            self.debug_log.info("=== TOP CANDIDATES AFTER SCORING AND FILTERING ===")
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
                sid_display = str(sid)[:8] + "..." if len(str(sid)) > 8 else str(sid)
                self.debug_log.info(f"--- EVALUATING STATUS {sid_display} ---")
                self.debug_log.info(f"From: {instance_name}, Score: {score:.2f}")
            
            # Step 1: Apply filters on the trending status (before attempting any network calls)
            # Use the trending status directly - it's already a full status object from the remote
            status = trending
            
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
            
            # Step 2: Attempt reblog with federation fallback
            if self.config.debug_decisions:
                self.debug_log.info(f"DECISION: BOOST - Status passes all checks")
                author = status.get("account", {}).get("acct", "unknown")
                content_preview = (status.get("content", "") or "").strip()[:100]
                if len(content_preview) > 97:
                    content_preview = content_preview[:97] + "..."
                self.debug_log.info(f"  Author: {author}")
                self.debug_log.info(f"  Content: {content_preview}")
            
            success, tracked_status = self._attempt_reblog_with_federation_fallback(status, instance_name)
            if not success:
                continue
            
            # Use tracked_status for memory (may be different if federated)
            self._count_public_boost()
            self._remember_status(tracked_status if tracked_status else status)
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

