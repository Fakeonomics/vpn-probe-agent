# VPN Probe Agent

Residential-network probe for the Just VPN configuration service. It runs on a normal
user device, receives configurations from the service, rejects unreachable TCP endpoints
immediately, and can verify real traffic through a bundled sing-box engine when the binary
is available.

## Install

Linux and macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.sh | sh
```

Windows:

```powershell
irm https://raw.githubusercontent.com/Fakeonomics/vpn-probe-agent/main/install.ps1 | iex
```

Set `PROBE_KEY` or `PROBE_BIND_CODE` before installation when the service gives you one.
The key is stored only in the local protected configuration file and is never printed.

## Commands

```sh
probe on
probe off
probe status
```

Linux desktop sessions receive an autostart entry. Windows creates a per-user scheduled
task. macOS launchd can be added by the packaging workflow.

## Checks

1. TCP connect to the endpoint.
2. TLS handshake for protocols that use TLS.
3. Optional real HTTP GET through sing-box (`generate_204`).

A failed TCP check is reported immediately. A task that passes TCP/TLS but has no engine is
reported as inconclusive rather than falsely marked working.

## Privacy

The agent stores a random probe identifier and a server-issued probe token locally. It does
not log configuration lines or tokens. It does not change VPN, DNS, routes, firewall, or
system proxy settings. Run it as a normal user.
