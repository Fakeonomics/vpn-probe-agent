#!/bin/sh
set -eu

PREFIX="${PREFIX:-$HOME/.local}"
APP_DIR="$PREFIX/lib/vpn-probe"
BIN_DIR="$PREFIX/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/vpn-probe"
URL="${PROBE_URL:-https://fakeonomics.online}"

mkdir -p "$APP_DIR" "$BIN_DIR" "$CONFIG_DIR"
cp "$(dirname "$0")/probe_agent.py" "$APP_DIR/probe_agent.py"
cp "$(dirname "$0")/singbox_engine.py" "$APP_DIR/singbox_engine.py"
chmod 700 "$APP_DIR/probe_agent.py"

if [ ! -f "$CONFIG_DIR/client.env" ]; then
    umask 077
    {
        printf 'PROBE_URL=%s\n' "$URL"
        printf 'PROBE_KEY=%s\n' "${PROBE_KEY:-}"
        printf 'PROBE_BIND_CODE=%s\n' "${PROBE_BIND_CODE:-}"
        printf 'PROBE_ACCESS_TYPE=%s\n' "${PROBE_ACCESS_TYPE:-home}"
        printf 'SING_BOX=%s\n' "${SING_BOX:-$PREFIX/bin/sing-box}"
    } > "$CONFIG_DIR/client.env"
    chmod 600 "$CONFIG_DIR/client.env"
fi

cat > "$BIN_DIR/probe" <<EOF
#!/bin/sh
set -eu
CONFIG_DIR="${CONFIG_DIR}"
. "\$CONFIG_DIR/client.env"
PID="\$CONFIG_DIR/probe.pid"
LOG="\$CONFIG_DIR/probe.log"
case "\${1:-status}" in
  on|start)
    if [ -s "\$PID" ] && kill -0 "\$(cat "\$PID")" 2>/dev/null; then exit 0; fi
    nohup python3 "$APP_DIR/probe_agent.py" >>"\$LOG" 2>&1 &
    echo \$! >"\$PID"
    ;;
  off|stop)
    if [ -s "\$PID" ]; then kill "\$(cat "\$PID")" 2>/dev/null || true; rm -f "\$PID"; fi
    ;;
  status)
    if [ -s "\$PID" ] && kill -0 "\$(cat "\$PID")" 2>/dev/null; then echo running; else echo stopped; fi
    ;;
  *) echo "usage: probe {on|off|status}" >&2; exit 2 ;;
esac
EOF
chmod 700 "$BIN_DIR/probe"

case "${XDG_CURRENT_DESKTOP:-}" in
  *GNOME*|*KDE*|*XFCE*)
    mkdir -p "$HOME/.config/autostart"
    cat > "$HOME/.config/autostart/vpn-probe.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=VPN Probe
Exec=$BIN_DIR/probe on
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
    ;;
esac

if [ "$(uname -s)" = "Darwin" ]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cat > "$HOME/Library/LaunchAgents/com.fakeonomics.vpn-probe.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.fakeonomics.vpn-probe</string>
<key>ProgramArguments</key><array><string>python3</string><string>$APP_DIR/probe_agent.py</string></array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$CONFIG_DIR/probe.log</string>
<key>StandardErrorPath</key><string>$CONFIG_DIR/probe.log</string>
</dict></plist>
EOF
    launchctl load -w "$HOME/Library/LaunchAgents/com.fakeonomics.vpn-probe.plist" 2>/dev/null || true
fi

printf 'Installed: %s\n' "$BIN_DIR/probe"
printf 'Run: probe on\n'
