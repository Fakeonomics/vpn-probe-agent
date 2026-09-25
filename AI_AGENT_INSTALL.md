# AI Agent Installation

This repository is designed so an AI agent can install the probe on a user's machine
without seeing or storing the user's subscription key.

## Inputs

The installer needs one of these values from the user:

- `PROBE_KEY`: the probe registration key issued by the service.
- `PROBE_BIND_CODE`: a one-time code obtained from the Telegram bot with `/probe`.

Never put a key in GitHub, source code, shell history, logs, screenshots, or an issue.
Prefer an environment variable or a protected local configuration file.

## Linux and macOS

Ask the user for the key, then run:

```sh
export PROBE_KEY='issued-key'
export PROBE_BIND_CODE='one-time-code'
curl -fsSL https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.sh | sh
probe on
probe status
```

## Windows

Ask the user for the key, then run in PowerShell:

```powershell
$env:PROBE_KEY = 'issued-key'
$env:PROBE_BIND_CODE = 'one-time-code'
irm https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.ps1 | iex
& "$env:LOCALAPPDATA\bin\probe.cmd" on
& "$env:LOCALAPPDATA\bin\probe.cmd" status
```

## Verification

The agent must show `running`. The server admin panel should show the new worker online.
The first cycle is expected to report TCP failures quickly and only mark `success` after
the real sing-box tunnel HTTP check succeeds. Never claim that a config works from a TCP
or TLS result alone.
