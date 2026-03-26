"""Color depth conversion utilities for terminal rendering.

Converts RGB and 256-color values to lower color depths so that
``fg()`` and ``bg()`` degrade gracefully on terminals that don't
support truecolor or 256-color modes.
"""

from __future__ import annotations

# The 16 standard ANSI colors as (R, G, B) — used for basic fallback.
# Indices 0-7 are normal, 8-15 are bright.
_BASIC_RGB: list[tuple[int, int, int]] = [
    (0, 0, 0),  # 0  black
    (170, 0, 0),  # 1  red
    (0, 170, 0),  # 2  green
    (170, 85, 0),  # 3  yellow
    (0, 0, 170),  # 4  blue
    (170, 0, 170),  # 5  magenta
    (0, 170, 170),  # 6  cyan
    (170, 170, 170),  # 7  white
    (85, 85, 85),  # 8  bright black (gray)
    (255, 85, 85),  # 9  bright red
    (85, 255, 85),  # 10 bright green
    (255, 255, 85),  # 11 bright yellow
    (85, 85, 255),  # 12 bright blue
    (255, 85, 255),  # 13 bright magenta
    (85, 255, 255),  # 14 bright cyan
    (255, 255, 255),  # 15 bright white
]

# Mapping from basic color index (0-15) to foreground SGR code.
_BASIC_TO_FG: list[int] = [
    30,
    31,
    32,
    33,
    34,
    35,
    36,
    37,  # normal
    90,
    91,
    92,
    93,
    94,
    95,
    96,
    97,  # bright
]


def _dist_sq(r1: int, g1: int, b1: int, r2: int, g2: int, b2: int) -> int:
    """Squared Euclidean distance between two RGB colors."""
    return (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2


def rgb_to_256(r: int, g: int, b: int) -> int:
    """Convert RGB to the nearest xterm-256 color index.

    Checks the 6x6x6 color cube (indices 16-231) and the grayscale
    ramp (indices 232-255), returning whichever is closest.
    """
    # 6x6x6 color cube
    ri = round(r / 255 * 5)
    gi = round(g / 255 * 5)
    bi = round(b / 255 * 5)
    cube_idx = 16 + 36 * ri + 6 * gi + bi
    cube_r, cube_g, cube_b = ri * 51, gi * 51, bi * 51
    cube_dist = _dist_sq(r, g, b, cube_r, cube_g, cube_b)

    # Grayscale ramp (24 shades from 8 to 238)
    gray = round((r + g + b) / 3)
    gray_idx = max(0, min(23, round((gray - 8) / 10)))
    gray_val = 8 + gray_idx * 10
    gray_dist = _dist_sq(r, g, b, gray_val, gray_val, gray_val)

    return 232 + gray_idx if gray_dist < cube_dist else cube_idx


def rgb_to_basic_fg(r: int, g: int, b: int) -> int:
    """Convert RGB to the nearest basic ANSI foreground SGR code (30-37, 90-97)."""
    best_idx = 0
    best_dist = _dist_sq(r, g, b, *_BASIC_RGB[0])
    for i in range(1, 16):
        d = _dist_sq(r, g, b, *_BASIC_RGB[i])
        if d < best_dist:
            best_dist = d
            best_idx = i
    return _BASIC_TO_FG[best_idx]


def index256_to_basic_fg(n: int) -> int:
    """Convert a 256-color index to the nearest basic foreground SGR code."""
    if n < 16:
        return _BASIC_TO_FG[n]

    # Resolve 256-color index to RGB, then map to basic
    if n < 232:
        # Color cube
        n -= 16
        bi = n % 6
        gi = (n // 6) % 6
        ri = n // 36
        r, g, b = ri * 51, gi * 51, bi * 51
    else:
        # Grayscale
        v = 8 + (n - 232) * 10
        r, g, b = v, v, v

    return rgb_to_basic_fg(r, g, b)
