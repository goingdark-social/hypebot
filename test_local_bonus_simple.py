#!/usr/bin/env python3
"""
Simple test to verify local post bonus implementation
"""


def test_config_defaults():
    """Test that configuration defaults are correct by reading the file"""
    with open("hype/config.py", "r") as f:
        content = f.read()

    # Check that the defaults are set correctly
    assert "local_timeline_boost_limit: int = 4" in content, (
        "local_timeline_boost_limit not set to 4"
    )
    assert "1.5  # Multiplier for local instance posts" in content, (
        "local_post_bonus not set to 1.5"
    )
    assert "hashtag_diversity_enforced: bool = True" in content, (
        "hashtag_diversity_enforced not set to True"
    )

    print("✓ Configuration defaults are correct")
    print("  - local_timeline_boost_limit: 4 (increased from 2)")
    print("  - local_post_bonus: 1.5 (new feature)")
    print("  - hashtag_diversity_enforced: True (enabled by default)")


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


if __name__ == "__main__":
    print("Testing Local Post Bonus Implementation")
    print("=" * 60)

    try:
        test_config_defaults()
        test_local_post_bonus_in_scoring()
        test_environment_variable_loading()

        if not test_syntax_validation():
            print("\n" + "=" * 60)
            print("Syntax validation failed!")
            exit(1)

        print("\n" + "=" * 60)
        print("All basic tests passed! ✓")
        print("\nChanges implemented:")
        print("1. Increased local_timeline_boost_limit from 2 to 4")
        print("2. Added local_post_bonus (1.5x multiplier for local posts)")
        print("3. Enabled hashtag_diversity_enforced by default")
        print("4. Added environment variable support (HYPE_LOCAL_POST_BONUS)")
        print("5. Applied local post bonus in scoring logic with debug logging")

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
