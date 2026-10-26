ABB9000 Display

Raspberry Pi GPIO driver for the multiplexed LCD display from an ALIBARBAR 9000 INGOT battery and liquid display.

Features:

Digit and symbol display control
Segment testing and animations
Process management with graceful GPIO cleanup
ntfy.sh notification triggers with configurable commands and delayed actions
Per-user systemd service for background notifications
Requirements
Raspberry Pi with GPIO support
Python 3 and RPi.GPIO
Zsh for the display wrappers
Bash and systemd for installation and service management
Network access for ntfy notifications
Installation

Run the interactive installer from the repository root:

bash
chmod +x install.sh
./install.sh


Choose Install to install the commands, Python scripts, notification configuration, and systemd user service.

Installed files are placed in ~/.local/bin/, with the service at ~/.config/systemd/user/display-notifications.service.

Choose Uninstall to stop and disable the notification service and remove the installed application files. Configuration and notification state can optionally be preserved.

Display driver

Display a digit continuously:

bash
display --digit 3 --symbol NONE


Display a digit with a symbol:

bash
display --digit 8 --symbol LIGHTNING
display --digit 5 --symbol PERCENT
display --digit 2 --symbol DROP_TOP
display --digit 2 --symbol DROP_MIDDLE
display --digit 2 --symbol DROP_BOTTOM


Select the digit position:

bash
display --digit 3 --side LEFT
display --digit 3 --side RIGHT

Argument	Description
--digit	Required digit, 0–9
--symbol	NONE, LIGHTNING, PERCENT, DROP_TOP, DROP_MIDDLE, DROP_BOTTOM
--side	LEFT or RIGHT
--khz	Refresh rate in Hz, despite the option name
Animations

Run an animation continuously:

bash
display-pattern --animation chase --hz 120


Available animations:

Animation	Description
chase	Lights each component in sequence
fill	Builds and clears the left digit
bounce	Moves a lit component back and forth
count	Counts from 0 to 9
symbols	Cycles through lightning, percent, and water-drop components

Examples:

bash
display-pattern --animation fill --hz 10
display-pattern --animation bounce --hz 20
display-pattern --animation count --hz 2
display-pattern --animation symbols --hz 2

Process management

Starting a new configuration automatically stops existing processes belonging to the same driver.

Stop all matching display processes:

bash
display --killall


Stop all matching animation processes:

bash
display-pattern --killall


The --killall option should find every matching process, send SIGINT to allow Python's cleanup handlers to run, and attempt to stop all matches even if one fails.

Press Ctrl+C to stop foreground scripts. Avoid kill -9, which prevents normal GPIO cleanup.

Segment testing

Test one component continuously:

bash
python3 ~/.local/bin/test_segment.py --segment L_a --hz 120
python3 ~/.local/bin/test_segment.py --segment R_g --hz 60
python3 ~/.local/bin/test_segment.py --segment LIGHTNING --hz 120
python3 ~/.local/bin/test_segment.py --segment DROP_BOTTOM --hz 120


Test all 19 components sequentially:

bash
python3 ~/.local/bin/test_segments.py

Notification worker

display-notifications.py polls configured ntfy.sh topics every five seconds and runs commands when new notifications arrive.

Configuration:

bash
nano ~/.local/bin/display-notifications.json


Example:

json
{
  "base_url": "https://ntfy.sh",
  "poll_interval_seconds": 5,
  "request_timeout_seconds": 10,
  "state_file": "display-notifications-state.json",
  "topics": [
    {
      "topic": "your-topic-name",
      "on_message": [
        ["/home/pi/.local/bin/display-pattern", "--animation", "chase"]
      ],
      "delayed_policy": "reset",
      "delayed_actions": [
        {
          "delay_seconds": 60,
          "command": [
            "/home/pi/.local/bin/display-pattern",
            "--killall"
          ]
        }
      ]
    }
  ]
}


Replace your-topic-name with your actual topic. Update command paths for your user and configuration.

on_message: commands executed when a notification arrives.
delayed_actions: commands scheduled after a delay.
reset: a new notification resets the pending timer for that action.
parallel: each notification schedules its own delayed action.

Notification fields are available to commands through environment variables, including NTFY_MESSAGE, NTFY_TITLE, NTFY_TOPIC, and NTFY_ID.

The example starts an animation when a notification arrives and stops it 60 seconds after the most recent notification.

Service management
bash
systemctl --user status display-notifications.service
systemctl --user restart display-notifications.service
systemctl --user stop display-notifications.service
journalctl --user -u display-notifications.service -f


The installer enables and starts the service. After editing the configuration, restart it to apply changes.

The worker starts with an empty topic list until configured. Notification timers are held in memory and are lost if the worker restarts.

GPIO mapping

BCM numbering is used.

Component	BCM GPIO	Physical pin
1	17	11
2	27	13
3	22	15
4	23	16
5	24	18
6	25	22

Component pin pairs are defined in display.py and reused by the testing and animation scripts.

Logging and safety

The display wrapper writes Python output to /tmp/display.log:

bash
tail -f /tmp/display.log


Continuous scripts should turn the display components off and release GPIO resources during graceful shutdown. Physical LEDs may still be affected by circuit design or electrical faults.

Use appropriate current limiting and protect Raspberry Pi GPIO pins from unsafe voltages. Keep notification topics and command configuration restricted to trusted users.
