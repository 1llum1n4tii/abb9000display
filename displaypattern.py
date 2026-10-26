
#!/usr/bin/env python3

import argparse
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

COMPONENTS = list(SEGMENTS.keys())
SYMBOLS = [
    "LIGHTNING",
    "PERCENT",
    "DROP_TOP",
    "DROP_MIDDLE",
    "DROP_BOTTOM",
]


def all_off():
    """Put all GPIO pins into input mode."""
    for gpio in PINS.values():
        GPIO.setup(gpio, GPIO.IN)


def light_components(names):
    """Light a set of components simultaneously."""
    all_off()

    # Drive each requested pair.
    # If a pin is needed as both HIGH and LOW, this wiring
    # cannot safely illuminate those components simultaneously.
    low_pins = set()
    high_pins = set()

    for name in names:
        negative, positive = SEGMENTS[name]
        low_pins.add(PINS[negative])
        high_pins.add(PINS[positive])

    conflicts = low_pins & high_pins
    if conflicts:
        return

    for gpio in low_pins:
        GPIO.setup(gpio, GPIO.OUT, initial=GPIO.LOW)

    for gpio in high_pins:
        GPIO.setup(gpio, GPIO.OUT, initial=GPIO.HIGH)


def digit_components(digit, side="L"):
    return {
        f"{side}_{segment}"
        for segment in DIGITS[digit]
    }


def pause(seconds):
    time.sleep(seconds)


def animation_chase(hz):
    delay = 1.0 / hz

    while True:
        for component in COMPONENTS:
            light_components([component])
            pause(delay)


def animation_fill(hz):
    delay = 1.0 / hz

    while True:
        # Build up the left digit, segment by segment.
        active = []

        for component in digit_components(8):
            active.append(component)
            light_components(active)
            pause(delay)

        pause(0.3)

        for _ in range(len(active)):
            active.pop()
            light_components(active)
            pause(delay)

        pause(0.3)


def animation_bounce(hz):
    delay = 1.0 / hz

    while True:
        for index in list(range(len(COMPONENTS))) + list(
            range(len(COMPONENTS) - 2, 0, -1)
        ):
            light_components([COMPONENTS[index]])
            pause(delay)


def animation_count(hz):
    delay = 1.0 / hz

    while True:
        for digit in range(10):
            light_components(digit_components(digit, "L"))
            pause(max(delay, 0.5))


def animation_symbols(hz):
    delay = 1.0 / hz

    while True:
        for symbol in SYMBOLS:
            light_components([symbol])
            pause(max(delay, 0.5))


ANIMATIONS = {
    "chase": animation_chase,
    "fill": animation_fill,
    "bounce": animation_bounce,
    "count": animation_count,
    "symbols": animation_symbols,
}


def main():
    parser = argparse.ArgumentParser(
        description="GPIO display animations"
    )

    parser.add_argument(
        "--animation",
        required=True,
        choices=ANIMATIONS.keys(),
        help="Animation to run",
    )

    parser.add_argument(
        "--hz",
        type=float,
        default=120,
        help="Animation update rate in Hz (default: 120)",
    )

    args = parser.parse_args()

    if args.hz <= 0:
        parser.error("--hz must be greater than zero")

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    try:
        print(
            f"Running animation '{args.animation}' "
            f"at {args.hz:g} Hz. Press Ctrl+C to stop."
        )

        ANIMATIONS[args.animation](args.hz)

    except KeyboardInterrupt:
        print("\nAnimation stopped.")

    finally:
        all_off()
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()

