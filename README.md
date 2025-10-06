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

### Custom User ID/Group ID

The Docker image supports customizable UID/GID for security and compatibility with different deployment environments:

```bash
# Build with custom UID/GID (useful for matching host user permissions)
docker build --build-arg USER_UID=2000 --build-arg USER_GID=3000 -t hypebot-custom .

# Build with custom user name (default is 'hype')
docker build --build-arg USER_NAME=mybot --build-arg USER_UID=1500 -t hypebot-named .
```

**Build Arguments:**
- `USER_UID` - User ID (default: 1000)
- `USER_GID` - Group ID (default: 1000) 
- `USER_NAME` - Username (default: hype)

### Kubernetes Deployment

For Kubernetes deployments with Pod Security Standards, use the provided `deploy.yaml`:

```bash
kubectl apply -f deploy.yaml
```

The deployment includes:
- `runAsNonRoot: true` for security
- Numeric UID/GID specification for compatibility
- Security context with dropped capabilities
- Resource limits and requests
- Proper volume mounts for config, secrets, and logs

**Important for Kubernetes:** The image uses numeric UID:GID format (`USER 1000:1000`) instead of named users to ensure compatibility with `runAsNonRoot: true` security policies.

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
# Refresh interval in minutes (default: 15)
interval: 15

# Text to add to the bot profile befor the list of subscribed servers
profile_prefix: "I am boosting trending posts from:"

# profile fields to fill in
fields:
  code: https://github.com/goingdark-social/hypebot
  operator: "YOUR HANDLE HERE"

# Define subscribed instances with fetch and boost limits
# fetch_limit: how many trending posts to fetch from the instance (max 20)
# boost_limit: how many of those to actually boost per run
# Legacy format (single limit) still supported for backward compatibility
subscribed_instances:
  chaos.social:
    fetch_limit: 20  # Fetch top 20 trending posts
    boost_limit: 4   # But only boost up to 4 best posts
  mastodon.social:
    fetch_limit: 15  # Fetch top 15 trending posts
    boost_limit: 3   # But only boost up to 3 best posts
  # Legacy format still works:
  fosstodon.org:
    limit: 5  # Fetch and boost up to 5 posts

# Local Timeline Configuration
# Enable boosting from your own instance's local timeline
local_timeline_enabled: false  # Set to true to enable local timeline boosting
local_timeline_fetch_limit: 20  # How many posts to fetch from local timeline
local_timeline_boost_limit: 2  # Max boosts from local timeline per run
local_timeline_min_engagement: 1  # Minimum total engagement (boosts + stars + comments) required

# Filter posts from specific instances
filtered_instances:
  - example.com

daily_public_cap: 48
per_hour_public_cap: 6
max_boosts_per_run: 8
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

# Spam Detection Options
spam_emoji_penalty: 1.0  # Points to reduce per emoji over the threshold
spam_emoji_threshold: 2  # Number of emojis before penalty applies
spam_link_penalty: 0.5   # Points to reduce when links are present

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

### Spam Detection

The bot includes configurable spam detection to reduce scores for potentially promotional content:

- `spam_emoji_penalty` - Points to reduce per emoji over the threshold (default: 0, disabled)
- `spam_emoji_threshold` - Number of emojis before penalty applies (default: 2)
- `spam_link_penalty` - Points to reduce when links are detected in posts (default: 0, disabled)

When enabled, posts with excessive emojis or links receive score penalties to reduce their boost priority. This helps avoid promoting content that may be spam-like or overly promotional.

### Local Timeline Boosting

The bot can optionally boost posts from your own instance's local timeline, in addition to trending posts from remote instances. This feature helps promote local content that has already gained some community engagement.

**How it works:**
- When `local_timeline_enabled: true`, the bot fetches posts from your instance's local timeline
- Posts are filtered to include only those from the current day (same day as the boost run)
- Posts must have minimum engagement: at least `local_timeline_min_engagement` total interactions (reblogs + favorites + replies)
- The bot respects `local_timeline_boost_limit` to avoid over-promoting local content
- Local posts are scored and ranked alongside trending posts from remote instances

**Configuration:**
```yaml
local_timeline_enabled: true  # Enable local timeline boosting
local_timeline_fetch_limit: 20  # How many local posts to fetch
local_timeline_boost_limit: 2  # Max boosts from local timeline per run
local_timeline_min_engagement: 1  # Minimum total engagement required
```

This feature is useful for smaller instances where local content may not trend globally, but deserves visibility within the community.

### Proactive Federation

The bot automatically federates unfederated trending posts from remote instances. When a trending post is not yet in your local instance's database, the bot will actively federate it using `search_v2(resolve=True)` before boosting. This helps seed federation by bringing trending content from other instances into your local timeline, which is especially useful for smaller instances that want to increase content discovery for their users.

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
- Optionally boost from your own instance's local timeline with engagement filtering
- Fetch larger candidate pools (up to 20 per instance) while boosting fewer posts for diversity
- Separate fetch_limit and boost_limit per instance for fine-grained control
- Update bot profile with list of subscribed instances
- Rank collected posts using hashtags, engagement, and optional media preference
- Normalize scores on a 0–100 scale and favor newer posts when scores tie
- Skip duplicates across instances by tracking canonical URLs with a configurable cache
- Enforce hourly and daily caps on public boosts
- Limit boosts per instance per run and for any single author per day
- Skip reposts and filter posts without media or missing content warnings
- Skip posts with too few reblogs or favourites
- Prioritize posts containing weighted hashtags
- Read timestamps whether they're strings or Python datetimes
- Default 15-minute interval for frequent, smaller boost cycles
- Local timeline filtering: only boost posts from the same day with minimum engagement

## Branches

Work starts on `develop`. When it's merged into `main` and deleted, a workflow recreates `develop` from `main`. If that job fails, create the branch manually.

---
 
