# Environment Variable Configuration Guide

HypeBot now supports configuration via environment variables, which is particularly useful for Kubernetes deployments where ConfigMaps can be used to set environment variables.

## Environment Variable Support

All configuration parameters can now be overridden using environment variables with the `HYPE_` prefix. The precedence order is:

1. Environment variables (highest priority)
2. Configuration file values 
3. Default values (lowest priority)

## Available Environment Variables

### Basic Configuration
- `HYPE_INTERVAL` - Refresh interval in minutes (default: 15)
- `HYPE_LOG_LEVEL` - Logging level (default: "INFO")
- `HYPE_DEBUG_DECISIONS` - Enable detailed decision logging (default: false)
- `HYPE_LOGFILE_PATH` - Path to log file (default: "")
- `HYPE_PROFILE_PREFIX` - Text to add before instance list in profile (default: "")

### Boost Limits
- `HYPE_DAILY_PUBLIC_CAP` - Maximum boosts per day (default: 48)
- `HYPE_PER_HOUR_PUBLIC_CAP` - Maximum boosts per hour (default: 1)
- `HYPE_MAX_BOOSTS_PER_RUN` - Maximum boosts per cycle (default: 5)
- `HYPE_MAX_BOOSTS_PER_AUTHOR_PER_DAY` - Max boosts per author within a 24-hour rolling window (default: 1)

### Content Filtering
- `HYPE_REQUIRE_MEDIA` - Only boost posts with media attachments (default: true)
- `HYPE_SKIP_SENSITIVE_WITHOUT_CW` - Skip sensitive posts without content warnings (default: true)
- `HYPE_MIN_REBLOGS` - Minimum reblogs required (default: 0)
- `HYPE_MIN_FAVOURITES` - Minimum favourites required (default: 0)
- `HYPE_MIN_REPLIES` - **NEW**: Minimum replies required (default: 0)

### Quality and Scoring
- `HYPE_MIN_SCORE_THRESHOLD` - Minimum score threshold for boosting (default: 0)
- `HYPE_PREFER_MEDIA` - Bonus points for media content (default: 0)
- `HYPE_AGE_DECAY_ENABLED` - Enable age-based score decay (default: false)
- `HYPE_AGE_DECAY_HALF_LIFE_HOURS` - Hours for score to halve (default: 24.0)

### Diversity Controls
- `HYPE_AUTHOR_DIVERSITY_ENFORCED` - Enforce author diversity using a 24-hour rolling window (default: true)
- `HYPE_HASHTAG_DIVERSITY_ENFORCED` - Enforce hashtag diversity (default: false)
- `HYPE_MAX_BOOSTS_PER_HASHTAG_PER_RUN` - Max boosts per hashtag per run (default: 1)

**Note on Author Diversity**: When enabled, the bot tracks the timestamp of when each author was last boosted and prevents the same author from being boosted again until 24 hours have elapsed. This is a true rolling window, not a calendar-day reset, ensuring diverse content even across day boundaries.

### Spam Detection
- `HYPE_SPAM_EMOJI_PENALTY` - Points deducted per excess emoji (default: 0)
- `HYPE_SPAM_EMOJI_THRESHOLD` - Emoji count before penalty applies (default: 2)
- `HYPE_SPAM_LINK_PENALTY` - Points deducted for posts with links (default: 0)

### Advanced Configuration
- `HYPE_LANGUAGES_ALLOWLIST` - Comma-separated list of allowed languages (default: [])
- `HYPE_STATE_PATH` - Path to state file (default: "/app/secrets/state.json")
- `HYPE_SEEN_CACHE_SIZE` - Size of seen posts cache (default: 6000)

### Complex Configuration via Environment Variables

For complex objects like hashtag scores, subscribed instances, and fields, use these formats:

#### Hashtag Scores
```bash
HYPE_HASHTAG_SCORES="python=10,docker=8,kubernetes=9,homelab=7"
```

#### Subscribed Instances
```bash
HYPE_SUBSCRIBED_INSTANCES="mastodon.social=5,chaos.social=3,fosstodon.org=5"
```

#### Profile Fields
```bash
HYPE_FIELDS="code=https://github.com/goingdark-social/hypebot,operator=@admin@mastodon.social"
```

#### Filtered Instances
```bash
HYPE_FILTERED_INSTANCES="spam.instance,blocked.instance"
```

#### Languages Allowlist
```bash
HYPE_LANGUAGES_ALLOWLIST="en,de,fr"
```

## Boolean Values

For boolean environment variables, the following values are considered `true`:
- `true`, `1`, `yes`, `on` (case-insensitive)

All other values are considered `false`.

## Example Kubernetes ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: hypebot-config
data:
  HYPE_INTERVAL: "30"
  HYPE_MIN_REPLIES: "2"
  HYPE_DAILY_PUBLIC_CAP: "24"
  HYPE_PER_HOUR_PUBLIC_CAP: "2"
  HYPE_REQUIRE_MEDIA: "false"
  HYPE_MIN_SCORE_THRESHOLD: "5"
  HYPE_HASHTAG_SCORES: "homelab=10,selfhosted=8,docker=9"
  HYPE_SUBSCRIBED_INSTANCES: "mastodon.social=3,chaos.social=5"
```

## Migration from Config Files

Existing `config.yaml` files continue to work unchanged. Environment variables simply override specific values when set, allowing for hybrid configurations where most settings come from the config file but specific values are overridden via environment variables.

## New Minimum Replies Feature

The `min_replies` parameter (environment variable: `HYPE_MIN_REPLIES`) allows you to filter out posts that don't have enough community engagement in the form of replies. This helps ensure that boosted content has generated actual discussion.

- **Default**: 0 (disabled)
- **Recommended for quality filtering**: 2-5 replies minimum
- **Strict quality control**: 10+ replies minimum

Posts with fewer replies than the threshold will be filtered out before scoring and boosting consideration.

## Proactive Federation

The bot automatically federates unfederated trending posts from remote instances. When a trending post is not yet in your local instance's database, the bot will actively federate it using `search_v2(resolve=True)` before boosting.

### How It Works

The bot uses the following flow for each trending post:
1. Try direct reblog (works if post is already in local database)
2. If reblog returns 404 (post not in local DB), use `search_v2(resolve=True)` to federate it
3. Retry reblog after successful federation

This helps seed federation by pulling in trending content from remote instances, which is especially useful for smaller instances that want to increase content discovery for their users.

### Error Handling

The bot includes comprehensive error handling for federation attempts:
- **401 Unauthorized**: Logged as `token-scope-missing` (federation skipped gracefully)
- **Empty results**: Logged as `remote-200-local-resolve-empty` (post exists remotely but couldn't be federated)
- **API errors**: Logged with specific error codes for debugging
- **Network errors**: Handled gracefully, bot continues with next post

All federation failures are logged with clear reason codes for operational monitoring.