#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import shutil
import socket
import ssl
import sys
import time
import uuid
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

import singbox_engine

VERSION = "0.2.0"
DEFAULT_URL = "https://fakeonomics.online"


def config_dir():
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", Path.home())) / "vpn-probe"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "vpn-probe"


def load_env(path):
    values = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    return values


def settings(args):
    values = load_env(config_dir() / "client.env")
    values.update({k: v for k, v in os.environ.items() if k.startswith("PROBE_")})
    if args.url:
        values["PROBE_URL"] = args.url
    if args.key:
        values["PROBE_KEY"] = args.key
    return values


def state_path():
    return config_dir() / "state.json"


def load_state():
    path = state_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_state(value):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def request(url, key, method="GET", payload=None, timeout=30):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-Probe-Key"] = key
    req = Request(url, data=body, method=method, headers=headers)
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def target(config_line):
    parsed = urlsplit(config_line)
    if parsed.scheme == "vmess":
        raw = config_line.split("://", 1)[1]
        raw += "=" * (-len(raw) % 4)
        import base64
        data = json.loads(base64.b64decode(raw))
        return str(data.get("add") or data.get("host")), int(data.get("port"))
    if not parsed.hostname or not parsed.port:
        raise ValueError("endpoint missing")
    return parsed.hostname, int(parsed.port)


def tcp_probe(host, port, timeout=5):
    started = time.time()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, round((time.time() - started) * 1000), "ok"
    except socket.timeout:
        return False, round((time.time() - started) * 1000), "connect_timeout"
    except OSError as exc:
        return False, round((time.time() - started) * 1000), type(exc).__name__.lower()


def tls_probe(host, port):
    started = time.time()
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, port), timeout=5) as raw:
            raw.settimeout(5)
            with context.wrap_socket(raw, server_hostname=host):
                return True, round((time.time() - started) * 1000), "ok"
    except Exception as exc:
        return False, round((time.time() - started) * 1000), type(exc).__name__.lower()


def engine_check(config_line, engine):
    if not engine:
        return False, 0, "engine_missing"
    try:
        ok = singbox_engine.run(config_line, engine)
        return ok, 0, "ok" if ok else "end_to_end_failed"
    except Exception as exc:
        return False, 0, type(exc).__name__.lower()


def register(values, state):
    key = values.get("PROBE_KEY", "")
    if not key:
        raise RuntimeError("PROBE_KEY is missing")
    probe_id = state.get("probe_id") or "home-" + uuid.uuid4().hex[:16]
    url = values.get("PROBE_URL", DEFAULT_URL).rstrip("/")
    result = request(url + "/api/probe/register", key, "POST", {
        "probe_id": probe_id,
        "access_type": values.get("PROBE_ACCESS_TYPE", "home"),
        "country": values.get("PROBE_COUNTRY", ""),
        "region": values.get("PROBE_REGION", ""),
        "asn": int(values.get("PROBE_ASN", "0") or 0),
        "operator": values.get("PROBE_OPERATOR", ""),
        "radio_type": values.get("PROBE_RADIO", ""),
        "ip_version": "IPv4",
        "client_version": VERSION,
        "bind_code": values.get("PROBE_BIND_CODE", ""),
    })
    state = {"probe_id": result["probe_id"], "token": result["token"], "bound_user_id": result.get("user_id")}
    save_state(state)
    return state


def observation_result(ok, stage):
    if ok:
        return "success"
    if stage == "engine_missing":
        return "inconclusive"
    if stage.startswith("tls_"):
        return "tls_failed"
    if stage == "connect_timeout":
        return "connect_timeout"
    return "end_to_end_failed"


def subscription_tasks(values):
    token = values.get("PROBE_SUBSCRIPTION_TOKEN", "").strip()
    if not token:
        return None
    cache = config_dir() / "subscription.txt"
    if cache.exists() and time.time() - cache.stat().st_mtime < 21600:
        text = cache.read_text(encoding="utf-8", errors="ignore")
    else:
        base = values.get("PROBE_URL", DEFAULT_URL).rstrip("/")
        req = Request(base + "/sub/" + urllib.parse.quote(token, safe="") + "?raw=1", headers={"User-Agent": "v2rayN"})
        with urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8", errors="ignore")
        cache.write_text(text, encoding="utf-8")
        try:
            cache.chmod(0o600)
        except OSError:
            pass
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) == 1 and not lines[0].startswith(("vless://", "vmess://", "trojan://", "ss://", "hy2://", "hysteria2://")):
        try:
            text = base64.b64decode(lines[0] + "=" * (-len(lines[0]) % 4)).decode("utf-8", errors="ignore")
            lines = [line.strip() for line in text.splitlines() if line.strip()]
        except Exception:
            pass
    schemes = ("vless://", "vmess://", "trojan://", "ss://", "hy2://", "hysteria2://")
    return [{"config_line": line} for line in lines if line.startswith(schemes)]


def progress_path():
    return config_dir() / "subscription-progress.json"


def load_progress():
    try:
        return set(json.loads(progress_path().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def save_progress(done):
    path = progress_path()
    path.write_text(json.dumps(sorted(done)), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def run(values, once=False, interval=60, use_engine=True):
    state = load_state()
    if not state.get("token"):
        state = register(values, state)
    url = values.get("PROBE_URL", DEFAULT_URL).rstrip("/")
    engine = values.get("SING_BOX") or shutil.which("sing-box") if use_engine else None
    workers = min(12, max(2, os.cpu_count() or 4))
    try:
        workers = max(2, min(12, int(values.get("PROBE_WORKERS", workers))))
    except ValueError:
        pass
    while True:
        try:
            tasks = subscription_tasks(values)
            subscription_mode = tasks is not None
            done = load_progress() if subscription_mode else set()
            if tasks is not None:
                tasks = [task for task in tasks if hashlib.sha256(task["config_line"].encode()).hexdigest() not in done]
            if tasks is None:
                tasks_url = url + "/api/probe/tasks?limit=15&probe_id=" + quote(state["probe_id"], safe="")
                tasks = request(tasks_url, state["token"]).get("tasks", [])
            def check(task):
                config_line = task["config_line"]
                host, port = target(config_line)
                ok, duration, stage = tcp_probe(host, port, timeout=3)
                if ok and config_line.startswith(("vless://", "trojan://", "vmess://")):
                    tls_ok, tls_ms, tls_stage = tls_probe(host, port)
                    duration += tls_ms
                    if not tls_ok:
                        ok, stage = False, "tls_" + tls_stage
                if ok and use_engine:
                    traffic_ok, traffic_ms, traffic_stage = engine_check(config_line, engine)
                    duration += traffic_ms
                    ok = traffic_ok
                    stage = traffic_stage
                elif ok:
                    stage = "engine_missing"
                return {
                    "probe_id": state["probe_id"],
                    "config_line": config_line,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                    "duration_ms": duration,
                    "validation_result": "valid",
                    "observation_result": observation_result(ok, stage),
                    "failure_stage": None if ok else stage,
                    "network": {
                        "country": values.get("PROBE_COUNTRY", ""),
                        "region": values.get("PROBE_REGION", ""),
                        "asn": int(values.get("PROBE_ASN", "0") or 0),
                        "operator": values.get("PROBE_OPERATOR", ""),
                        "access_type": values.get("PROBE_ACCESS_TYPE", "home"),
                        "radio_type": values.get("PROBE_RADIO", ""),
                        "ip_version": "IPv4",
                        "dns_mode": "system",
                    },
                }
            for offset in range(0, len(tasks), 20):
                batch = tasks[offset:offset + 20]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    payloads = list(pool.map(check, batch))
                for payload in payloads:
                    try:
                        request(url + "/api/probe/observation", state["token"], "POST", payload)
                        if subscription_mode:
                            done.add(hashlib.sha256(payload["config_line"].encode()).hexdigest())
                    except Exception as exc:
                        code = getattr(exc, "code", type(exc).__name__)
                        print("observation error:", code, flush=True)
                    if len(tasks) > 15:
                        time.sleep(1.05)
                if tasks is not None:
                    save_progress(done)
                if offset + 20 < len(tasks):
                    time.sleep(1.05)
            if once:
                return
        except Exception as exc:
            print("probe error:", getattr(exc, "code", type(exc).__name__), flush=True)
        time.sleep(max(interval, 15))


def main():
    parser = argparse.ArgumentParser(description="Residential VPN configuration probe")
    parser.add_argument("--url")
    parser.add_argument("--key")
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-engine", action="store_true")
    args = parser.parse_args()
    run(settings(args), args.once, args.interval, not args.no_engine)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
