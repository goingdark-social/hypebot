# Boosting Improvements Configuration Guide

This document explains how to use the new quality-focused boosting features added to address the requirements for smaller, more frequent boosts with higher quality content.

## Quality Threshold Feature

The `min_score_threshold` setting allows you to enforce a minimum quality standard for posts before they can be boosted.

### Configuration

```yaml
# config.yaml
min_score_threshold: 5  # Only boost posts with raw score >= 5
```

### How It Works

- Posts are scored based on engagement (reblogs, favorites), hashtags, media, etc.
- The quality threshold is applied to **raw scores** (before normalization)
- If no posts meet the threshold, the entire boost cycle is skipped
- This prevents boosting "the best of the worst" posts when all content is low quality

### Typical Score Ranges

- Low engagement (1 reblog, 1 favorite): ~2 points
- Medium engagement (10 reblogs, 5 favorites): ~6 points  
- High engagement (100 reblogs, 50 favorites): ~13 points
- Hashtag bonuses can add significant points based on your configuration

### Recommended Settings

- **Conservative**: `min_score_threshold: 3` - filters out very low engagement
- **Moderate**: `min_score_threshold: 5` - requires decent engagement
- **Strict**: `min_score_threshold: 8` - only high-quality content

## Related Hashtag Scoring

The `related_hashtags` feature allows posts to earn partial hashtag bonuses for related content, even without the exact hashtag.

### Configuration

```yaml
# config.yaml
hashtag_scores:
  homelab: 10
  docker: 8
  python: 12

related_hashtags:
  homelab:
    self-hosting: 0.5      # 50% of homelab score (5 points)
    selfhosted: 0.4        # 40% of homelab score (4 points)
    server: 0.3            # 30% of homelab score (3 points)
  docker:
    container: 0.6         # 60% of docker score (4.8 points)
    containerization: 0.4  # 40% of docker score (3.2 points)
  python:
    programming: 0.3       # 30% of python score (3.6 points)
    coding: 0.25           # 25% of python score (3 points)
```

### How It Works

- Content is scanned for related terms in both post text and existing hashtags
- Only applies when the main hashtag is NOT already present
- Case-insensitive matching
- Only one bonus per main hashtag (first match wins)
- Only applies bonuses for positive base hashtag scores

### Example

A post about "self-hosting applications" without #homelab would get:
- Base engagement score: ~6 points
- Related hashtag bonus: 5 points (50% of homelab's 10 points)
- **Total**: ~11 points

## Achieving Smaller, More Frequent Boosts

To implement the "smaller bursts more often" pattern mentioned in the issue:

### Current Configuration (Large, Infrequent Bursts)
```yaml
interval: 60              # Every 60 minutes
max_boosts_per_run: 5     # Up to 5 posts per cycle
min_score_threshold: 0    # No quality filter
```

### Recommended Configuration (Smaller, Frequent Bursts)
```yaml
interval: 15              # Every 15 minutes (4x more frequent)
max_boosts_per_run: 2     # Only 1-2 posts per cycle
min_score_threshold: 5    # Quality threshold
per_hour_public_cap: 4    # Total hourly limit remains the same
```

This approach:
- ✅ Boosts fewer posts at a time (smaller bursts)
- ✅ Runs more frequently (every 15 vs 60 minutes)
- ✅ Maintains the same total hourly output
- ✅ Enforces quality standards
- ✅ Skips cycles when no quality content is available

## Complete Example Configuration

```yaml
# config.yaml - Quality-focused smaller bursts
interval: 20                    # Check every 20 minutes
max_boosts_per_run: 2          # Max 2 posts per cycle
min_score_threshold: 5         # Quality threshold
per_hour_public_cap: 6         # 6 posts per hour max
daily_public_cap: 48          # 48 posts per day max

# Hashtag scoring with related terms
hashtag_scores:
  homelab: 10
  selfhosted: 8
  docker: 8
  kubernetes: 9
  python: 7
  opensource: 6

related_hashtags:
  homelab:
    self-hosting: 0.5
    selfhosted: 0.6
    server: 0.3
    nas: 0.4
  docker:
    container: 0.6
    containerization: 0.4
    k8s: 0.3
  python:
    programming: 0.3
    coding: 0.25
    development: 0.3

subscribed_instances:
  - name: "mastodon.social"
    limit: 3
  - name: "chaos.social"  
    limit: 3
```

This configuration will:
- Check for content every 20 minutes
- Boost up to 2 high-quality posts per cycle
- Skip cycles when no posts meet the quality threshold
- Give bonuses for related content (e.g., "self-hosting" gets homelab bonus)
- Maintain natural-feeling boost patterns instead of large dumps