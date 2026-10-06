"""Pure path-building helpers for extracted PIG data.

This module deliberately has no PyQt, serial, or hardware dependencies so its
behavior can be validated in the development test environment.
"""

from __future__ import annotations

import os
import re
from typing import Optional


_WINDOWS_RESERVED_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_path_component(value: object, fallback: str) -> str:
    """Return a Windows-safe, non-empty directory-name component."""
    text = _WINDOWS_RESERVED_CHARS.sub("_", str(value or "").strip())
    text = text.rstrip(" .")
    return text or fallback


def normalize_pig_type(board_type: object) -> str:
    """Normalize configured board/PIG types used in extraction paths."""
    normalized = str(board_type or "").strip().upper()
    if normalized in {"A-MFL", "C-MFL", "EGP"}:
        return normalized
    return "Unknown-type"


def format_pig_size(pipe_size: object) -> str:
    """Format a positive configured pipe size, otherwise use a stable bucket."""
    try:
        size = int(pipe_size)
    except (TypeError, ValueError):
        size = 0
    return f"{size}-inch" if size > 0 else "Unknown-size"


def build_by_label_destination(
    extracted_data_root: str,
    board_type: object,
    pipe_size: object,
    board_index: int,
    slot: int,
    volume_label: Optional[str] = None,
) -> str:
    """Build `By_Label/<type>/<size>/<label>` for an extraction target."""
    pig_type = safe_path_component(normalize_pig_type(board_type), "Unknown-type")
    pig_size = safe_path_component(format_pig_size(pipe_size), "Unknown-size")
    fallback_label = f"UNLABELED_B{int(board_index)}S{int(slot)}"
    label = safe_path_component((volume_label or "").upper(), fallback_label)
    return os.path.join(extracted_data_root, "By_Label", pig_type, pig_size, label)

