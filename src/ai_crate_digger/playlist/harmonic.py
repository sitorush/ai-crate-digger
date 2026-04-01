"""Harmonic mixing using the Camelot wheel."""

from ai_crate_digger.analysis.key import CAMELOT_WHEEL


def get_compatible_keys(camelot: str | None) -> list[str]:
    """Get harmonically compatible Camelot keys.

    Compatible keys on the Camelot wheel:
    - Same key (perfect match)
    - +1/-1 on wheel (adjacent keys)
    - Switch between A/B (relative major/minor)

    Args:
        camelot: Camelot notation (e.g., "8A", "5B")

    Returns:
        List of compatible Camelot keys
    """
    if not camelot or len(camelot) < 2:
        return []

    try:
        number = int(camelot[:-1])
        mode = camelot[-1].upper()
    except ValueError:
        return []

    if mode not in ("A", "B"):
        return []

    compatible = [camelot]  # Same key

    # Adjacent keys on wheel (+1, -1 with wraparound 1-12)
    prev_num = 12 if number == 1 else number - 1
    next_num = 1 if number == 12 else number + 1
    compatible.append(f"{prev_num}{mode}")
    compatible.append(f"{next_num}{mode}")

    # Relative major/minor (same number, switch A/B)
    other_mode = "B" if mode == "A" else "A"
    compatible.append(f"{number}{other_mode}")

    return compatible


def camelot_to_standard(camelot: str) -> str | None:
    """Convert Camelot notation back to standard key.

    Args:
        camelot: Camelot notation (e.g., "8A")

    Returns:
        Standard key notation (e.g., "Am") or None if unknown
    """
    # Reverse lookup in CAMELOT_WHEEL
    for key, cam in CAMELOT_WHEEL.items():
        if cam == camelot:
            return key
    return None


def is_compatible(key1: str | None, key2: str | None) -> bool:
    """Check if two Camelot keys are harmonically compatible.

    Args:
        key1: First Camelot key
        key2: Second Camelot key

    Returns:
        True if keys are compatible for mixing
    """
    if not key1 or not key2:
        return True  # Unknown keys are considered compatible

    return key2 in get_compatible_keys(key1)


def harmonic_distance(key1: str | None, key2: str | None) -> int:
    """Calculate harmonic distance between two Camelot keys.

    Distance of 0 = same key
    Distance of 1 = compatible (adjacent or relative)
    Distance of 2+ = number of steps on wheel

    Args:
        key1: First Camelot key
        key2: Second Camelot key

    Returns:
        Harmonic distance (lower is better), 99 if unknown
    """
    if not key1 or not key2:
        return 99

    if key1 == key2:
        return 0

    if is_compatible(key1, key2):
        return 1

    try:
        num1 = int(key1[:-1])
        num2 = int(key2[:-1])
        mode1 = key1[-1].upper()
        mode2 = key2[-1].upper()
    except (ValueError, IndexError):
        return 99

    # Calculate circular distance on wheel
    forward = (num2 - num1) % 12
    backward = (num1 - num2) % 12
    wheel_dist = min(forward, backward)

    # Add 1 if modes differ
    mode_penalty = 0 if mode1 == mode2 else 1

    return wheel_dist + mode_penalty
