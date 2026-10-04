"""End-to-end checks for the versioned, rate-limited console gateway."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, timedelta
from typing import Any

from portpower.console.gateway import Gateway
from portpower.console.http import Request
from portpower.console.ratelimit import IdempotencyStore, RateLimiter
from portpower.console.routes import build_router
from portpower.console.runtime import build_runtime
from portpower.console.usage import VersionUsage
from portpower.console.versioning import VersionWindow, default_windows
from portpower.meter.binder import Binding
from portpower.ns.harbor import Harbor
from portpower.store.kvstore import RecordStore

TODAY = date(2026, 10, 4)


def make_request(
    method: str,
    path: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    query: dict[str, list[str]] | None = None,
    client: str = "10.0.0.1",
) -> Request:
    return Request(
        method=method,
        path=path,
        query=query or {},
        headers={name.lower(): value for name, value in (headers or {}).items()},
        body=json.dumps(body).encode("utf-8") if body is not None else b"",
        client=client,
    )


def body_of(response) -> Any:
    return json.loads(response.payload.decode("utf-8"))


class GatewayCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = RecordStore(self.tmp.name)
        self.store.load()
        self.runtime = build_runtime(Harbor("pp-north", "port-north"), self.store)
        self.router = build_router(self.runtime)
        self.clock = [1000.0]

    def make_gateway(
        self,
        *,
        windows: dict[str, VersionWindow] | None = None,
        capacity: float = 20.0,
        refill: float = 5.0,
        today: date = TODAY,
    ) -> Gateway:
        from portpower.console.gateway import register_management_routes

        gateway = Gateway(
            self.router,
            windows=windows if windows is not None else default_windows(),
            limiter=RateLimiter(
                capacity, refill, 10000.0, 10000.0, clock=lambda: self.clock[0]
            ),
            idempotency=IdempotencyStore(ttl_seconds=3600, clock=lambda: self.clock[0]),
            usage=VersionUsage(self.store),
            replay_detectors={"/meter": self._meter_replay},
            today=lambda: today,
        )
        register_management_routes(self.router, gateway)
        return gateway

    def _meter_replay(self, request: Request) -> bool:
        from portpower.console.gateway import _meter_replay_detector

        return _meter_replay_detector(self.runtime)(request)


class VersionNegotiationTests(GatewayCase):
    def test_legacy_client_posts_old_fields_and_gets_old_response(self) -> None:
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "vessel-1", "limit": 100})
        )
        self.assertEqual(response.status, 200)
        body = body_of(response)
        self.assertEqual(body["ship"], "vessel-1")
        self.assertNotIn("ship_id", body)
        self.assertEqual(response.headers["X-API-Version"], "v1")
        self.assertEqual(response.headers["Deprecation"], "true")

    def test_explicit_current_version_uses_new_fields(self) -> None:
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship_id": "vessel-2", "limit": 50},
                headers={"X-API-Version": "v2"},
            )
        )
        self.assertEqual(response.status, 200)
        body = body_of(response)
        self.assertEqual(body["ship_id"], "vessel-2")
        self.assertNotIn("ship", body)
        self.assertEqual(response.headers["X-API-Version"], "v2")
        self.assertNotIn("Deprecation", response.headers)

    def test_conflict_resolved_by_explicit_version(self) -> None:
        gateway = self.make_gateway()
        payload = {"ship": "old-ship", "ship_id": "new-ship", "limit": 10}
        legacy = gateway.dispatch(
            make_request("POST", "/quota", payload, headers={"X-API-Version": "v1"})
        )
        self.assertEqual(body_of(legacy)["ship"], "old-ship")
        current = gateway.dispatch(
            make_request("POST", "/quota", payload, headers={"X-API-Version": "v2"})
        )
        self.assertEqual(body_of(current)["ship_id"], "new-ship")

    def test_version_is_never_guessed_from_fields(self) -> None:
        # The default is v1: an unmarked request with only new-style fields
        # still negotiates v1 (and is tolerated), it does not become v2.
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request("POST", "/quota", {"ship_id": "vessel-3", "limit": 5})
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["X-API-Version"], "v1")
        self.assertEqual(body_of(response)["ship"], "vessel-3")

    def test_default_version_decides_conflicts(self) -> None:
        windows = default_windows()
        quota = windows["/quota"]
        windows["/quota"] = VersionWindow(
            path="/quota", default="v2", fields=dict(quota.fields)
        )
        gateway = self.make_gateway(windows=windows)
        response = gateway.dispatch(
            make_request(
                "POST", "/quota", {"ship": "old-ship", "ship_id": "new-ship", "limit": 1}
            )
        )
        self.assertEqual(response.headers["X-API-Version"], "v2")
        self.assertEqual(body_of(response)["ship_id"], "new-ship")

    def test_unknown_version_rejected_with_supported_list(self) -> None:
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship": "x", "limit": 1},
                headers={"X-API-Version": "v9"},
            )
        )
        self.assertEqual(response.status, 400)
        self.assertEqual(body_of(response)["supported"], ["v1", "v2"])

    def test_query_parameter_selects_version(self) -> None:
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship_id": "vessel-4", "limit": 5},
                query={"version": ["v2"]},
            )
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers["X-API-Version"], "v2")

    def test_connect_end_to_end_with_legacy_fields(self) -> None:
        gateway = self.make_gateway()
        response = gateway.dispatch(
            make_request(
                "POST",
                "/connect",
                {
                    "berth": "A1",
                    "ship": "vessel-1",
                    "phase": "ABC",
                    "frequency": 50,
                    "load": 120,
                    "temperature": 30,
                },
            )
        )
        self.assertEqual(response.status, 200, body_of(response))
        body = body_of(response)
        self.assertEqual(body["ship"], "vessel-1")
        self.assertNotIn("ship_id", body)
        self.assertEqual(body["berth"], "A1")


class TransitionWindowTests(GatewayCase):
    def test_legacy_rejected_after_window_closes(self) -> None:
        windows = default_windows()
        quota = windows["/quota"]
        windows["/quota"] = VersionWindow(
            path="/quota",
            legacy_end=TODAY - timedelta(days=1),
            fields=dict(quota.fields),
        )
        gateway = self.make_gateway(windows=windows)
        legacy = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "vessel-1", "limit": 1})
        )
        self.assertEqual(legacy.status, 410)
        body = body_of(legacy)
        self.assertIn("retired", body["error"])
        self.assertEqual(body["supported"], ["v2"])
        current = gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship_id": "vessel-1", "limit": 1},
                headers={"X-API-Version": "v2"},
            )
        )
        self.assertEqual(current.status, 200)

    def test_legacy_rejected_before_window_opens(self) -> None:
        windows = default_windows()
        quota = windows["/quota"]
        windows["/quota"] = VersionWindow(
            path="/quota",
            legacy_start=TODAY + timedelta(days=1),
            fields=dict(quota.fields),
        )
        gateway = self.make_gateway(windows=windows)
        response = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "vessel-1", "limit": 1})
        )
        self.assertEqual(response.status, 400)
        self.assertIn("not accepted before", body_of(response)["error"])

    def test_windows_are_independent_per_path(self) -> None:
        self.runtime.binder.bind(Binding(berth="A1", ship="vessel-1"))
        windows = default_windows()
        quota = windows["/quota"]
        windows["/quota"] = VersionWindow(
            path="/quota",
            legacy_end=TODAY - timedelta(days=1),
            fields=dict(quota.fields),
        )
        gateway = self.make_gateway(windows=windows)
        retired = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "vessel-1", "limit": 1})
        )
        self.assertEqual(retired.status, 410)
        open_window = gateway.dispatch(
            make_request(
                "POST",
                "/meter",
                {"berth": "A1", "timestamp": "2026-10-04T00:00:00", "value": 12.5},
            )
        )
        self.assertEqual(open_window.status, 200, body_of(open_window))
        self.assertTrue(body_of(open_window)["recorded"])

    def test_sunset_headers_advertise_the_end_date(self) -> None:
        windows = default_windows()
        quota = windows["/quota"]
        windows["/quota"] = VersionWindow(
            path="/quota",
            legacy_end=TODAY + timedelta(days=30),
            fields=dict(quota.fields),
        )
        gateway = self.make_gateway(windows=windows)
        response = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "vessel-1", "limit": 1})
        )
        self.assertEqual(response.status, 200)
        self.assertIn("Sunset", response.headers)
        self.assertTrue(response.headers["Deprecation"].startswith("@"))


class RateLimitTests(GatewayCase):
    def test_burst_rejected_with_retry_after(self) -> None:
        gateway = self.make_gateway(capacity=2, refill=0.5)
        for _ in range(2):
            ok = gateway.dispatch(
                make_request("POST", "/quota", {"ship": "s", "limit": 1})
            )
            self.assertEqual(ok.status, 200)
        blocked = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s", "limit": 1})
        )
        self.assertEqual(blocked.status, 429)
        body = body_of(blocked)
        self.assertEqual(body["scope"], "client")
        self.assertEqual(body["retry_after_seconds"], 2)
        self.assertEqual(blocked.headers["Retry-After"], "2")

    def test_reads_are_never_limited(self) -> None:
        gateway = self.make_gateway(capacity=1, refill=0.1)
        for _ in range(10):
            response = gateway.dispatch(make_request("GET", "/quota"))
            self.assertEqual(response.status, 200)

    def test_limit_recovers_as_tokens_refill(self) -> None:
        gateway = self.make_gateway(capacity=1, refill=1.0)
        first = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s", "limit": 1})
        )
        self.assertEqual(first.status, 200)
        blocked = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s", "limit": 1})
        )
        self.assertEqual(blocked.status, 429)
        self.clock[0] += 1.0
        recovered = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s", "limit": 1})
        )
        self.assertEqual(recovered.status, 200)

    def test_idempotent_replay_bypasses_the_limiter(self) -> None:
        gateway = self.make_gateway(capacity=1, refill=1.0)
        gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s", "limit": 10})
        )
        self.clock[0] += 1.0
        payload = {"ship": "s", "demand": 4}
        headers = {"Idempotency-Key": "reserve-1"}
        first = gateway.dispatch(
            make_request("POST", "/quota/reserve", payload, headers=headers)
        )
        self.assertEqual(first.status, 200)
        self.assertTrue(body_of(first)["reserved"])

        replay = gateway.dispatch(
            make_request("POST", "/quota/reserve", payload, headers=headers)
        )
        self.assertEqual(replay.status, 200)
        self.assertEqual(replay.headers["Idempotency-Replayed"], "true")
        self.assertEqual(replay.payload, first.payload)

        # The handler did not run again: demand was reserved only once.
        quota = body_of(gateway.dispatch(make_request("GET", "/quota")))
        self.assertEqual(quota["quotas"]["s"]["used"], 4.0)

        # And the replay consumed no token, so a fresh write still fits.
        self.clock[0] += 1.0
        other = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "s2", "limit": 1})
        )
        self.assertEqual(other.status, 200)

    def test_idempotency_key_reuse_with_different_body_conflicts(self) -> None:
        gateway = self.make_gateway()
        headers = {"Idempotency-Key": "same-key"}
        first = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "a", "limit": 1}, headers=headers)
        )
        self.assertEqual(first.status, 200)
        conflict = gateway.dispatch(
            make_request("POST", "/quota", {"ship": "b", "limit": 1}, headers=headers)
        )
        self.assertEqual(conflict.status, 409)

    def test_duplicate_meter_reading_is_not_blocked(self) -> None:
        self.runtime.binder.bind(Binding(berth="A1", ship="vessel-1"))
        gateway = self.make_gateway(capacity=1, refill=0.1)
        reading = {"berth": "A1", "timestamp": "2026-10-04T00:00:00", "value": 12.5}
        first = gateway.dispatch(make_request("POST", "/meter", reading))
        self.assertEqual(first.status, 200)
        self.assertTrue(body_of(first)["recorded"])

        # Bucket is empty now, but the idempotent resend must still pass.
        duplicate = gateway.dispatch(make_request("POST", "/meter", reading))
        self.assertEqual(duplicate.status, 200)
        self.assertTrue(body_of(duplicate)["duplicate"])

        # A genuinely new reading is the one that gets throttled.
        fresh = gateway.dispatch(
            make_request(
                "POST",
                "/meter",
                {"berth": "A1", "timestamp": "2026-10-04T01:00:00", "value": 13.0},
            )
        )
        self.assertEqual(fresh.status, 429)


class ReportingTests(GatewayCase):
    def test_usage_report_lists_remaining_legacy_clients(self) -> None:
        gateway = self.make_gateway()
        gateway.dispatch(
            make_request("POST", "/quota", {"ship": "old", "limit": 1}, client="10.0.0.9")
        )
        gateway.dispatch(
            make_request("POST", "/quota", {"ship": "old", "limit": 1}, client="10.0.0.9")
        )
        gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship_id": "new", "limit": 1},
                headers={"X-API-Version": "v2"},
                client="10.0.0.10",
            )
        )
        report = body_of(gateway.dispatch(make_request("GET", "/version/usage")))
        legacy = report["legacy"]
        self.assertEqual(legacy["client_count"], 1)
        self.assertEqual(legacy["total_requests"], 2)
        entry = legacy["clients"]["10.0.0.9"]
        self.assertEqual(entry["count"], 2)
        self.assertEqual(entry["paths"], {"/quota": "v1"})
        self.assertIn("10.0.0.10", report["clients"])

    def test_named_client_header_identifies_caller(self) -> None:
        gateway = self.make_gateway()
        gateway.dispatch(
            make_request(
                "POST",
                "/quota",
                {"ship": "old", "limit": 1},
                headers={"X-Client-Id": "scada-north"},
                client="10.0.0.9",
            )
        )
        report = body_of(gateway.dispatch(make_request("GET", "/version/usage")))
        self.assertIn("scada-north", report["legacy"]["clients"])

    def test_policy_report_shows_windows_per_path(self) -> None:
        gateway = self.make_gateway()
        report = body_of(gateway.dispatch(make_request("GET", "/version/policy")))
        self.assertEqual(report["today"], TODAY.isoformat())
        by_path = {entry["path"]: entry for entry in report["windows"]}
        self.assertIn("/connect", by_path)
        connect = by_path["/connect"]
        self.assertEqual(connect["legacy"], "v1")
        self.assertEqual(connect["current"], "v2")
        self.assertTrue(connect["legacy_active"])
        self.assertEqual(
            connect["fields"]["legacy_to_canonical"],
            {"ship": "ship_id", "load": "max_load"},
        )


if __name__ == "__main__":
    unittest.main()
