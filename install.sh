
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
    local source_dir python_bin file answer
    local existing=0 keep_config=0 was_active=0
    local backup_dir stage unit_stage
    local had_unit=0

    source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
    python_bin="$(command -v python3)" ||
        die "Python 3 is required."

    for file in "${FILES[@]}"; do
        [[ -f "$source_dir/$file" ]] ||
            die "Required repository file is missing: $file"
    done

    require_systemd
    mkdir -p "$BIN_DIR" "$UNIT_DIR"

    for file in "${FILES[@]}"; do
        [[ ! -e "$BIN_DIR/$file" ]] || existing=1
    done
    [[ ! -e "$UNIT" ]] || existing=1

    if (( existing )); then
        say "Existing installation detected."
        confirm "Update installed application files and service?" ||
            { say "Cancelled; nothing changed."; return 0; }
    else
        say "Fresh installation."
    fi

    if [[ -e "$CONFIG" ]]; then
        printf '\nExisting configuration found: %s\n' "$CONFIG"
        if confirm "Keep the existing notification configuration?"; then
            keep_config=1
        else
            confirm "Replace it with the repository/default configuration?" ||
                { say "Cancelled; nothing changed."; return 0; }
        fi
    fi

    backup_dir="$HOME/abb9000display-backup-$(date +%Y%m%d-%H%M%S)"
    stage="$(mktemp -d "${TMPDIR:-/tmp}/abb9000display.XXXXXX")"
    unit_stage="$stage/$SERVICE"

    cleanup() { rm -rf "$stage"; }
    trap cleanup RETURN

    # Stage all application files before touching the installed version.
    for file in "${FILES[@]}"; do
        install -m 0755 "$source_dir/$file" "$stage/$file"
    done

    # Preserve the config when requested. Never replace saved message state.
    if (( keep_config )); then
        cp -a "$CONFIG" "$stage/display-notifications.json"
    elif [[ -f "$source_dir/display-notifications.json" ]]; then
        install -m 0600 "$source_dir/display-notifications.json" \
            "$stage/display-notifications.json"
    else
        python3 - "$stage/display-notifications.json" <<'JSON'
import json
import sys
config = {
    "base_url": "https://ntfy.sh",
    "poll_interval_seconds": 5,
    "request_timeout_seconds": 10,
    "state_file": "display-notifications-state.json",
    "topics": []
}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(config, f, indent=2)
    f.write("\n")
JSON
        chmod 600 "$stage/display-notifications.json"
    fi

    # Validate staged files before stopping the running service.
    python3 -m json.tool "$stage/display-notifications.json" >/dev/null ||
        die "Staged configuration is invalid; installed files were not changed."

    "$python_bin" -m py_compile "$stage/display-notifications.py" ||
        die "Python validation failed; installed files were not changed."

    cat > "$unit_stage" <<EOF
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
    chmod 0644 "$unit_stage"

    if command -v systemd-analyze >/dev/null 2>&1; then
        systemd-analyze --user verify "$unit_stage" ||
            die "Service unit validation failed; installed files were not changed."
    fi

    # Back up every installed file that may be replaced.
    mkdir -p "$backup_dir"
    for file in "${FILES[@]}"; do
        [[ ! -e "$BIN_DIR/$file" ]] ||
            cp -a "$BIN_DIR/$file" "$backup_dir/"
    done
    [[ ! -e "$UNIT" ]] || {
        cp -a "$UNIT" "$backup_dir/"
        had_unit=1
    }
    [[ ! -e "$CONFIG" ]] ||
        cp -a "$CONFIG" "$backup_dir/"

    # Preserve whether the service was running before the update.
    if systemctl --user is-active --quiet "$SERVICE"; then
        was_active=1
    fi

    if (( was_active || had_unit )); then
        systemctl --user stop "$SERVICE" ||
            die "Could not stop the service; installed files were not changed."
    fi

    # Install the validated application files.
    for file in "${FILES[@]}"; do
        install -m 0755 "$stage/$file" "$BIN_DIR/$file"
    done

    if (( ! keep_config )); then
        install -m 0600 "$stage/display-notifications.json" "$CONFIG"
    fi

    install -m 0644 "$unit_stage" "$UNIT"

    # Revalidate installed files before starting the service.
    if ! "$python_bin" -m py_compile "$BIN_DIR/display-notifications.py" ||
       ! python3 -m json.tool "$CONFIG" >/dev/null; then
        warn "Post-install validation failed. Service will remain stopped."
        warn "Backups are available at $backup_dir"
        return 1
    fi

    systemctl --user daemon-reload ||
        die "daemon-reload failed; service not restarted. Backup: $backup_dir"

    if (( was_active )); then
        systemctl --user enable "$SERVICE" &&
            systemctl --user restart "$SERVICE" ||
            die "Update installed, but service restart failed. Backup: $backup_dir"
    else
        systemctl --user enable "$SERVICE" ||
            die "Could not enable service. Backup: $backup_dir"
        if (( ! had_unit )); then
            systemctl --user start "$SERVICE" ||
                die "Install complete, but service start failed. Backup: $backup_dir"
        fi
    fi

    install_path_hint
    say "Installation/update complete."
    say "Configuration: $CONFIG"
    say "Saved state preserved: $STATE"
    say "Backup: $backup_dir"
    systemctl --user status "$SERVICE" --no-pager || true
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

