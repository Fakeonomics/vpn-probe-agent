import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import probe_agent
import singbox_engine


class ProbeTests(unittest.TestCase):
    def test_target_vless(self):
        host, port = probe_agent.target("vless://uuid@example.com:443?security=tls#x")
        self.assertEqual((host, port), ("example.com", 443))

    def test_target_vmess(self):
        raw = "eyJhZGQiOiAiZXhhbXBsZS5jb20iLCAicG9ydCI6IDQ0MywgImlkIjogInV1aWQifQ=="
        host, port = probe_agent.target("vmess://" + raw)
        self.assertEqual((host, port), ("example.com", 443))

    def test_tcp_failure_is_immediate(self):
        with patch("probe_agent.socket.create_connection", side_effect=OSError("refused")):
            ok, _, stage = probe_agent.tcp_probe("127.0.0.1", 1, timeout=0.01)
        self.assertFalse(ok)
        self.assertNotEqual(stage, "ok")

    def test_observation_result(self):
        self.assertEqual(probe_agent.observation_result(True, "ok"), "success")
        self.assertEqual(probe_agent.observation_result(False, "tls_failed"), "tls_failed")
        self.assertEqual(probe_agent.observation_result(False, "engine_missing"), "inconclusive")

    def test_singbox_vless_config(self):
        item = singbox_engine._outbound("vless://uuid@example.com:443?security=tls&sni=example.com#x")
        self.assertEqual(item["type"], "vless")
        self.assertEqual(item["server"], "example.com")
        self.assertTrue(item["tls"]["enabled"])

    def test_singbox_shadowsocks_config(self):
        item = singbox_engine._outbound("ss://aes-256-gcm:pass@example.com:8388#x")
        self.assertEqual(item["type"], "shadowsocks")
        self.assertEqual(item["method"], "aes-256-gcm")
        self.assertEqual(item["password"], "pass")

    def test_config_file_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(probe_agent, "config_dir", return_value=Path(directory)):
                probe_agent.save_state({"probe_id": "test", "token": "secret"})
                mode = (Path(directory) / "state.json").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)


if __name__ == "__main__":
    unittest.main()
