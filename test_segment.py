
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


def all_off():
    for gpio in PINS.values():
        GPIO.setup(gpio, GPIO.IN)


def light_segment(name):
    negative_pin, positive_pin = SEGMENTS[name]

    all_off()
    GPIO.setup(PINS[negative_pin], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS[positive_pin], GPIO.OUT, initial=GPIO.HIGH)


def main():
    parser = argparse.ArgumentParser(
        description="Continuously test one display component."
    )
    parser.add_argument(
        "--segment",
        required=True,
        type=str.upper,
        choices=[name.upper() for name in SEGMENTS],
        help="Component name, e.g. L_a, R_g, LIGHTNING, DROP_TOP",
    )
    parser.add_argument(
        "--hz",
        type=float,
        default=120,
        help="Refresh rate in Hz (default: 120)",
    )

    args = parser.parse_args()

    if args.hz <= 0:
        parser.error("--hz must be greater than zero")

    # Match case-insensitively to the defined component name.
    segment = next(
        name for name in SEGMENTS if name.upper() == args.segment
    )

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    try:
        print(f"Testing {segment} at {args.hz:g} Hz. Press Ctrl+C to stop.")

        frame_time = 1.0 / args.hz

        while True:
            frame_start = time.monotonic()
            light_segment(segment)

            remaining = frame_start + frame_time - time.monotonic()
            if remaining > 0:
                time.sleep(remaining)

            all_off()

    except KeyboardInterrupt:
        print("\nTest stopped.")

    finally:
        all_off()
        GPIO.cleanup()
        print("GPIO cleaned up.")


if __name__ == "__main__":
    main()

