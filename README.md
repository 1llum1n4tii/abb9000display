AliBarBarIngot9000 LCD Rpi Driver

Raspberry Pi GPIO driver for a multiplexed display. Continuously displays a digit and optional symbol until stopped. Use display.zsh to start, replace, or stop display processes.

Requirements
Raspberry Pi with GPIO support
Python 3 and RPi.GPIO
Zsh

Make the wrapper executable:

bash
chmod +x display.zsh

Usage

Start a display:

bash
./display.zsh --khz 120 --symbol NONE --digit 3


Display a digit with a symbol:

bash
./display.zsh --khz 120 --symbol LIGHTNING --digit 8
./display.zsh --symbol PERCENT --digit 5
./display.zsh --symbol DROP_TOP --digit 2


Select the right-hand digit:

bash
./display.zsh --digit 3 --side RIGHT

Arguments
Argument	Default	Description
--digit	Required	Digit from 0 to 9
--symbol	NONE	NONE, LIGHTNING, PERCENT, DROP_TOP, DROP_MIDDLE, DROP_BOTTOM
--khz	120	Refresh rate in Hz, despite the option name
--side	LEFT	LEFT or RIGHT
Process Management

Starting a new configuration automatically stops existing Python processes matching display.py.

Capture the PID:

bash
PID=$(./display.zsh --digit 3)
echo "$PID"


Stop a specific display process:

bash
./display.zsh --killpid "$PID"


Stop a directly running Python display with Ctrl+C.

The wrapper uses SIGTERM and waits for graceful shutdown. Avoid kill -9, which prevents GPIO cleanup.

GPIO Mapping

GPIO numbering uses BCM mode.

Pin ID	BCM GPIO
1	17
2	27
3	22
4	23
5	24
6	25

Components are defined by pin pairs in display.py. Each pair is driven LOW/HIGH to activate its component.

Logging

Python output is written to /tmp/display.log.

bash
tail -f /tmp/display.log

Notes
The display runs continuously until terminated.
--khz 120 means 120 Hz, not 120 kHz.
GPIO cleanup runs on graceful shutdown, but is not guaranteed after SIGKILL or power loss.
Ensure the circuit uses appropriate current limiting and is electrically safe for Raspberry Pi GPIO.