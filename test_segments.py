
import RPi.GPIO as GPIO
import time

# BCM GPIO mapping
PINS = {
    1: 17,
    2: 27,
    3: 22,
    4: 23,
    5: 24,
    6: 25,
}

# Component: (negative pin ID, positive pin ID)
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
    """Release all GPIO pins."""
    for gpio in PINS.values():
        GPIO.setup(gpio, GPIO.IN)


def light_segment(name):
    """Activate one component."""
    negative_pin, positive_pin = SEGMENTS[name]

    all_off()

    GPIO.setup(PINS[negative_pin], GPIO.OUT, initial=GPIO.LOW)
    GPIO.setup(PINS[positive_pin], GPIO.OUT, initial=GPIO.HIGH)


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    try:
        for name in SEGMENTS:
            print(f"Testing {name}...")

            light_segment(name)
            time.sleep(1)

            all_off()

        print("All 19 components tested successfully.")

    except KeyboardInterrupt:
        print("\nTest interrupted.")

    finally:
        all_off()
        GPIO.cleanup()
        print("GPIO cleaned up. Exiting.")


if __name__ == "__main__":
    main()

