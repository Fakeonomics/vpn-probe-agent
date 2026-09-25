import base64
import json
import os
import socket
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, unquote, urlsplit


def _b64(value):
    return base64.b64decode(value + "=" * (-len(value) % 4)).decode()


def _tls(query, host):
    security = query.get("security", [""])[0]
    if security not in ("tls", "reality"):
        return None
    tls = {"enabled": True, "server_name": query.get("sni", [host])[0]}
    if security == "reality":
        tls["reality"] = {
            "enabled": True,
            "public_key": query.get("pbk", [""])[0],
            "short_id": query.get("sid", [""])[0],
        }
    return tls


def _transport(query):
    kind = query.get("type", ["tcp"])[0]
    if kind in ("", "tcp", "raw"):
        return None
    result = {"type": kind}
    if kind == "ws":
        result["path"] = query.get("path", ["/"])[0]
        if query.get("host"):
            result["headers"] = {"Host": query["host"][0]}
    elif kind == "grpc":
        result["service_name"] = query.get("serviceName", query.get("path", [""]))[0]
    elif kind in ("http", "xhttp"):
        result["host"] = [query.get("host", [""])[0]]
        result["path"] = query.get("path", ["/"])[0]
    return result


def _endpoint(config):
    parsed = urlsplit(config)
    scheme = parsed.scheme.lower()
    if scheme == "vmess":
        data = json.loads(_b64(config.split("://", 1)[1]))
        return {
            "type": "vmess",
            "server": data.get("add") or data.get("host"),
            "server_port": int(data.get("port")),
            "uuid": data.get("id"),
            "alter_id": int(data.get("aid", 0)),
            "security": data.get("scy", "auto"),
        }
    if scheme in ("vless", "trojan"):
        query = parse_qs(parsed.query)
        return {
            "type": scheme,
            "server": parsed.hostname,
            "server_port": parsed.port or 443,
            "uuid": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "flow": query.get("flow", [""])[0],
            "tls": _tls(query, parsed.hostname),
            "transport": _transport(query),
        }
    if scheme in ("hy2", "hysteria2"):
        query = parse_qs(parsed.query)
        return {
            "type": "hysteria2",
            "server": parsed.hostname,
            "server_port": parsed.port or 443,
            "password": unquote(parsed.username or ""),
            "obfs": query.get("obfs", [""])[0],
            "tls": _tls(query, parsed.hostname) or {"enabled": True, "server_name": parsed.hostname},
        }
    if scheme == "ss":
        raw = config.split("://", 1)[1].split("#", 1)[0]
        raw = _b64(raw) if "@" not in raw else unquote(raw)
        method, rest = raw.split(":", 1)
        password, endpoint = rest.rsplit("@", 1)
        host, port = endpoint.rsplit(":", 1)
        return {"type": "shadowsocks", "server": host, "server_port": int(port), "method": method, "password": password}
    raise ValueError("unsupported protocol")


def _outbound(config):
    item = _endpoint(config)
    if item["type"] == "vmess":
        item["tls"] = {"enabled": str(item.get("security", "auto")).lower() in ("tls", "reality")}
    if item["type"] == "shadowsocks":
        item["tag"] = "proxy"
        return item
    if item["type"] == "vless":
        item["security"] = "none"
    item["tag"] = "proxy"
    return item


def _config(config_line, port):
    return {
        "log": {"level": "error"},
        "inbounds": [{"type": "mixed", "tag": "mixed", "listen": "127.0.0.1", "listen_port": port}],
        "outbounds": [_outbound(config_line)],
        "route": {"final": "proxy"},
    }


def _recv(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise OSError("proxy closed")
        data += chunk
    return data


def _http_get(port):
    with socket.create_connection(("127.0.0.1", port), timeout=4) as sock:
        sock.settimeout(8)
        sock.sendall(b"\x05\x01\x00")
        if _recv(sock, 2)[1] != 0:
            raise OSError("socks auth failed")
        host = b"www.gstatic.com"
        sock.sendall(b"\x05\x01\x00\x03" + bytes([len(host)]) + host + (80).to_bytes(2, "big"))
        response = _recv(sock, 4)
        if response[1] != 0:
            raise OSError("socks connect failed")
        request = b"GET /generate_204 HTTP/1.1\r\nHost: www.gstatic.com\r\nConnection: close\r\n\r\n"
        sock.sendall(request)
        return _recv(sock, 12).startswith(b"HTTP/")


def run(config_line, engine):
    probe_socket = socket.socket()
    probe_socket.bind(("127.0.0.1", 0))
    port = probe_socket.getsockname()[1]
    probe_socket.close()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(_config(config_line, port), handle)
        path = handle.name
    process = subprocess.Popen([engine, "run", "-c", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 8
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    return _http_get(port)
            except OSError:
                time.sleep(0.2)
        return False
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
        os.unlink(path)
