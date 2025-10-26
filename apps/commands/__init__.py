# apps/commands/__init__.py

"""
Command utilities and helpers for DMK Poll Bot.
"""

# Default permission suffix for command descriptions
DEFAULT_SUFFIX = "(admin/mod)"
DESC_MAX = 100


def with_default_suffix(desc: str) -> str:
    """
    Append the default permission suffix to a command description.

    Ensures the total length does not exceed Discord's 100-character limit
    by trimming the description if necessary.

    Args:
        desc: Base description text

    Returns:
        Description with suffix, maximum 100 characters
    """
    # Add space before suffix
    out = f"{desc} {DEFAULT_SUFFIX}"

    # If too long, trim the description (not the suffix)
    if len(out) > DESC_MAX:
        max_desc_len = DESC_MAX - len(DEFAULT_SUFFIX) - 1  # -1 for space
        trimmed_desc = desc[:max_desc_len].rstrip()
        out = f"{trimmed_desc} {DEFAULT_SUFFIX}"

    return out
