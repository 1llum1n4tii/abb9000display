AliBarBarIngot9000 LCD Rpi Driver

Raspberry Pi GPIO driver for a multiplexed display, with command-line control, segment testing, and animations.

Requirements
Raspberry Pi with GPIO support
Python 3 and RPi.GPIO
Zsh for the command-line wrapper

Make the wrapper executable:

bash
chmod +x display.zsh

Scripts
Script	Purpose
display.py	Continuously display a digit and optional symbol
display.zsh	Start, replace, and stop display processes
test_segment.py	Test an individual display component
test_segments.py	Test all 19 components sequentially
displaypattern.py	Run display animations
Display Driver

Display a digit continuously:

bash
./display.zsh --khz 120 --symbol NONE --digit 3


Display a digit with a symbol:

bash
./display.zsh --digit 8 --symbol LIGHTNING
./display.zsh --digit 5 --symbol PERCENT
./display.zsh --digit 2 --symbol DROP_TOP
./display.zsh --digit 2 --symbol DROP_MIDDLE
./display.zsh --digit 2 --symbol DROP_BOTTOM


Select the digit position:

bash
./display.zsh --digit 3 --side LEFT
./display.zsh --digit 3 --side RIGHT

Driver arguments
Argument	Default	Description
--digit	Required	Digit 0–9
--symbol	NONE	NONE, LIGHTNING, PERCENT, DROP_TOP, DROP_MIDDLE, DROP_BOTTOM
--khz	120	Refresh rate in Hz; despite the option name
--side	LEFT	LEFT or RIGHT
Segment Testing

Test one component continuously:

bash
python3 test_segment.py --segment L_a --hz 120
python3 test_segment.py --segment R_g --hz 60
python3 test_segment.py --segment LIGHTNING --hz 120
python3 test_segment.py --segment DROP_BOTTOM --hz 120


Test all 19 components sequentially for one second each:

bash
python3 test_segments.py

Animations

Run an animation continuously:

bash
python3 displaypattern.py --animation chase --hz 120


Available animations:

Animation	Description
chase	Lights each component in sequence
fill	Builds and clears the left digit
bounce	Moves a lit component back and forth
count	Counts from 0 to 9 on the left digit
symbols	Cycles through lightning, percent, and water-drop components

Examples:

bash
python3 displaypattern.py --animation fill --hz 10
python3 displaypattern.py --animation bounce --hz 20
python3 displaypattern.py --animation count --hz 2
python3 displaypattern.py --animation symbols --hz 2

Process Management

Starting a new configuration automatically stops existing Python processes
matching the relevant driver script.

Stop all display processes:

```bash
./display --killall
```

Stop all animation processes:

```bash
./display-pattern --killall
```

Both commands send SIGINT to every matching process and wait up to five
seconds per process for graceful GPIO cleanup. They attempt to stop all
matching processes even if one fails to exit, and return an error if any
process fails to stop.

Press Ctrl+C to stop scripts running in the foreground.

GPIO Mapping

The scripts use BCM numbering.

Pin ID	BCM GPIO	Physical pin
1	17	11
2	27	13
3	22	15
4	23	16
5	24	18
6	25	22

Component pin pairs are defined in display.py and reused by the test and animation scripts.

Logging

The wrapper redirects Python output to /tmp/display.log.

bash
tail -f /tmp/display.log

Notes
All continuous scripts stop with Ctrl+C and clean up GPIO on graceful exit.
--khz 120 means 120 Hz, not 120 kHz.
--hz controls the timing used by the segment tester and animation runner; it does not guarantee precise hardware timing.
Some simultaneous component combinations can conflict because they share GPIO pins.
Use appropriate current limiting and ensure the circuit is safe for Raspberry Pi GPIO.
