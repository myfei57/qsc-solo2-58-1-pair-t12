"""End-to-end tests for the gateway: versioning, windows, limits, replay."""

from __future__ import annotations

import http.client
import json
import shutil
import tempfile
import unittest

from portpower.bootstrap import create_server
from portpower.config import Settings


def call(
    server,
    method: str,
    path: str,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict, dict[str, str]]:
    connection = http.client.HTTPConnection(*server.address, timeout=5)
    payload = json.dumps(body) if body is not None else None
    request_headers = dict(headers or {})
    if payload is not None:
        request_headers.setdefault("Content-Type", "application/json")
    connection.request(method, path, body=payload, headers=request_headers)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    parsed = json.loads(raw.decode("utf-8")) if raw else {}
    response_headers = {name.lower(): value for name, value in response.getheaders()}
    return response.status, parsed, response_headers


class ServerCase(unittest.TestCase):
    """One server with a throwaway data directory per test class."""

    server = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.data_dir = tempfile.mkdtemp(prefix="portpower-test-")
        settings = Settings(data_dir=cls.data_dir, host="127.0.0.1", port=0)
        cls.server = create_server(settings)
        cls.server.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        shutil.rmtree(cls.data_dir, ignore_errors=True)

    def call(self, method, path, body=None, headers=None):
        return call(self.server, method, path, body, headers)

    def connect(self, berth, ship, extra=None, headers=None):
        body = {"berth": berth, "ship": ship, "phase": "ABC"}
        body.update(extra or {})
        return self.call("POST", "/connect", body, headers)

    def disconnect(self, berth):
        return self.call("POST", "/disconnect", {"berth": berth, "final_value": 5})


class TestVersioning(ServerCase):
    """Version negotiation and transition windows (limiter disabled)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        status, _, _ = call(
            cls.server,
            "POST",
            "/ratelimit",
            {"enabled": False},
            headers={"X-Client-Id": "versioning-setup"},
        )
        assert status == 200

    def test_current_version_passes_through_unchanged(self):
        status, body, headers = self.connect(
            "A1", "ship-current", {"frequency": 50.0, "load": 100.0}
        )
        try:
            self.assertEqual(status, 200, body)
            self.assertIn("breaker_state", body)
            self.assertIn("headroom", body)
            self.assertIn("cable_rating", body)
            self.assertEqual(headers.get("x-api-version"), "v2")
            self.assertEqual(headers.get("x-api-current-version"), "v2")
            self.assertNotIn("deprecation", headers)
        finally:
            self.disconnect("A1")

    def test_legacy_fields_are_sniffed_and_response_is_legacy_shaped(self):
        status, body, headers = self.connect(
            "A2", "ship-legacy", {"freq": 50.0, "kw": 120.0, "temp": 30.0}
        )
        try:
            self.assertEqual(status, 200, body)
            self.assertIn("breaker", body)
            self.assertNotIn("breaker_state", body)
            self.assertNotIn("headroom", body)
            self.assertNotIn("cable_rating", body)
            self.assertEqual(body["demand"], 120.0)
            self.assertEqual(headers.get("x-api-version"), "v1")
        finally:
            self.disconnect("A2")

    def test_explicit_legacy_header_without_sniffable_fields(self):
        status, body, headers = self.connect(
            "B1",
            "ship-explicit",
            {"frequency": 50.0, "load": 100.0},
            headers={"X-Api-Version": "v1"},
        )
        try:
            self.assertEqual(status, 200, body)
            self.assertIn("breaker", body)
            self.assertNotIn("breaker_state", body)
            self.assertEqual(headers.get("x-api-version"), "v1")
        finally:
            self.disconnect("B1")

    def test_conflicting_field_names_are_rejected_without_explicit_version(self):
        status, body, _ = self.connect(
            "B2", "ship-conflict", {"freq": 50.0, "kw": 100.0, "load": 200.0}
        )
        self.assertEqual(status, 400, body)
        self.assertIn("both map to", body["error"])

    def test_explicit_version_resolves_field_conflict(self):
        conflict = {"freq": 50.0, "kw": 100.0, "load": 200.0}
        # v1's own name (kw) wins when v1 is declared
        status, body, _ = self.connect(
            "C1", "ship-wins-v1", conflict, headers={"X-Api-Version": "v1"}
        )
        try:
            self.assertEqual(status, 200, body)
            self.assertEqual(body["demand"], 100.0)
        finally:
            self.disconnect("C1")
        # the canonical name wins when the current version is declared
        status, body, _ = self.connect(
            "C1", "ship-wins-v2", conflict, headers={"X-Api-Version": "v2"}
        )
        try:
            self.assertEqual(status, 200, body)
            self.assertEqual(body["demand"], 200.0)
        finally:
            self.disconnect("C1")

    def test_conflicting_version_declarations_are_rejected(self):
        status, body, _ = self.connect(
            "A1",
            "ship-decl",
            {"frequency": 50.0, "load": 100.0, "version": "v2"},
            headers={"X-Api-Version": "v1"},
        )
        self.assertEqual(status, 400, body)
        self.assertIn("conflicting version declarations", body["error"])

    def test_unknown_version_is_rejected_with_supported_list(self):
        status, body, _ = self.connect(
            "A1",
            "ship-unknown",
            {"frequency": 50.0, "load": 100.0},
            headers={"X-Api-Version": "v9"},
        )
        self.assertEqual(status, 400, body)
        self.assertIn("v1", body["error"])
        self.assertIn("v2", body["error"])

    def test_deprecated_window_adds_warning_headers(self):
        status, _, _ = self.call(
            "POST",
            "/versions/window",
            {
                "path": "/connect",
                "version": "v1",
                "deprecated_at": "2026-01-01T00:00:00Z",
                "sunset_at": "2099-01-01T00:00:00Z",
            },
        )
        self.assertEqual(status, 200)
        try:
            status, body, headers = self.connect(
                "A1", "ship-depr", {"freq": 50.0, "kw": 100.0}
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(headers.get("deprecation"), "true")
            self.assertIn("sunset", headers)
        finally:
            self.disconnect("A1")
            self.call(
                "DELETE", "/versions/window", {"path": "/connect", "version": "v1"}
            )

    def test_retired_version_is_gone_but_current_still_works(self):
        status, _, _ = self.call(
            "POST",
            "/versions/window",
            {
                "path": "/connect",
                "version": "v1",
                "deprecated_at": "2020-01-01T00:00:00Z",
                "sunset_at": "2021-01-01T00:00:00Z",
            },
        )
        self.assertEqual(status, 200)
        try:
            status, body, _ = self.connect(
                "A1", "ship-gone", {"freq": 50.0, "kw": 100.0}
            )
            self.assertEqual(status, 410, body)
            self.assertEqual(body["version"], "v1")
            self.assertEqual(body["current_version"], "v2")
            self.assertIn("sunset_at", body)
            # the current version is unaffected
            status, body, _ = self.connect(
                "A1", "ship-still-ok", {"frequency": 50.0, "load": 100.0}
            )
            self.assertEqual(status, 200, body)
            self.disconnect("A1")
        finally:
            self.call(
                "DELETE", "/versions/window", {"path": "/connect", "version": "v1"}
            )

    def test_window_requires_a_known_path_and_version(self):
        status, body, _ = self.call(
            "POST",
            "/versions/window",
            {
                "path": "/nope",
                "version": "v1",
                "deprecated_at": "2026-01-01T00:00:00Z",
                "sunset_at": "2027-01-01T00:00:00Z",
            },
        )
        self.assertEqual(status, 400, body)
        status, body, _ = self.call(
            "POST",
            "/versions/window",
            {
                "path": "/connect",
                "version": "v2",
                "deprecated_at": "2026-01-01T00:00:00Z",
                "sunset_at": "2027-01-01T00:00:00Z",
            },
        )
        self.assertEqual(status, 400, body)
        self.assertIn("current version", body["error"])

    def test_usage_report_names_the_legacy_clients(self):
        client = {"X-Client-Id": "scada-north"}
        status, _, _ = self.connect(
            "A2", "ship-metered", {"freq": 50.0, "kw": 100.0}, headers=client
        )
        self.assertEqual(status, 200)
        self.disconnect("A2")
        status, body, _ = self.call("GET", "/versions/usage?path=/connect")
        self.assertEqual(status, 200)
        clients = body["paths"]["/connect"]["v1"]["clients"]
        self.assertIn("scada-north", clients)
        self.assertGreaterEqual(clients["scada-north"]["count"], 1)
        self.assertIn("last_seen", clients["scada-north"])

    def test_versions_endpoint_describes_contracts(self):
        status, body, _ = self.call("GET", "/versions")
        self.assertEqual(status, 200)
        connect = body["paths"]["/connect"]
        self.assertEqual(connect["current_version"], "v2")
        self.assertEqual(connect["versions"]["v1"]["request_fields"]["kw"], "load")
        self.assertIsNone(connect["versions"]["v1"]["window"])

    def test_legacy_meter_fields(self):
        status, _, _ = self.connect(
            "B2", "ship-meter", {"frequency": 50.0, "load": 100.0}
        )
        self.assertEqual(status, 200)
        try:
            reading = {"berth": "B2", "ts": "2026-10-04T00:00:00Z", "reading": 42.0}
            status, body, headers = self.call("POST", "/meter", reading)
            self.assertEqual(status, 200, body)
            self.assertTrue(body["recorded"])
            self.assertNotIn("duplicate", body)
            self.assertEqual(headers.get("x-api-version"), "v1")
            # the canonical shape still works and reports the duplicate
            status, body, _ = self.call(
                "POST",
                "/meter",
                {"berth": "B2", "timestamp": "2026-10-04T00:00:00Z", "value": 42.0},
            )
            self.assertEqual(status, 200, body)
            self.assertTrue(body["duplicate"])
        finally:
            self.disconnect("B2")


class TestRateLimit(ServerCase):
    """Write throttling: per-client buckets, reads exempt, 429 contract."""

    def setUp(self) -> None:
        self.operator = {"X-Client-Id": f"operator-{self._testMethodName}"}
        status, _, _ = self.call(
            "POST",
            "/ratelimit",
            {"capacity": 2, "refill_per_second": 0.01},
            headers=self.operator,
        )
        assert status == 200

    def tearDown(self) -> None:
        self.call(
            "POST",
            "/ratelimit",
            {"capacity": 20, "refill_per_second": 5, "enabled": True},
            headers=self.operator,
        )

    def write(self, client):
        return self.call(
            "POST",
            "/quota",
            {"ship": f"ship-of-{client}", "limit": 50},
            headers={"X-Client-Id": client},
        )

    def test_writes_are_limited_and_reads_are_not(self):
        client = "flood-client"
        self.assertEqual(self.write(client)[0], 200)
        self.assertEqual(self.write(client)[0], 200)
        status, body, headers = self.write(client)
        self.assertEqual(status, 429, body)
        self.assertIn("retry_after_seconds", body)
        self.assertIn("retry-after", headers)
        self.assertGreater(float(headers["retry-after"]), 0)
        # read-only requests are never metered
        for path in ("/quota", "/health", "/status", "/versions"):
            status, _, _ = self.call("GET", path)
            self.assertEqual(status, 200, path)

    def test_limit_is_per_client(self):
        self.assertEqual(self.write("client-a")[0], 200)
        self.assertEqual(self.write("client-a")[0], 200)
        self.assertEqual(self.write("client-a")[0], 429)
        self.assertEqual(self.write("client-b")[0], 200)

    def test_limit_can_be_disabled_for_emergencies(self):
        self.call("POST", "/ratelimit", {"enabled": False}, headers=self.operator)
        for _ in range(5):
            self.assertEqual(self.write("open-client")[0], 200)
        status, body, _ = self.call("GET", "/ratelimit")
        self.assertEqual(status, 200)
        self.assertFalse(body["config"]["enabled"])

    def test_invalid_limit_config_is_rejected(self):
        status, body, _ = self.call(
            "POST", "/ratelimit", {"capacity": 0}, headers=self.operator
        )
        self.assertEqual(status, 400, body)
        status, body, _ = self.call(
            "POST", "/ratelimit", {"refill_per_second": -1}, headers=self.operator
        )
        self.assertEqual(status, 400, body)


class TestIdempotency(ServerCase):
    """Idempotent replay: stored responses, no re-execution, no throttling."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        status, _, _ = call(
            cls.server,
            "POST",
            "/ratelimit",
            {"enabled": False},
            headers={"X-Client-Id": "idempotency-setup"},
        )
        assert status == 200

    def setUp(self) -> None:
        status, _, _ = self.call(
            "POST", "/quota", {"ship": "idem-ship", "limit": 100}
        )
        assert status == 200

    def reserve(self, key=None, client="idem-client"):
        headers = {"X-Client-Id": client}
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.call(
            "POST", "/quota/reserve", {"ship": "idem-ship", "demand": 10}, headers
        )

    def test_replay_returns_stored_response_without_reexecuting(self):
        status, first, _ = self.reserve(key="op-1")
        self.assertEqual(status, 200, first)
        self.assertEqual(first["remaining"], 90.0)
        status, replayed, headers = self.reserve(key="op-1")
        self.assertEqual(status, 200)
        self.assertEqual(replayed, first)
        self.assertEqual(headers.get("idempotency-replayed"), "true")
        # a fresh key really does execute again
        status, second, _ = self.reserve(key="op-2")
        self.assertEqual(status, 200)
        self.assertEqual(second["remaining"], 80.0)

    def test_replay_is_never_rate_limited(self):
        operator = {"X-Client-Id": "flood-operator"}
        self.call(
            "POST",
            "/ratelimit",
            {"enabled": True, "capacity": 1, "refill_per_second": 0.01},
            headers=operator,
        )
        try:
            status, first, _ = self.reserve(key="op-flood")
            self.assertEqual(status, 200, first)
            # the bucket is now empty: plain writes are refused...
            status, body, _ = self.call(
                "POST",
                "/quota",
                {"ship": "other", "limit": 1},
                headers={"X-Client-Id": "idem-client"},
            )
            self.assertEqual(status, 429, body)
            # ...but the idempotent resend still gets its answer
            status, replayed, headers = self.reserve(key="op-flood")
            self.assertEqual(status, 200, replayed)
            self.assertEqual(replayed, first)
            self.assertEqual(headers.get("idempotency-replayed"), "true")
        finally:
            self.call(
                "POST",
                "/ratelimit",
                {"enabled": False, "capacity": 20, "refill_per_second": 5},
                headers=operator,
            )

    def test_failed_requests_are_not_cached(self):
        headers = {"Idempotency-Key": "bad-op", "X-Client-Id": "idem-client"}
        status, body, _ = self.call(
            "POST", "/quota/reserve", {"ship": "idem-ship"}, headers
        )
        self.assertEqual(status, 400, body)
        status, _, resp_headers = self.call(
            "POST", "/quota/reserve", {"ship": "idem-ship"}, headers
        )
        self.assertEqual(status, 400)
        self.assertNotIn("idempotency-replayed", resp_headers)

    def test_keys_are_scoped_per_client(self):
        status, first, _ = self.reserve(key="shared-key")
        self.assertEqual(status, 200)
        self.assertEqual(first["remaining"], 90.0)
        # the same key under another client is a different operation
        status, body, resp_headers = self.reserve(key="shared-key", client="other")
        self.assertEqual(status, 200)
        self.assertNotIn("idempotency-replayed", resp_headers)
        self.assertEqual(body["remaining"], 80.0)


if __name__ == "__main__":
    unittest.main()
