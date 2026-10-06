"""Pure helpers for byte-based extraction progress."""

from __future__ import annotations


def extraction_percent(copied_bytes: object, total_bytes: object, complete: bool = False) -> int:
    """Return a safe percentage; active copies remain below 100 until verified."""
    if complete:
        return 100
    try:
        copied = max(0, int(copied_bytes))
        total = max(0, int(total_bytes))
    except (TypeError, ValueError):
        return 0
    if total <= 0:
        return 0
    return min(99, max(0, int((copied * 100) / total)))


def estimate_eta_seconds(
    copied_bytes: object,
    total_bytes: object,
    started_at: object,
    now: object,
) -> int | None:
    """Estimate remaining seconds from average copy speed for the whole slot copy."""
    try:
        copied = max(0, int(copied_bytes))
        total = max(0, int(total_bytes))
        start = float(started_at)
        current = float(now)
    except (TypeError, ValueError):
        return None
    if copied <= 0 or total <= 0 or copied >= total or current <= start:
        return None
    bytes_per_second = copied / (current - start)
    if bytes_per_second <= 0:
        return None
    return max(0, int((total - copied) / bytes_per_second))


def format_eta(seconds: object) -> str:
    """Format seconds as a compact ETA string."""
    try:
        remaining = max(0, int(seconds))
    except (TypeError, ValueError):
        return "ETA calculating..."
    hours, rem = divmod(remaining, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"ETA {hours}h {minutes:02d}m"
    if minutes:
        return f"ETA {minutes}m {secs:02d}s"
    return f"ETA {secs}s"
