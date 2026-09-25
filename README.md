# VPN Probe Agent

Residential-network probe for the Just VPN configuration service. It runs on a normal
user device, receives configurations from the service, rejects unreachable TCP endpoints
immediately, and can verify real traffic through a bundled sing-box engine when the binary
is available.

## Install

Get a registration key or one-time Telegram binding code from the service first. The key is
required for registration and is not included in this public repository.

Linux and macOS:

```sh
export PROBE_KEY='issued-key'
export PROBE_BIND_CODE='one-time-code'
curl -fsSL https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.sh | sh
```

Windows:

```powershell
$env:PROBE_KEY = 'issued-key'
$env:PROBE_BIND_CODE = 'one-time-code'
irm https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.ps1 | iex
```

The key is stored only in the local protected configuration file and is never printed.
For an AI-assisted installation, follow [AI_AGENT_INSTALL.md](AI_AGENT_INSTALL.md).

## Commands

```sh
probe on
probe off
probe status
```

Linux desktop sessions receive an autostart entry. Windows creates a per-user scheduled
task. macOS launchd can be added by the packaging workflow.

## Checks

When `PROBE_SUBSCRIPTION_TOKEN` is set, the agent checks the configs currently returned by
that subscription first (raw catalog targets), then resumes unfinished targets on later runs.
It does not spend the first pass on the full server catalog.

1. TCP connect to the endpoint.
2. TLS handshake for protocols that use TLS.
3. Optional real HTTP GET through sing-box (`generate_204`).

A failed TCP check is reported immediately. A task that passes TCP/TLS but has no engine is
reported as inconclusive rather than falsely marked working.

## Privacy

The agent stores a random probe identifier and a server-issued probe token locally. It does
not log configuration lines or tokens. It does not change VPN, DNS, routes, firewall, or
system proxy settings. Run it as a normal user.
