![](./res/hype_header.png)

# hype

This Mastodon bot pulls trending posts from chosen instances, ranks them, and boosts the top results to your timeline. You decide which instances it fetches and how much you want to see per instance.

## Why

For smaller instances the local timeline is rather empty. This is why trends simply do not work on those instances: There is just not enough activity. Instead of manually checking out other instances this bot allows to subscribe to a multitude of different mastodon compatible servers to fetch trending posts and repost them to your current server helping discoverability of accounts, people and topics within the federated social web.

## Installation

Deploy with docker-compose

```yaml
version: "3"
services:
  hype:
    image: ghcr.io/goingdark-social/hypebot:v0.1.0
    volumes:
      - ./config:/app/config
```
Replace `v0.1.0` with the release you want to run.

Pull requests publish images tagged with the PR number and commit. For testing you can pull them from the registry, for example:

```
docker pull ghcr.io/goingdark-social/hypebot:pr-123
docker pull ghcr.io/goingdark-social/hypebot:sha-abcdef1
```

## Configuration

Create a `config.yaml` and a `auth.yaml` file in `./config/`. Enter the credentials of your bot-account into `auth.yaml`. You can define which servers to follow and how often to fetch new posts as well as how to automatically change your profile in config.yaml. See the examples below:

`auth.yaml`:

```yaml
# Credentials for your bot account
bot_account:
  server: "mastodon.example.com"
  access_token: "Create a new application in your bot account at Preferences -> Development"
```

`config.yaml`

```yaml
# Refresh interval in minutes
interval: 60

# Text to add to the bot profile befor the list of subscribed servers
profile_prefix: "I am boosting trending posts from:"

# profile fields to fill in
fields:
  code: https://github.com/v411e/hype
  operator: "YOUR HANDLE HERE"

# Define subscribed instances and
# their individual limit (top n trending posts)
# which is again limited by the API to max 20
subscribed_instances:
  chaos.social:
    limit: 20
  mastodon.social:
    limit: 5

# Filter posts from specific instances
filtered_instances:
  - example.com

daily_public_cap: 48
per_hour_public_cap: 1
max_boosts_per_run: 5
max_boosts_per_author_per_day: 1
author_diversity_enforced: true
prefer_media: 1
require_media: true
skip_sensitive_without_cw: true
min_reblogs: 0
min_favourites: 0
languages_allowlist:
  - en
  - sv
state_path: "/app/secrets/state.json"
seen_cache_size: 6000
hashtag_scores:
  python: 10
  rust: 5

# Debug and Logging Options
log_level: "INFO"  # Set to "DEBUG" for detailed logging
debug_decisions: false  # Enable detailed decision tracing and reasoning
logfile_path: ""  # Path to log file for persistent logging (e.g., "/app/logs/hypebot.log")
```

`min_reblogs` and `min_favourites` let you ignore posts that haven't gained enough traction yet.
`seen_cache_size` sets how many posts the bot keeps in memory to avoid boosting the same thing twice. A bigger cache catches more duplicates but uses more RAM and takes longer to search.
`hashtag_scores` lets you push posts with certain hashtags to the front by assigning weights.
`prefer_media` adds the given bonus to posts with attachments; set to `true` for a default of `1`.
`author_diversity_enforced` respects `max_boosts_per_author_per_day` when enabled.
`max_boosts_per_run` limits how many posts get boosted in each run.
`max_boosts_per_author_per_day` stops the bot from boosting the same author over and over.

### Debug Logging

For detailed traceability of the bot's decisions, you can enable debug logging:

- `debug_decisions: true` - Enables comprehensive logging of each decision made during the boost process
- `logfile_path: "/path/to/logfile.log"` - Enables persistent logging to a file in addition to console output
- `log_level: "DEBUG"` - Sets the logging level to show debug messages

When `debug_decisions` is enabled, the bot will log:
- Detailed scoring breakdown for each post (hashtag scores, engagement, media bonus)
- Filtering decisions with specific reasons (content rules, seen status, instance filters)
- Instance fetching results and counts
- Complete boost cycle summaries with statistics

Example debug output:
```
STATUS 12345678... | SCORING: 21.48
  Hashtags: ['python', 'mastodon']
  Tag scores: [10, 5] = 15
  Reblogs: 5 -> 3.58
  Favourites: 10 -> 2.40
  Media bonus: 0.5 (has_media: True)
  Total: 15 + 3.58 + 2.40 + 0.5 = 21.48
STATUS 12345678... | FILTER CHECK: KEEP
  Media attachments: 1
  Skip no media: False (require_media: False)
  Language: 'en', allowlist: ['en']
  Skip language: False
DECISION: BOOST - Status passes all checks
```

**Migration note**: The `rotate_instances` option has been removed. The bot now checks every subscribed instance each run, so older configs should drop this field.

## Features

- Boost trending posts from other Mastodon instances
- Update bot profile with list of subscribed instances
- Rank collected posts using hashtags, engagement, and optional media preference
- Normalize scores on a 0–100 scale and favor newer posts when scores tie
- Skip duplicates across instances by tracking canonical URLs with a configurable cache
- Enforce hourly and daily caps on public boosts
- Limit boosts for any single author per day
- Skip reposts and filter posts without media or missing content warnings
- Skip posts with too few reblogs or favourites
- Prioritize posts containing weighted hashtags
- Read timestamps whether they're strings or Python datetimes

## Branches

Work starts on `develop`. When it's merged into `main` and deleted, a workflow recreates `develop` from `main`. If that job fails, create the branch manually.

---
 
