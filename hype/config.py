import logging
import os
from typing import List

import yaml


class BotAccount:
    server: str
    access_token: str

    def __init__(self, server: str, access_token: str) -> None:
        self.server = server
        self.access_token = access_token

    def __repr__(self) -> str:
        return f"server: {self.server}, access_token: {self.access_token}"


class Instance:
    name: str
    fetch_limit: int
    boost_limit: int

    def __init__(self, name: str, limit: int = None, fetch_limit: int = None, boost_limit: int = None) -> None:
        self.name = name
        # Support legacy 'limit' parameter for backward compatibility
        if limit is not None and fetch_limit is None and boost_limit is None:
            # Legacy mode: single limit means both fetch and boost the same amount
            self.fetch_limit = limit if limit > 0 and limit <= 20 else 20
            self.boost_limit = limit if limit > 0 and limit <= 20 else 20
        else:
            # New mode: separate fetch and boost limits
            self.fetch_limit = fetch_limit if fetch_limit is not None and fetch_limit > 0 and fetch_limit <= 20 else 20
            self.boost_limit = boost_limit if boost_limit is not None and boost_limit > 0 else 4

    @property
    def limit(self):
        """Legacy property for backward compatibility"""
        return self.fetch_limit

    def __repr__(self) -> str:
        if self.fetch_limit == self.boost_limit:
            return f"{self.name} (top {self.fetch_limit})"
        return f"{self.name} (fetch {self.fetch_limit}, boost {self.boost_limit})"


class Config:
    bot_account: BotAccount
    interval: int = 15
    log_level: str = "DEBUG"
    debug_decisions: bool = True
    logfile_path: str = ""
    subscribed_instances: List = []
    filtered_instances: List = ["example.com"]
    profile_prefix: str = "Official hypebot for goingdark.social, automatically boosting top trending posts from selected Mastodon instances:"
    fields: dict = {
        "instance": "https://goingdark.social",
        "code": "https://github.com/goingdark-social/hypebot",
        "automation": "Runs every 15 minutes",
        "about": "Boosts trending posts from curated instances"
    }
    daily_public_cap: int = 96
    per_hour_public_cap: int = 5
    max_boosts_per_run: int = 5
    max_boosts_per_author_per_day: int = 1
    author_diversity_enforced: bool = True
    prefer_media: float = 0
    require_media: bool = False
    skip_sensitive_without_cw: bool = True
    min_reblogs: int = 10
    min_favourites: int = 10
    min_replies: int = 0
    languages_allowlist: list = ["en"]
    state_path: str = "/app/secrets/state.json"
    seen_cache_size: int = 6000
    hashtag_scores: dict = {
        "homelab": 20,
        "selfhosted": 15,
        "privacy": 10,
        "security": 10,
        "cybersecurity": 10,
        "kubernetes": 15,
        "docker": 15
    }
    # Age decay configuration
    age_decay_enabled: bool = False
    age_decay_half_life_hours: float = 24.0  # Hours for score to halve due to age
    # Hashtag diversity configuration  
    hashtag_diversity_enforced: bool = False
    max_boosts_per_hashtag_per_run: int = 1
    # Spam detection configuration
    spam_emoji_penalty: float = 0  # Points to reduce per emoji over the threshold
    spam_emoji_threshold: int = 2  # Number of emojis before penalty applies
    spam_link_penalty: float = 0  # Points to reduce when links are present
    # Quality threshold configuration
    min_score_threshold: float = 0  # Minimum normalized score (0-100) required for boosting
    # Related hashtag scoring configuration
    related_hashtags: dict = {}  # Map hashtag -> {related_term: partial_score_multiplier}
    # Local instance timeline configuration
    local_timeline_enabled: bool = True  # Whether to fetch from local timeline
    local_timeline_fetch_limit: int = 20  # How many posts to fetch from local timeline
    local_timeline_boost_limit: int = 2  # Max boosts from local timeline per run
    local_timeline_min_engagement: int = 1  # Minimum boosts, stars, or comments required

    def __init__(self):
        # Helper method to get config values with environment variable override
        def get_config_value(env_var, config_dict, config_key, default_value, value_type=str):
            """Get configuration value from environment variable, config file, or default."""
            # Check environment variable first
            env_value = os.environ.get(env_var)
            if env_value is not None:
                try:
                    if value_type == bool:
                        return env_value.lower() in ('true', '1', 'yes', 'on')
                    elif value_type == int:
                        return int(env_value)
                    elif value_type == float:
                        return float(env_value)
                    elif value_type == list:
                        # For lists, split by comma
                        return [item.strip() for item in env_value.split(',') if item.strip()]
                    else:
                        return env_value
                except (ValueError, TypeError):
                    logging.getLogger("Config").warning(f"Invalid value for {env_var}: {env_value}, using default")
            
            # Check config file value
            if config_dict and config_dict.get(config_key) is not None:
                return config_dict[config_key]
            
            # Return default
            return default_value

        # auth file containing login info
        auth = "/app/config/auth.yaml"
        # settings file containing subscriptions
        conf = "/app/config/config.yaml"

        # only load auth info
        with open(auth, "r") as configfile:
            config = yaml.load(configfile, Loader=yaml.Loader)
            logging.getLogger("Config").debug("Loading auth info")
            if (
                config
                and config.get("bot_account")
                and config["bot_account"].get("server")
                and config["bot_account"].get("access_token")
            ):
                self.bot_account = BotAccount(
                    server=config["bot_account"]["server"],
                    access_token=config["bot_account"]["access_token"],
                )
            else:
                logging.getLogger("Config").error(config)
                raise ConfigException("Bot account config is incomplete or missing.")

        with open(conf, "r") as configfile:
            config = yaml.load(configfile, Loader=yaml.Loader)
            logging.getLogger("Config").debug("Loading settings")
            if config is None:
                config = {}  # Ensure config is not None for environment variable fallback
                
            # Use environment variables with fallback to config file and defaults
            self.interval = get_config_value("HYPE_INTERVAL", config, "interval", self.interval, int)
            self.log_level = get_config_value("HYPE_LOG_LEVEL", config, "log_level", self.log_level, str)
            self.debug_decisions = get_config_value("HYPE_DEBUG_DECISIONS", config, "debug_decisions", self.debug_decisions, bool)
            self.logfile_path = get_config_value("HYPE_LOGFILE_PATH", config, "logfile_path", self.logfile_path, str)
            self.profile_prefix = get_config_value("HYPE_PROFILE_PREFIX", config, "profile_prefix", self.profile_prefix, str)
            
            # Handle fields configuration (complex object)
            if os.environ.get("HYPE_FIELDS"):
                # Simple key=value,key=value format for environment variables
                fields_str = os.environ.get("HYPE_FIELDS")
                self.fields = {}
                for pair in fields_str.split(','):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        self.fields[key.strip()] = value.strip()
            else:
                self.fields = (
                    {name: value for name, value in config["fields"].items()}
                    if config.get("fields")
                    else self.fields
                )

            # Handle subscribed instances (complex object)
            if os.environ.get("HYPE_SUBSCRIBED_INSTANCES"):
                # Simple name1=limit1,name2=limit2 format for environment variables  
                instances_str = os.environ.get("HYPE_SUBSCRIBED_INSTANCES")
                self.subscribed_instances = []
                for pair in instances_str.split(','):
                    if '=' in pair:
                        name, limit = pair.split('=', 1)
                        try:
                            limit_int = int(limit.strip())
                            self.subscribed_instances.append(Instance(name.strip(), limit=limit_int))
                        except ValueError:
                            logging.getLogger("Config").warning(f"Invalid limit for instance {name}: {limit}")
            else:
                self.subscribed_instances = []
                if config.get("subscribed_instances"):
                    for name, props in config["subscribed_instances"].items():
                        # Support both old format (limit: int) and new format (fetch_limit/boost_limit)
                        if isinstance(props, dict):
                            fetch_limit = props.get("fetch_limit")
                            boost_limit = props.get("boost_limit")
                            limit = props.get("limit")
                            self.subscribed_instances.append(
                                Instance(name, limit=limit, fetch_limit=fetch_limit, boost_limit=boost_limit)
                            )
                        else:
                            # Legacy format: subscribed_instances is a dict with limit as value
                            self.subscribed_instances.append(Instance(name, limit=props))
                else:
                    # No instances configured - use goingdark.social defaults
                    self.subscribed_instances = [
                        Instance("infosec.exchange", fetch_limit=20, boost_limit=5),
                        Instance("mastodon.social", fetch_limit=20, boost_limit=4),
                        Instance("mas.to", fetch_limit=20, boost_limit=5),
                        Instance("fosstodon.org", fetch_limit=20, boost_limit=6),
                        Instance("floss.social", fetch_limit=20, boost_limit=4),
                        Instance("ioc.exchange", fetch_limit=20, boost_limit=3),
                        Instance("mstdn.social", fetch_limit=20, boost_limit=2)
                    ]

            self.filtered_instances = get_config_value("HYPE_FILTERED_INSTANCES", config, "filtered_instances", self.filtered_instances, list)
            if isinstance(self.filtered_instances, list) and config.get("filtered_instances"):
                # If from config file, it's a list of strings, keep as is
                if not os.environ.get("HYPE_FILTERED_INSTANCES"):
                    self.filtered_instances = [name for name in config["filtered_instances"]]

            # Basic configuration parameters with environment variable support
            self.daily_public_cap = get_config_value("HYPE_DAILY_PUBLIC_CAP", config, "daily_public_cap", self.daily_public_cap, int)
            self.per_hour_public_cap = get_config_value("HYPE_PER_HOUR_PUBLIC_CAP", config, "per_hour_public_cap", self.per_hour_public_cap, int)
            self.max_boosts_per_run = get_config_value("HYPE_MAX_BOOSTS_PER_RUN", config, "max_boosts_per_run", self.max_boosts_per_run, int)
            self.max_boosts_per_author_per_day = get_config_value("HYPE_MAX_BOOSTS_PER_AUTHOR_PER_DAY", config, "max_boosts_per_author_per_day", self.max_boosts_per_author_per_day, int)
            self.author_diversity_enforced = get_config_value("HYPE_AUTHOR_DIVERSITY_ENFORCED", config, "author_diversity_enforced", self.author_diversity_enforced, bool)
            
            # Handle prefer_media with special bool/float logic
            prefer_media_env = os.environ.get("HYPE_PREFER_MEDIA")
            if prefer_media_env is not None:
                if prefer_media_env.lower() in ('true', '1', 'yes', 'on'):
                    self.prefer_media = 1
                elif prefer_media_env.lower() in ('false', '0', 'no', 'off'):
                    self.prefer_media = 0
                else:
                    try:
                        self.prefer_media = float(prefer_media_env)
                    except ValueError:
                        self.prefer_media = self.prefer_media
            else:
                pm = config.get("prefer_media", self.prefer_media)
                if isinstance(pm, bool):
                    self.prefer_media = 1 if pm else 0
                else:
                    try:
                        self.prefer_media = float(pm)
                    except (TypeError, ValueError):
                        self.prefer_media = self.prefer_media
                        
            self.require_media = get_config_value("HYPE_REQUIRE_MEDIA", config, "require_media", self.require_media, bool)
            self.skip_sensitive_without_cw = get_config_value("HYPE_SKIP_SENSITIVE_WITHOUT_CW", config, "skip_sensitive_without_cw", self.skip_sensitive_without_cw, bool)
            self.min_reblogs = get_config_value("HYPE_MIN_REBLOGS", config, "min_reblogs", self.min_reblogs, int)
            self.min_favourites = get_config_value("HYPE_MIN_FAVOURITES", config, "min_favourites", self.min_favourites, int)
            self.min_replies = get_config_value("HYPE_MIN_REPLIES", config, "min_replies", self.min_replies, int)
            self.languages_allowlist = get_config_value("HYPE_LANGUAGES_ALLOWLIST", config, "languages_allowlist", self.languages_allowlist, list)
            self.state_path = get_config_value("HYPE_STATE_PATH", config, "state_path", self.state_path, str)
            self.seen_cache_size = get_config_value("HYPE_SEEN_CACHE_SIZE", config, "seen_cache_size", self.seen_cache_size, int)
            
            # Handle hashtag_scores (complex object) 
            hashtag_scores_env = os.environ.get("HYPE_HASHTAG_SCORES")
            if hashtag_scores_env:
                # Simple tag1=score1,tag2=score2 format for environment variables
                self.hashtag_scores = {}
                for pair in hashtag_scores_env.split(','):
                    if '=' in pair:
                        tag, score = pair.split('=', 1)
                        try:
                            self.hashtag_scores[tag.strip().lower()] = float(score.strip())
                        except ValueError:
                            logging.getLogger("Config").warning(f"Invalid score for hashtag {tag}: {score}")
            else:
                config_hashtag_scores = config.get("hashtag_scores")
                if config_hashtag_scores:
                    self.hashtag_scores = {
                        k.lower(): float(v)  # Changed to float to support negative values
                        for k, v in config_hashtag_scores.items()
                    }
                # If config doesn't specify hashtag_scores, keep the default from class attribute
                
            # Age decay configuration
            self.age_decay_enabled = get_config_value("HYPE_AGE_DECAY_ENABLED", config, "age_decay_enabled", self.age_decay_enabled, bool)
            self.age_decay_half_life_hours = get_config_value("HYPE_AGE_DECAY_HALF_LIFE_HOURS", config, "age_decay_half_life_hours", self.age_decay_half_life_hours, float)
            
            # Hashtag diversity configuration
            self.hashtag_diversity_enforced = get_config_value("HYPE_HASHTAG_DIVERSITY_ENFORCED", config, "hashtag_diversity_enforced", self.hashtag_diversity_enforced, bool)
            self.max_boosts_per_hashtag_per_run = get_config_value("HYPE_MAX_BOOSTS_PER_HASHTAG_PER_RUN", config, "max_boosts_per_hashtag_per_run", self.max_boosts_per_hashtag_per_run, int)
            
            # Spam detection configuration
            self.spam_emoji_penalty = get_config_value("HYPE_SPAM_EMOJI_PENALTY", config, "spam_emoji_penalty", self.spam_emoji_penalty, float)
            self.spam_emoji_threshold = get_config_value("HYPE_SPAM_EMOJI_THRESHOLD", config, "spam_emoji_threshold", self.spam_emoji_threshold, int)
            self.spam_link_penalty = get_config_value("HYPE_SPAM_LINK_PENALTY", config, "spam_link_penalty", self.spam_link_penalty, float)
            
            # Quality threshold configuration
            self.min_score_threshold = get_config_value("HYPE_MIN_SCORE_THRESHOLD", config, "min_score_threshold", self.min_score_threshold, float)
            
            # Related hashtag scoring configuration (complex object - only from config file for now)
            self.related_hashtags = config.get("related_hashtags", self.related_hashtags) or {}
            
            # Local timeline configuration
            self.local_timeline_enabled = get_config_value("HYPE_LOCAL_TIMELINE_ENABLED", config, "local_timeline_enabled", self.local_timeline_enabled, bool)
            self.local_timeline_fetch_limit = get_config_value("HYPE_LOCAL_TIMELINE_FETCH_LIMIT", config, "local_timeline_fetch_limit", self.local_timeline_fetch_limit, int)
            self.local_timeline_boost_limit = get_config_value("HYPE_LOCAL_TIMELINE_BOOST_LIMIT", config, "local_timeline_boost_limit", self.local_timeline_boost_limit, int)
            self.local_timeline_min_engagement = get_config_value("HYPE_LOCAL_TIMELINE_MIN_ENGAGEMENT", config, "local_timeline_min_engagement", self.local_timeline_min_engagement, int)



class ConfigException(Exception):
    pass
