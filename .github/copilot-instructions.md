# HypeBot - Mastodon Trending Posts Bot

HypeBot is a Python 3 Mastodon bot that fetches trending posts from multiple Mastodon instances, ranks them, and boosts the top results to your timeline. It helps smaller instances discover content from the broader Fediverse.

Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.

## Working Effectively

### Initial Setup
- Install Python dependencies: `pip install -r requirements.txt`
  - Takes 1-2 seconds on subsequent runs (all already cached)
  - Fresh install takes ~2-5 seconds to download and install packages
  - NEVER CANCEL: Set timeout to 120+ seconds to handle network delays
- Run tests: `python -m pytest tests/ -v`
  - NEVER CANCEL: Tests complete in <0.5 seconds typically. Set timeout to 60+ seconds to be safe.
  - All 31 tests should pass
  - Real execution time measured: ~0.45 seconds including setup
- Validate imports: `python -c "from hype.hype import Hype; from hype.config import Config; print('Import successful')"`

### Development Commands
- Run the bot (requires valid Mastodon credentials): `python -m hype`
  - NEVER CANCEL: Bot runs continuously in a scheduling loop
  - Will fail immediately without valid config: expects `/app/config/auth.yaml` and `/app/config/config.yaml`
- Run tests with verbose output: `python -m pytest tests/ -v`
  - NEVER CANCEL: Completes in <0.5 seconds typically. Set timeout to 60+ seconds.
- Run specific test file: `python -m pytest tests/test_boosting.py -v`
  - NEVER CANCEL: Single test file takes <0.2 seconds. Set timeout to 30+ seconds.
- Import modules for testing: `python -c "import sys; sys.path.insert(0, '.'); from hype.hype import Hype"`

### Docker Development
- Build Docker image: `docker build -t hypebot .`
  - NEVER CANCEL: Build takes 2-5 minutes depending on network. Set timeout to 600+ seconds.
  - NOTE: Docker build fails in environments with SSL certificate issues when accessing PyPI
  - Document as: "Docker build fails due to network/firewall limitations in some environments"
- Run with docker-compose: `docker-compose up`
  - Requires valid config files in `./config/` directory

## Validation Scenarios

### Testing Code Changes
Always validate changes by running the complete test suite:
- Run `python -m pytest tests/ -v` after making any code changes
- NEVER CANCEL: Tests complete in ~0.5 seconds. Set timeout to 60+ seconds.
- Ensure all 31 tests continue to pass
- Tests cover: boosting logic, hashtag scoring, public caps, seen status tracking, status filtering

### Application Failure Testing  
Validate that configuration errors are caught properly:
- Run `python -m hype` without config files to see clear error: `FileNotFoundError: [Errno 2] No such file or directory: '/app/config/auth.yaml'`
- This confirms the application fails gracefully with descriptive error messages
- Never attempt to run the bot without proper Mastodon credentials as it will fail immediately

### Configuration Testing
Test configuration loading without real Mastodon credentials:
```python
# Create minimal test config in Python
import tempfile, yaml, os
from hype.config import Config, BotAccount, Instance

# Mock configuration works for testing config parsing logic
# Real Mastodon credentials required for actual bot operation
```

### Application Structure Testing
- Validate module imports work: `python -c "from hype.hype import Hype; print('Hype class available')"`
- Check available methods: `python -c "import inspect; from hype.hype import Hype; print([name for name, _ in inspect.getmembers(Hype, predicate=inspect.isfunction)])"`

## Configuration Requirements

### Required Files
The bot requires two configuration files in `/app/config/` (or custom path):

#### auth.yaml
```yaml
bot_account:
  server: "https://your.mastodon.instance"
  access_token: "your_bot_access_token"
```

#### config.yaml
```yaml
interval: 60  # minutes between runs
profile_prefix: "I am boosting trending posts from:"
subscribed_instances:
  chaos.social:
    limit: 5
  mastodon.social:
    limit: 5
# Additional configuration options available
```

### Authentication
- Bot requires a valid Mastodon account with API access token
- Create application in Mastodon: Preferences -> Development -> New Application
- Grant appropriate permissions for reading timelines and posting/boosting

## Key Application Flows

### Main Execution
1. `python -m hype` loads configuration from `/app/config/auth.yaml` and `/app/config/config.yaml`
2. Bot logs into Mastodon instance specified in auth.yaml
3. Updates bot profile with list of subscribed instances
4. Starts boost cycle, then schedules recurring runs every `interval` minutes
5. Each boost cycle: fetches trending posts, scores them, boosts top results within limits

### Core Functions
- `Hype.login()`: Authenticates with Mastodon API
- `Hype.update_profile()`: Updates bot profile with subscribed instances list
- `Hype.boost()`: Main logic - fetches, scores, and boosts trending posts
- `Hype.start()`: Runs initial boost then schedules recurring execution

## Project Structure

### Core Modules
- `hype/__main__.py`: Entry point that creates bot and starts execution
- `hype/hype.py`: Main bot logic (183 lines for boost method, ~270 total)
- `hype/config.py`: Configuration parsing and validation (176 lines)

### Test Coverage
- `tests/test_boosting.py`: Core boosting logic and sorting
- `tests/test_hashtag_scoring.py`: Hashtag weight preferences
- `tests/test_public_cap.py`: Daily/hourly posting limits
- `tests/test_score_status.py`: Post scoring algorithm
- `tests/test_seen_status.py`: Duplicate detection and author limits
- `tests/test_should_skip_status.py`: Content filtering rules

### Dependencies
- `pyyaml`: Configuration file parsing
- `Mastodon.py`: Mastodon API client
- `schedule`: Recurring task scheduling
- `pytest`: Test framework

## Common Tasks

### Testing Changes
- Always run full test suite: `python -m pytest tests/ -v`
- Tests are fast (<0.5 seconds) and comprehensive
- 31 tests covering all major functionality

### Configuration Validation
- Config files use YAML format with specific structure
- Bot validates configuration on startup
- Missing or invalid config files cause immediate failure with clear error messages

### Deployment
- Docker-based deployment recommended
- GitHub Actions automatically builds and publishes container images
- Supports both amd64 and arm64 architectures

## GitHub Workflow

### CI/CD Pipeline (.github/workflows/main.yml)
- **Test job**: Runs on pull requests, installs dependencies and runs pytest
- **Build PR images**: Creates tagged images for testing pull requests
- **Release job**: Tags and builds production images on main branch pushes
- **GitHub releases**: Creates releases with automatic changelog generation

### Branch Strategy
- Work starts on `develop` branch
- Merge to `main` triggers release workflow
- Workflow recreates `develop` branch after successful merge

## Limitations and Notes

### Network Dependencies
- Requires internet access to fetch trending posts from Mastodon instances
- Docker builds may fail in environments with SSL certificate restrictions
- Bot needs valid Mastodon API credentials to function

### Runtime Behavior
- Bot runs continuously, executing boost cycles on configured interval
- State persisted to `/app/secrets/state.json` for tracking seen posts and daily limits
- Respects rate limits and implements various safety caps

### Configuration Dependencies
- Hardcoded config paths: `/app/config/auth.yaml` and `/app/config/config.yaml`
- No command-line options to override config file locations
- Bot will fail immediately if config files are missing or invalid

Always test configuration changes with the test suite before deploying to ensure the bot continues to function correctly.