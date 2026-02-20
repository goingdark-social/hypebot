![](./res/hype_header.png)

# hype

A Mastodon bot that boosts trending posts from other instances into your timeline, helping you discover content across the federated social web.

## Why

For smaller Mastodon instances, the local timeline can be quite empty and trends often don't work due to limited activity. Rather than manually checking other instances, this bot lets you subscribe to multiple Mastodon-compatible servers to fetch trending posts and boost them to your timeline—enhancing discoverability of accounts, people, and topics across the Fediverse.

## Installation

### Docker Compose

```yaml
version: "3"
services:
  hype:
    image: ghcr.io/goingdark-social/hypebot:latest
    volumes:
      - ./config:/app/config
```

Replace `latest` with a specific version (e.g., `v0.4.0`).

Pull requests publish images tagged with the PR number and commit SHA:

```bash
docker pull ghcr.io/goingdark-social/hypebot:pr-123
docker pull ghcr.io/goingdark-social/hypebot:sha-abcdef1
```

### Custom UID/GID

The Docker image supports customizable UID/GID for security and compatibility:

```bash
docker build --build-arg USER_UID=2000 --build-arg USER_GID=3000 -t hypebot-custom .
docker build --build-arg USER_NAME=mybot --build-arg USER_UID=1500 -t hypebot-named .
```

**Arguments:**
- `USER_UID` - User ID (default: 1000)
- `USER_GID` - Group ID (default: 1000)
- `USER_NAME` - Username (default: hype)

### Kubernetes

```bash
kubectl apply -f deploy.yaml
```

Includes `runAsNonRoot: true`, security context with dropped capabilities, resource limits, and proper volume mounts.

## Configuration

Create `config.yaml` and `auth.yaml` in `./config/`:

`auth.yaml`:
```yaml
bot_account:
  server: "mastodon.example.com"
  access_token: "Create a new application in your bot account at Preferences -> Development"
```

`config.yaml`:
```yaml
interval: 30

profile_prefix: "Boosting trending posts from:"

fields:
  instance: https://mastodon.example.com
  code: "https://github.com/goingdark-social/hypebot"
  automation: "Runs every 30 minutes"
  about: "Boosts trending posts from curated instances"

subscribed_instances:
  chaos.social:
    fetch_limit: 20
    boost_limit: 4
  mastodon.social:
    fetch_limit: 15
    boost_limit: 3
  fosstodon.org:
    limit: 5

filtered_instances:
  - example.com

daily_public_cap: 96
per_hour_public_cap: 6
max_boosts_per_run: 8
max_boosts_per_author_per_day: 1
author_diversity_enforced: true

prefer_media: 1
require_media: true
min_reblogs: 10
min_favourites: 10

languages_allowlist:
  - en

hashtag_scores:
  python: 10
  rust: 5

local_timeline_enabled: true
local_timeline_fetch_limit: 20
local_timeline_boost_limit: 4
local_timeline_min_engagement: 1

spam_emoji_penalty: 0.5
spam_emoji_threshold: 2
spam_link_penalty: 0.3

debug_decisions: true
log_level: "DEBUG"
```

## Features

### Multi-Instance Trending Posts
- Boost trending posts from multiple Mastodon instances
- Configure separate fetch and boost limits per instance
- Filter posts from specific instances entirely

### Local Timeline Boosting
- Optionally boost posts from your own instance's local timeline
- Only boosts posts from the same day with minimum engagement
- Great for promoting local community content on smaller instances

### Language Filtering
- Filter posts by language using Mastodon metadata
- Or use automatic content-based detection with langdetect
- Skips posts with undetectable or non-allowed languages

### Quality Controls
- **Hashtag scoring**: Assign weights to prioritize certain hashtags
- **Media preferences**: Prefer or require posts with media attachments
- **Engagement thresholds**: Skip posts with too few reblogs or favorites
- **Age decay**: Reduce score of older posts
- **Minimum score threshold**: Skip posts below a score cutoff

### Spam & Duplicate Detection
- **Spam detection**: Penalize posts with excessive emojis or links
- **Duplicate avoidance**: Track canonical URLs with configurable cache
- **Author diversity**: Prevent same author from dominating your timeline (24h rolling window)

### Proactive Federation
- Automatically federates unfederated trending posts
- Uses `search_v2(resolve=True)` before boosting to seed federation

### Debug Logging
- Comprehensive decision tracing with `debug_decisions: true`
- Detailed scoring breakdown: hashtag scores, engagement, media bonus
- Filtering decisions with specific reasons
- Persistent logging to file with `logfile_path`

### Flexible Deployment
- Configurable refresh interval (default: 15 minutes)
- Hourly and daily public boost caps
- State persistence for continuity across restarts
- Docker and Kubernetes support

## Credits

This project is a fork of [v411e/hype](https://github.com/v411e/hype). Significant enhancements have been made including local timeline boosting, language filtering, hashtag scoring, spam detection, quality controls, author diversity enforcement, and debug logging.

---

