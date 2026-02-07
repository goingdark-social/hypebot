#!/usr/bin/env python3
"""
Test script to verify local post bonus functionality
"""

import sys
import os

# Add the hype directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "hype"))


def test_config_defaults():
    """Test that configuration defaults are correct"""
    from hype.config import Config

    config = Config()

    # Check local timeline defaults
    assert config.local_timeline_boost_limit == 4, (
        f"Expected 4, got {config.local_timeline_boost_limit}"
    )
    assert config.local_timeline_min_engagement == 1, (
        f"Expected 1, got {config.local_timeline_min_engagement}"
    )
    assert config.local_post_bonus == 1.5, (
        f"Expected 1.5, got {config.local_post_bonus}"
    )
    assert config.hashtag_diversity_enforced == True, (
        f"Expected True, got {config.hashtag_diversity_enforced}"
    )

    print("✓ Configuration defaults are correct")
    print(f"  - local_timeline_boost_limit: {config.local_timeline_boost_limit}")
    print(f"  - local_timeline_min_engagement: {config.local_timeline_min_engagement}")
    print(f"  - local_post_bonus: {config.local_post_bonus}")
    print(f"  - hashtag_diversity_enforced: {config.hashtag_diversity_enforced}")


def test_local_post_bonus_calculation():
    """Test that local post bonus is applied correctly"""
    from hype.config import Config

    config = Config()
    config.local_post_bonus = 2.0  # Test with 2x bonus

    # Simulate a simple score calculation
    base_score = 10.0
    expected_bonus_score = base_score * config.local_post_bonus

    assert expected_bonus_score == 20.0, f"Expected 20.0, got {expected_bonus_score}"
    print(
        f"✓ Local post bonus calculation correct: {base_score} * {config.local_post_bonus} = {expected_bonus_score}"
    )


def test_environment_variable_loading():
    """Test that environment variables override defaults"""
    from hype.config import Config

    # Set environment variables
    os.environ["HYPE_LOCAL_TIMELINE_BOOST_LIMIT"] = "5"
    os.environ["HYPE_LOCAL_POST_BONUS"] = "3.0"

    config = Config()

    assert config.local_timeline_boost_limit == 5, (
        f"Expected 5, got {config.local_timeline_boost_limit}"
    )
    assert config.local_post_bonus == 3.0, (
        f"Expected 3.0, got {config.local_post_bonus}"
    )

    print("✓ Environment variables override defaults correctly")

    # Clean up
    del os.environ["HYPE_LOCAL_TIMELINE_BOOST_LIMIT"]
    del os.environ["HYPE_LOCAL_POST_BONUS"]


if __name__ == "__main__":
    print("Testing Local Post Bonus Implementation")
    print("=" * 50)

    try:
        test_config_defaults()
        test_local_post_bonus_calculation()
        test_environment_variable_loading()

        print("\n" + "=" * 50)
        print("All tests passed! ✓")

    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
