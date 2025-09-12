import logging
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
    limit: int

    def __init__(self, name: str, limit: int) -> None:
        self.name = name
        self.limit = limit if limit > 0 and limit <= 20 else 20

    def __repr__(self) -> str:
        return f"{self.name} (top {self.limit})"


class Config:
    bot_account: BotAccount
    interval: int = 60
    log_level: str = "INFO"
    subscribed_instances: List = []
    filtered_instances: List = []
    profile_prefix: str = ""
    fields: dict = {}
    daily_public_cap: int = 48
    per_hour_public_cap: int = 1
    max_boosts_per_run: int = 5
    max_boosts_per_author_per_day: int = 1
    author_diversity_enforced: bool = True
    prefer_media: float = 0
    require_media: bool = True
    skip_sensitive_without_cw: bool = True
    min_reblogs: int = 0
    min_favourites: int = 0
    languages_allowlist: list = []
    state_path: str = "/app/secrets/state.json"
    seen_cache_size: int = 6000
    hashtag_scores: dict = {}

    def __init__(self):
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
            if config:
                self.interval = (
                    config["interval"] if config.get("interval") else self.interval
                )
                self.log_level = (
                    config["log_level"] if config.get("log_level") else self.log_level
                )

                self.profile_prefix = (
                    config["profile_prefix"]
                    if config.get("profile_prefix")
                    else self.profile_prefix
                )

                self.fields = (
                    {name: value for name, value in config["fields"].items()}
                    if config.get("fields")
                    else {}
                )

                self.subscribed_instances = (
                    [
                        Instance(name, props["limit"])
                        for name, props in config["subscribed_instances"].items()
                    ]
                    if config.get("subscribed_instances")
                    else []
                )

                self.filtered_instances = (
                    [
                        name for name in config["filtered_instances"]
                    ]
                    if config.get("filtered_instances")
                    else []
                )

                self.daily_public_cap = int(
                    config.get("daily_public_cap", self.daily_public_cap)
                )
                self.per_hour_public_cap = int(
                    config.get("per_hour_public_cap", self.per_hour_public_cap)
                )
                self.max_boosts_per_run = int(
                    config.get("max_boosts_per_run", self.max_boosts_per_run)
                )
                self.max_boosts_per_author_per_day = int(
                    config.get(
                        "max_boosts_per_author_per_day",
                        self.max_boosts_per_author_per_day,
                    )
                )
                self.author_diversity_enforced = bool(
                    config.get(
                        "author_diversity_enforced",
                        self.author_diversity_enforced,
                    )
                )
                pm = config.get("prefer_media", self.prefer_media)
                if isinstance(pm, bool):
                    self.prefer_media = 1 if pm else 0
                else:
                    try:
                        self.prefer_media = float(pm)
                    except (TypeError, ValueError):
                        self.prefer_media = self.prefer_media
                self.require_media = bool(
                    config.get("require_media", self.require_media)
                )
                self.skip_sensitive_without_cw = bool(
                    config.get(
                        "skip_sensitive_without_cw", self.skip_sensitive_without_cw
                    )
                )
                self.min_reblogs = int(
                    config.get("min_reblogs", self.min_reblogs)
                )
                self.min_favourites = int(
                    config.get("min_favourites", self.min_favourites)
                )
                self.languages_allowlist = config.get(
                    "languages_allowlist", self.languages_allowlist
                ) or []
                self.state_path = config.get("state_path", self.state_path)
                self.seen_cache_size = int(
                    config.get("seen_cache_size", self.seen_cache_size)
                )
                self.hashtag_scores = {
                    k.lower(): int(v)
                    for k, v in (config.get("hashtag_scores") or {}).items()
                }


class ConfigException(Exception):
    pass
