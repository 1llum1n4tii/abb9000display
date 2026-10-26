
#!/usr/bin/env bash
set -Eeuo pipefail

APP="abb9000display"
SERVICE="display-notifications.service"
BIN_DIR="$HOME/.local/bin"
UNIT_DIR="$HOME/.config/systemd/user"
CONFIG="$BIN_DIR/display-notifications.json"
STATE="$BIN_DIR/display-notifications-state.json"
UNIT="$UNIT_DIR/$SERVICE"

FILES=(
    display
    display-pattern
    display.py
    displaypattern.py
    test_segment.py
    test_segments.py
    display-notifications.py
)

say()  { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }
die()  { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

confirm() {
    local answer
    read -r -p "$1 [y/N] " answer
    [[ "$answer" == "y" || "$answer" == "Y" ]]
}

require_systemd() {
    command -v systemctl >/dev/null 2>&1 ||
        die "systemctl is unavailable; cannot manage the user service."

    systemctl --user show-environment >/dev/null 2>&1 ||
        die "The user systemd manager is unavailable. Log into a systemd user session and retry."
}

install_path_hint() {
    local rc block
    block='# Added by abb9000display installer
case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;
    *) export PATH="$HOME/.local/bin:$PATH" ;;
esac
# End abb9000display installer'

    for rc in "$HOME/.profile" "$HOME/.bashrc" "$HOME/.zshrc"; do
        [[ -e "$rc" ]] || continue
        if ! grep -q 'Added by abb9000display installer' "$rc"; then
            printf '\n%s\n' "$block" >> "$rc"
            say "Added ~/.local/bin to PATH in $rc"
        fi
    done
}

make_default_config() {
    python3 - "$CONFIG" <<'PY'
import json
import sys

path = sys.argv[1]
config = {
    "base_url": "https://ntfy.sh",
    "poll_interval_seconds": 5,
    "request_timeout_seconds": 10,
    "state_file": "display-notifications-state.json",
    "topics": []
}

with open(path, "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
PY
    chmod 600 "$CONFIG"
    say "Created default configuration: $CONFIG"
}

install_app() {
    local source_dir file python_bin

    source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
    python_bin="$(command -v python3)" ||
        die "Python 3 is required."

    [[ -f "$source_dir/display-notifications.py" ]] ||
        die "Run this installer from the repository containing display-notifications.py."

    for file in "${FILES[@]}"; do
        [[ -f "$source_dir/$file" ]] ||
            die "Required repository file is missing: $file"
    done

    require_systemd
    mkdir -p "$BIN_DIR" "$UNIT_DIR"

    # Do not silently overwrite unrelated commands in ~/.local/bin.
    local conflicts=()
    for file in "${FILES[@]}"; do
        [[ -e "$BIN_DIR/$file" ]] && conflicts+=("$BIN_DIR/$file")
    done

    if ((${#conflicts[@]})); then
        printf 'These destination files already exist:\n'
        printf '  %s\n' "${conflicts[@]}"
        die "Move or back up these files manually, then rerun the installer."
    fi

    [[ ! -e "$UNIT" ]] ||
        die "$UNIT already exists. Inspect it before replacing it."

    say "Installing commands and Python scripts into $BIN_DIR"
    for file in "${FILES[@]}"; do
        install -m 0755 "$source_dir/$file" "$BIN_DIR/$file"
    done

    # Preserve a user-created config in the repository if present.
    if [[ ! -e "$CONFIG" ]]; then
        if [[ -f "$source_dir/display-notifications.json" ]]; then
            install -m 0600 \
                "$source_dir/display-notifications.json" "$CONFIG"
            say "Installed repository notification configuration."
        else
            make_default_config
        fi
    else
        say "Keeping existing configuration: $CONFIG"
    fi

    # Validate JSON before enabling the service.
    python3 -m json.tool "$CONFIG" >/dev/null ||
        die "Invalid JSON in $CONFIG. Fix it and rerun installation."

    # Ensure the notification worker is compatible with this Python.
    "$python_bin" -m py_compile "$BIN_DIR/display-notifications.py"

    cat > "$UNIT" <<EOF
[Unit]
Description=ABB9000 display ntfy notifications worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$BIN_DIR
ExecStart=$python_bin $BIN_DIR/display-notifications.py --config $CONFIG
Restart=on-failure
RestartSec=5
KillSignal=SIGTERM
TimeoutStopSec=15
UMask=0077

[Install]
WantedBy=default.target
EOF

    chmod 0644 "$UNIT"

    systemctl --user daemon-reload
    systemctl --user enable --now "$SERVICE"

    install_path_hint

    say "Installation complete."
    printf '\nCommands installed:\n'
    printf '  display\n'
    printf '  display-pattern\n'
    printf '  python3 %s/test_segment.py\n' "$BIN_DIR"
    printf '  python3 %s/test_segments.py\n' "$BIN_DIR"
    printf '\nNotification service:\n'
    printf '  systemctl --user status %s\n' "$SERVICE"
    printf '  journalctl --user -u %s -f\n' "$SERVICE"
    printf '\nConfiguration:\n  %s\n' "$CONFIG"
    printf '\nEdit the config and add your ntfy topics/actions to enable notifications.\n'
    printf 'The service starts with an empty topic list until you configure it.\n'
    printf 'After changing the config, restart it with:\n'
    printf '  systemctl --user restart %s\n' "$SERVICE"
    printf '\nOpen a new shell session for PATH changes to take effect.\n'
}

uninstall_app() {
    require_systemd

    say "Stopping and disabling the notification service"
    systemctl --user disable --now "$SERVICE" 2>/dev/null || true
    rm -f "$UNIT"
    systemctl --user daemon-reload
    systemctl --user reset-failed "$SERVICE" 2>/dev/null || true

    say "Removing installed commands and Python files"
    local file
    for file in "${FILES[@]}"; do
        rm -f "$BIN_DIR/$file"
        rm -f "$BIN_DIR/__pycache__/${file%.py}".*.pyc
    done

    if confirm "Also remove the notification config and saved message state?"; then
        rm -f "$CONFIG" "$STATE"
        say "Removed notification config and state."
    else
        say "Preserved notification config and state."
    fi

    # Remove an empty cache directory, if any.
    rmdir "$BIN_DIR/__pycache__" 2>/dev/null || true

    say "Uninstallation complete."
    printf '\nThe installer does not remove your shell PATH entries.\n'
    printf 'It does not remove other files in ~/.local/bin.\n'
}

main() {
    printf '%s\n' "ABB9000 Display installer"
    printf '%s\n' "Repository: $(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
    printf '\n'
    printf '  1) Install / update setup\n'
    printf '  2) Uninstall\n'
    printf '  3) Quit\n\n'

    local choice
    read -r -p "Choose an action [1-3]: " choice

    case "$choice" in
        1) install_app ;;
        2)
            if confirm "Uninstall $APP and stop its notification service?"; then
                uninstall_app
            else
                say "Cancelled."
            fi
            ;;
        3) exit 0 ;;
        *) die "Invalid choice." ;;
    esac
}

main "$@"

