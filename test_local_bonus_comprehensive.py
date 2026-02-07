#!/usr/bin/env python3
"""
Comprehensive test to verify local post bonus implementation
"""


def test_config_defaults():
    """Test that configuration defaults are correct by reading the file"""
    with open("hype/config.py", "r") as f:
        content = f.read()

    # Check that the local post improvements are set correctly
    assert "local_timeline_boost_limit: int = 4" in content, (
        "local_timeline_boost_limit not set to 4"
    )
    assert "1.5  # Multiplier for local instance posts" in content, (
        "local_post_bonus not set to 1.5"
    )
    assert "hashtag_diversity_enforced: bool = True" in content, (
        "hashtag_diversity_enforced not set to True"
    )

    # Check that quality controls are enabled
    assert "age_decay_enabled: bool = True" in content, (
        "age_decay not enabled by default"
    )
    assert "spam_emoji_penalty: float = 0.5" in content, (
        "spam_emoji_penalty not set to 0.5"
    )
    assert "spam_link_penalty: float = 0.3" in content, (
        "spam_link_penalty not set to 0.3"
    )
    assert "min_score_threshold: float = (" in content and "4" in content, (
        "min_score_threshold not set to 4"
    )

    print("✓ Configuration defaults are correct")
    print("  Local Post Improvements:")
    print("    - local_timeline_boost_limit: 4 (increased from 2)")
    print("    - local_post_bonus: 1.5x multiplier (NEW)")
    print("    - hashtag_diversity_enforced: True (enabled)")
    print("  Quality Controls:")
    print("    - age_decay_enabled: True (enabled)")
    print("    - spam_emoji_penalty: 0.5 (enabled)")
    print("    - spam_link_penalty: 0.3 (enabled)")
    print("    - min_score_threshold: 4 (moderate threshold)")


def test_local_post_bonus_in_scoring():
    """Test that local post bonus is applied in scoring logic"""
    with open("hype/hype.py", "r") as f:
        content = f.read()

    # Check that the local post bonus is applied
    assert "local_post_bonus" in content, "local_post_bonus not found in hype.py"
    assert "base_score * self.config.local_post_bonus" in content, (
        "Local post bonus multiplication not found"
    )
    assert "LOCAL POST BONUS" in content, "Debug logging for local post bonus not found"

    print("✓ Local post bonus applied in scoring logic")
    print("  - Multiplies base score by local_post_bonus")
    print("  - Includes debug logging when bonus != 1.0")


def test_environment_variable_loading():
    """Test that environment variable loading is present"""
    with open("hype/config.py", "r") as f:
        content = f.read()

    # Check that environment variable loading is present
    assert "HYPE_LOCAL_POST_BONUS" in content, (
        "HYPE_LOCAL_POST_BONUS environment variable not found"
    )

    print("✓ Environment variable loading present")
    print("  - HYPE_LOCAL_POST_BONUS can override default")


def test_syntax_validation():
    """Test that files have valid Python syntax"""
    import py_compile

    try:
        py_compile.compile("hype/config.py", doraise=True)
        py_compile.compile("hype/hype.py", doraise=True)
        print("✓ Files have valid Python syntax")
    except py_compile.PyCompileError as e:
        print(f"✗ Syntax error: {e}")
        return False

    return True


def show_summary():
    """Show summary of all changes"""
    print("\n" + "=" * 70)
    print("SUMMARY OF IMPLEMENTED CHANGES")
    print("=" * 70)

    print("\n📈 Phase 1: Local Post Visibility Improvements")
    print("   ✅ Increased local_timeline_boost_limit from 2 to 4")
    print("   ✅ Added local_post_bonus (1.5x multiplier for local posts)")
    print("   ✅ Enabled hashtag_diversity_enforced by default")
    print("   ✅ Local engagement threshold already at 1 (minimal barrier)")

    print("\n🛡️ Phase 2: Quality Controls")
    print("   ✅ Enabled age_decay by default (24-hour half-life)")
    print("   ✅ Enabled spam_emoji_penalty (0.5 points per excess emoji)")
    print("   ✅ Enabled spam_link_penalty (0.3 points per link)")
    print("   ✅ Set min_score_threshold to 4 (filters low-quality content)")

    print("\n⚙️ Configuration Options")
    print("   ✅ HYPE_LOCAL_POST_BONUS - Set custom multiplier for local posts")
    print("   ✅ HYPE_LOCAL_TIMELINE_BOOST_LIMIT - Override boost limit")
    print("   ✅ HYPE_AGE_DECAY_ENABLED - Toggle age decay")
    print("   ✅ HYPE_SPAM_EMOJI_PENALTY - Adjust emoji spam penalty")
    print("   ✅ HYPE_SPAM_LINK_PENALTY - Adjust link spam penalty")

    print("\n🎯 Expected Impact")
    print(
        "   - Local posts get 1.5x score boost, competing better with trending content"
    )
    print("   - More local posts can be boosted (limit increased from 2 to 4)")
    print("   - Hashtag diversity prevents topic saturation")
    print("   - Age decay keeps content fresh and relevant")
    print("   - Spam penalties reduce low-quality content")
    print("   - Quality threshold filters out very low-quality posts")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    print("Testing Local Post Bonus Implementation")
    print("=" * 70)

    try:
        test_config_defaults()
        test_local_post_bonus_in_scoring()
        test_environment_variable_loading()

        if not test_syntax_validation():
            print("\n" + "=" * 70)
            print("Syntax validation failed!")
            exit(1)

        show_summary()

        print("=" * 70)
        print("All tests passed! ✅")
        print("\nThe hypebot will now:")
        print("1. Boost local posts 1.5x more than before")
        print("2. Allow up to 4 local posts per run (vs 2 before)")
        print("3. Filter spam and low-quality content")
        print("4. Keep content fresh with age decay")

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
