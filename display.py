
import argparse
import signal
import time

import RPi.GPIO as GPIO


PINS = {
    1: 17,
    2: 27,
    3: 22,
    4: 23,
    5: 24,
    6: 25,
}

# Each component maps to (negative pin, positive pin).
SEGMENTS = {
    "L_a": (1, 2),
    "L_b": (1, 3),
    "L_c": (1, 4),
    "L_d": (1, 5),
    "L_e": (1, 6),
    "L_f": (2, 1),
    "L_g": (2, 3),

    "R_a": (2, 4),
    "R_b": (2, 5),
    "R_c": (2, 6),
    "R_d": (3, 1),
    "R_e": (3, 2),
    "R_f": (3, 4),
    "R_g": (3, 5),

    "LIGHTNING": (3, 6),
    "PERCENT": (4, 1),
    "DROP_TOP": (4, 2),
    "DROP_MIDDLE": (4, 3),
    "DROP_BOTTOM": (4, 5),
}

DIGITS = {
    0: ("a", "b", "c", "d", "e", "f"),
    1: ("b", "c"),
    2: ("a", "b", "d", "e", "g"),
    3: ("a", "b", "c", "d", "g"),
    4: ("b", "c", "f", "g"),
    5: ("a", "c", "d", "f", "g"),
    6: ("a", "c", "d", "e", "f", "g"),
    7: ("a", "b", "c"),
    8: ("a", "b", "c", "d", "e", "f", "g"),
    9: ("a", "b", "c", "d", "f", "g"),
}

SYMBOLS = (
    "NONE",
    "LIGHTNING",
    "PERCENT",
    "DROP_TOP",
    "DROP_MIDDLE",
    "DROP_BOTTOM",
)

REFRESH_HZ = 120


def all_off():
    """Turn off all components by releasing all GPIO pins."""
    for gpio in PINS.values():
        GPIO.setup(gpio, GPIO.IN)


def light_segment(name):
    """Activate a single component using its assigned pin pair."""
    negative_pin, positive_pin = SEGMENTS[name]

    all_off()

    GPIO.setup(PINS[negative_pin], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS[positive_pin], GPIO.OUT, initial=GPIO.HIGH)


def get_active_components(digit, side, symbol):
    """Return the segments needed for the selected digit and symbol."""
    prefix = "L" if side == "LEFT" else "R"

    active = {
        f"{prefix}_{segment}"
        for segment in DIGITS[digit]
    }

    if symbol != "NONE":
        active.add(symbol)

    return active


def display(digit, side="LEFT", symbol="NONE", refresh_hz=REFRESH_HZ):
    """Continuously display a digit and optional symbol until stopped."""
    if digit not in DIGITS:
        raise ValueError("Digit must be between 0 and 9")

    if side not in ("LEFT", "RIGHT"):
        raise ValueError("Side must be LEFT or RIGHT")

    if symbol not in SYMBOLS:
        raise ValueError(f"Unsupported symbol: {symbol}")

    if refresh_hz <= 0:
        raise ValueError("Refresh rate must be greater than zero")

    active = get_active_components(digit, side, symbol)

    # Scan the seven digit positions and, if selected, one symbol.
    prefix = "L" if side == "LEFT" else "R"
    scan_order = [
        f"{prefix}_{letter}"
        for letter in "abcdefg"
    ]

    if symbol != "NONE":
        scan_order.append(symbol)

    frame_time = 1.0 / refresh_hz
    slot_time = frame_time / len(scan_order)

    while True:
        frame_start = time.monotonic()

        for component in scan_order:
            if component in active:
                light_segment(component)
            else:
                all_off()

            time.sleep(slot_time)
            all_off()

        # Keep the overall frame rate as consistent as possible.
        remaining = frame_start + frame_time - time.monotonic()
        if remaining > 0:
            time.sleep(remaining)


def main():
    parser = argparse.ArgumentParser(
        description="Continuously display a digit and optional symbol."
    )

    parser.add_argument(
        "--khz",
        type=float,
        default=REFRESH_HZ,
        help="Refresh rate in Hz (default: 120).",
    )

    parser.add_argument(
        "--symbol",
        type=str.upper,
        choices=SYMBOLS,
        default="NONE",
        help="Optional symbol to display (default: NONE).",
    )

    parser.add_argument(
        "--digit",
        type=int,
        choices=range(10),
        required=True,
        help="Digit to display (0-9).",
    )

    parser.add_argument(
        "--side",
        type=str.upper,
        choices=("LEFT", "RIGHT"),
        default="LEFT",
        help="Digit position (default: LEFT).",
    )

    args = parser.parse_args()

    if args.khz <= 0:
        parser.error("--khz must be greater than zero")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    try:
        print(
            f"Displaying {args.digit} on the {args.side} "
            f"with symbol {args.symbol} at {args.khz:g} Hz. "
            "Press Ctrl+C to stop."
        )

        display(
            digit=args.digit,
            side=args.side,
            symbol=args.symbol,
            refresh_hz=args.khz,
        )

    except KeyboardInterrupt:
        print("\nDisplay stopped.")

    finally:
        all_off()
        GPIO.cleanup()


if __name__ == "__main__":
    main()

