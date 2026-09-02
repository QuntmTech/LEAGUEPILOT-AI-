"""Bounded, self-clearing failure throttle."""

from __future__ import annotations

import pytest

from app.auth_server import throttle as throttle_mod
from app.auth_server.throttle import FailureThrottle, normalize_identifier, normalize_network


def test_allows_until_the_limit_then_refuses():
    t = FailureThrottle(limit=3)
    for _ in range(3):
        assert t.allows("k") is True
        t.record_failure("k")
    assert t.allows("k") is False


def test_window_expiry_restores_access_without_operator_action(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(throttle_mod.time, "monotonic", lambda: now[0])
    t = FailureThrottle(limit=2, window_seconds=60)
    t.record_failure("k")
    t.record_failure("k")
    assert t.allows("k") is False
    now[0] += 61
    assert t.allows("k") is True, "a throttle must decay, not become a lockout"


def test_success_clears_only_the_key_it_is_given():
    t = FailureThrottle(limit=1)
    t.record_failure("a")
    t.record_failure("b")
    t.clear("a")
    assert t.allows("a") is True
    assert t.allows("b") is False


def test_storage_is_bounded_and_evicts_least_recently_used():
    t = FailureThrottle(limit=1, max_keys=10)
    for i in range(500):
        t.record_failure(f"key-{i}")
    assert len(t._failures) <= 10, "attacker-supplied keys must not grow without bound"
    # The most recent keys survive; the oldest were evicted.
    assert t.allows("key-499") is False
    assert t.allows("key-0") is True


def test_expired_entries_are_dropped_rather_than_accumulating(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(throttle_mod.time, "monotonic", lambda: now[0])
    t = FailureThrottle(limit=5, window_seconds=10)
    t.record_failure("k")
    now[0] += 11
    assert t.allows("k") is True
    assert "k" not in t._failures


@pytest.mark.parametrize("raw,expected", [
    ("Owner@Example.com", "owner@example.com"),
    ("  owner@example.com  ", "owner@example.com"),
    ("OWNER@EXAMPLE.COM", "owner@example.com"),
])
def test_identifier_normalization_collapses_variants(raw, expected):
    assert normalize_identifier(raw) == expected


def test_ipv6_is_bucketed_to_a_64_so_one_host_cannot_mint_unlimited_budgets():
    a = normalize_network("2001:db8:1:2:3:4:5:6")
    b = normalize_network("2001:db8:1:2:ffff:ffff:ffff:ffff")
    assert a == b == "2001:db8:1:2::/64"


def test_ipv4_is_counted_per_address_so_shared_nat_is_not_collectively_punished():
    assert normalize_network("203.0.113.9") == "203.0.113.9"
    assert normalize_network("203.0.113.10") != normalize_network("203.0.113.9")


@pytest.mark.parametrize("value", [None, "", "not-an-ip", "999.999.999.999"])
def test_unparseable_addresses_share_one_bucket_rather_than_bypassing_the_budget(value):
    assert normalize_network(value) == "unknown"
