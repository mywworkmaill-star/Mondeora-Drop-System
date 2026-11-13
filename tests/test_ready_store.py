"""Persistent ready-listing buffer tests; SQLite files live only in tmp_path."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import multiprocessing
import sqlite3
import threading
import time

import pytest


NOW = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
PRODUCT = "1005001234567890"


def make_store(tmp_path):
    from src.listing_quality.ready_store import ReadyStore

    return ReadyStore(tmp_path / "ready.sqlite3")


def artifact(title="Hundeleine"):
    return {"st": {"title": title, "plan": [{"sku": "123456789"}]}}


def test_put_persists_complete_record_with_canonical_hash(tmp_path):
    store = make_store(tmp_path)
    payload = artifact()
    record = store.put(PRODUCT, payload, now=NOW)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    assert store.path == tmp_path / "ready.sqlite3"
    assert record == {
        "product_id": PRODUCT,
        "status": "ready",
        "artifact": payload,
        "artifact_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "prepared_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(days=1)).isoformat(),
        "updated_at": NOW.isoformat(),
        "detail": None,
        "blockers": [],
    }
    assert type(store)(store.path).ready(now=NOW) == [record]


def test_put_replaces_same_product_not_each_variant(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact("Alt"), now=NOW)
    payload = {"st": {"plan": [{"sku": "123456"}, {"sku": "234567"}]}}
    replacement = store.put(PRODUCT, payload, now=NOW + timedelta(seconds=1))

    assert store.ready(now=NOW + timedelta(seconds=2)) == [replacement]
    assert replacement["artifact"] == payload
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM ready_listings").fetchone()[0] == 1


@pytest.mark.parametrize("product_id", ["12345", "AUTO-123456", "١٢٣٤٥٦", "１２３４５６", " 123456", "123456\n", "123456x", True, 123456.0, None, -123456])
def test_put_rejects_non_ascii_or_non_numeric_product_identity(tmp_path, product_id):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="product_id"):
        store.put(product_id, artifact(), now=NOW)


def test_integer_identity_matches_identical_ascii_string(tmp_path):
    store = make_store(tmp_path)
    store.put(123456, artifact("Alt"), now=NOW)
    updated = store.put("123456", artifact("Neu"), now=NOW)
    assert updated["product_id"] == "123456"
    assert store.ready(now=NOW) == [updated]


@pytest.mark.parametrize("payload", [[], None, False, "{}", {1: "bad key"}, {"tuple": (1, 2)}, {"nan": float("nan")}, {"inf": float("inf")}, {"value": object()}])
def test_put_requires_dictionary_containing_only_real_json(tmp_path, payload):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="artifact|JSON"):
        store.put(PRODUCT, payload, now=NOW)
    assert store.ready(now=NOW) == []


def test_artifact_hash_is_independent_of_dictionary_key_order(tmp_path):
    store = make_store(tmp_path)
    first = store.put(PRODUCT, {"b": {"z": 1, "a": "ö"}, "a": [1, None, True]}, now=NOW)
    second = store.put(PRODUCT, {"a": [1, None, True], "b": {"a": "ö", "z": 1}}, now=NOW)
    assert first["artifact_hash"] == second["artifact_hash"]


def test_blocked_content_never_counts_as_ready_even_with_truthy_artifact(tmp_path):
    store = make_store(tmp_path)
    blocked = store.put(PRODUCT, {"st": {"ready": True, "res": "large private raw"}}, blockers=["freight_unverified"], now=NOW)
    assert blocked["status"] == "blocked"
    assert store.ready(now=NOW) == []
    report = store.summary(target=10, now=NOW)
    assert {key: report[key] for key in ("ready_count", "shortfall", "blocked_count", "expired_count", "publishing_count", "published_count", "content_prepared_count")} == {
        "ready_count": 0, "shortfall": 10, "blocked_count": 1, "expired_count": 0,
        "publishing_count": 0, "published_count": 0, "content_prepared_count": 1,
    }
    assert report["blocked_reasons"] == {"freight_unverified": 1}
    assert report["items"] == [{key: blocked[key] for key in (
        "product_id", "status", "expires_at", "prepared_at", "updated_at", "blockers", "detail"
    )}]
    assert "large private raw" not in json.dumps(report)


@pytest.mark.parametrize("blockers", [None, False, "blocked", {}, [False], [1], [""], ["   "]])
def test_put_rejects_malformed_blockers_instead_of_marking_ready(tmp_path, blockers):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="blockers"):
        store.put(PRODUCT, artifact(), blockers=blockers, now=NOW)
    assert store.ready(now=NOW) == []


def test_expiry_boundary_excludes_ready_and_summary_counts_actual_unexpired_products(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), ttl_seconds=60, now=NOW)
    second = store.put("123456", {"st": {"plan": [{"sku": "123456"}, {"sku": "234567"}]}}, ttl_seconds=120, now=NOW)
    boundary = NOW + timedelta(seconds=60)
    assert store.ready(now=boundary) == [second]
    report = store.summary(target=10, now=boundary)
    assert report["ready_count"] == 1
    assert report["expired_count"] == 1
    assert report["shortfall"] == 9
    assert {item["product_id"]: item["status"] for item in report["items"]} == {
        PRODUCT: "expired", "123456": "ready"
    }


@pytest.mark.parametrize("method", ["put", "ready", "summary"])
def test_now_must_be_timezone_aware(tmp_path, method):
    store = make_store(tmp_path)
    kwargs = {"now": NOW.replace(tzinfo=None)}
    with pytest.raises(ValueError, match="aware"):
        getattr(store, method)(PRODUCT, artifact(), **kwargs) if method == "put" else getattr(store, method)(**kwargs)


def test_timestamps_are_normalized_before_timezone_comparison(tmp_path):
    store = make_store(tmp_path)
    offset_now = NOW.astimezone(timezone(timedelta(hours=5)))
    stored = store.put(PRODUCT, artifact(), ttl_seconds=60, now=offset_now)
    assert stored["prepared_at"] == NOW.isoformat()
    assert store.ready(now=NOW) == [stored]
    assert store.ready(now=NOW + timedelta(seconds=60)) == []


@pytest.mark.parametrize("status", ["published", "blocked", "stale", "needs_reconciliation", "publishing"])
def test_mark_persists_status_detail_and_lookup_for_reconciliation(tmp_path, status):
    store = make_store(tmp_path)
    prepared = store.put(PRODUCT, artifact(), now=NOW)
    marked_at = NOW + timedelta(seconds=30)
    detail = {"reason": "local result", "offer_ids": ["offer-1"]}
    changed = store.mark(PRODUCT, status, detail=detail, now=marked_at)
    expected = {**prepared, "status": status, "detail": detail, "updated_at": marked_at.isoformat()}
    assert changed == expected
    assert type(store)(store.path).get(PRODUCT) == expected
    assert store.ready(now=marked_at) == []
    assert store.summary(now=marked_at)["items"][0]["detail"] == detail


def test_get_missing_product_returns_none(tmp_path):
    assert make_store(tmp_path).get(PRODUCT) is None


@pytest.mark.parametrize("status", ["ready", "expired", "retry", "", None])
def test_mark_cannot_bypass_preparation_or_invent_status(tmp_path, status):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), now=NOW)
    with pytest.raises(ValueError, match="status"):
        store.mark(PRODUCT, status)


def test_mark_missing_product_raises_without_creating_row(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(KeyError):
        store.mark(PRODUCT, "published")
    assert store.get(PRODUCT) is None


def test_claim_atomically_removes_only_unexpired_ready_products(tmp_path):
    store = make_store(tmp_path)
    first = store.put(PRODUCT, artifact(), now=NOW)
    store.put("123456", artifact(), blockers=["not_verified"], now=NOW)
    store.put("234567", artifact(), ttl_seconds=1, now=NOW)
    claimed_at = NOW + timedelta(seconds=2)
    claimed = store.claim(now=claimed_at)
    expected = {**first, "status": "publishing", "updated_at": claimed_at.isoformat()}
    assert claimed == [expected]
    assert type(store)(store.path).get(PRODUCT) == expected
    assert store.claim(now=claimed_at) == []
    assert store.summary(now=claimed_at)["publishing_count"] == 1


@pytest.mark.parametrize("limit", [0, -1, 11, True, 1.0, "2", None])
def test_claim_limit_must_be_integer_from_one_through_ten(tmp_path, limit):
    store = make_store(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        store.claim(limit=limit, now=NOW)


def _claim_worker(path, start, output):
    from src.listing_quality.ready_store import ReadyStore

    store = ReadyStore(path)
    if not start.wait(20):
        raise TimeoutError("claim start signal not received")
    output.put([row["product_id"] for row in store.claim(limit=10, now=NOW)])


def test_simultaneous_processes_cannot_double_claim(tmp_path):
    store = make_store(tmp_path)
    expected = {str(100000 + index) for index in range(23)}
    for product_id in expected:
        store.put(product_id, artifact(), now=NOW)
    context = multiprocessing.get_context("spawn")
    start = context.Event()
    output = context.Queue()
    processes = [context.Process(target=_claim_worker, args=(str(store.path), start, output)) for _ in range(4)]
    try:
        for process in processes:
            process.start()
        start.set()
        batches = [output.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=30)
            assert process.exitcode == 0
        product_ids = [product_id for batch in batches for product_id in batch]
        assert set(product_ids) == expected
        assert len(product_ids) == len(expected)
        assert all(len(batch) <= 10 for batch in batches)
        assert store.summary(now=NOW)["publishing_count"] == len(expected)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
        output.close()
        output.join_thread()


@pytest.mark.parametrize("status", ["publishing", "published", "needs_reconciliation", "future_unknown_state"])
def test_put_cannot_overwrite_side_effect_or_unknown_state_even_after_expiry(tmp_path, status):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact("Original"), ttl_seconds=1, now=NOW)
    if status == "future_unknown_state":
        with sqlite3.connect(store.path) as db:
            db.execute("UPDATE ready_listings SET status = ? WHERE product_id = ?", (status, PRODUCT))
    else:
        store.mark(PRODUCT, status, detail={"result": "do not repeat"}, now=NOW)
    original = store.get(PRODUCT)
    later = NOW + timedelta(days=2)
    assert store.put(PRODUCT, artifact("Replacement"), now=later) == original
    assert store.get(PRODUCT) == original
    assert store.ready(now=later) == []
    assert store.claim(now=later) == []


@pytest.mark.parametrize("outcome", ["blocked", "stale"])
def test_claim_history_permanently_prevents_repreparation_after_side_effect(tmp_path, outcome):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact("Original"), now=NOW)
    store.claim(now=NOW)
    original = store.mark(PRODUCT, outcome, detail={"reason": "possibly attempted"}, now=NOW)
    assert store.put(PRODUCT, artifact("Replacement"), now=NOW) == original
    assert store.claim(now=NOW) == []


def test_blocked_before_any_side_effect_can_be_prepared_again(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), blockers=["missing_freight"], now=NOW)
    updated = store.put(PRODUCT, artifact(), blockers=[], now=NOW)
    assert updated["status"] == "ready"
    assert store.claim(now=NOW)[0]["product_id"] == PRODUCT


def test_published_since_counts_unique_products_inclusive_of_aware_boundary(tmp_path):
    store = make_store(tmp_path)
    for product_id, delta in (("100000", -1), ("100001", 0), ("100002", 1)):
        store.put(product_id, artifact(), now=NOW - timedelta(days=1))
        store.mark(product_id, "published", now=NOW + timedelta(seconds=delta))
    store.mark("100002", "published", detail={"checked": True}, now=NOW + timedelta(seconds=2))
    store.put("100003", artifact(), now=NOW)
    store.mark("100003", "publishing", now=NOW)
    boundary = NOW.astimezone(timezone(timedelta(hours=-4)))
    assert store.published_since(boundary) == 2
    assert type(store)(store.path).published_since(NOW + timedelta(days=1)) == 0


def test_published_since_rejects_naive_boundary(tmp_path):
    with pytest.raises(ValueError, match="aware"):
        make_store(tmp_path).published_since(NOW.replace(tzinfo=None))


def test_published_since_invalid_published_timestamp_cannot_silently_undercount_cap(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), now=NOW)
    store.mark(PRODUCT, "published", now=NOW)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE ready_listings SET updated_at = 'broken' WHERE product_id = ?", (PRODUCT,))
    with pytest.raises(ValueError):
        store.published_since(NOW)


@pytest.mark.parametrize("column, value", [
    ("artifact", '{"changed":true}'),
    ("artifact", '{broken'),
    ("artifact", '{"value":NaN}'),
    ("artifact_hash", "0" * 64),
    ("expires_at", "not-a-date"),
    ("expires_at", "2099-01-01T12:00:00"),
    ("prepared_at", "broken"),
    ("updated_at", "broken"),
    ("blockers", "["),
    ("blockers", "false"),
    ("blockers", "[false]"),
    ("blockers", '["gate_failed"]'),
    ("detail", "not-json"),
    ("side_effect_started", 1),
    ("side_effect_started", "unknown"),
])
@pytest.mark.parametrize("method", ["ready", "claim"])
def test_corrupted_row_fails_closed_without_starving_valid_row(tmp_path, column, value, method):
    store = make_store(tmp_path)
    store.put("100000", artifact("Corrupt"), now=NOW)
    store.put("200000", artifact("Healthy"), now=NOW)
    with sqlite3.connect(store.path) as db:
        db.execute(f"UPDATE ready_listings SET {column} = ? WHERE product_id = ?", (value, "100000"))
    report = store.summary(now=NOW)
    assert report["ready_count"] == 1
    assert report["shortfall"] == 9
    corrupt = store.get("100000")
    assert corrupt is not None
    assert corrupt["status"] != "ready"
    assert corrupt["blockers"]
    assert [row["product_id"] for row in getattr(store, method)(limit=1, now=NOW)] == ["200000"]


def test_invalid_identity_in_database_cannot_become_ready(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), now=NOW)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE ready_listings SET product_id = '١٢٣٤٥٦'")
    assert store.ready(now=NOW) == []
    assert store.claim(now=NOW) == []
    assert store.summary(now=NOW)["ready_count"] == 0


def test_duplicate_json_keys_fail_closed_even_when_decoded_hash_matches(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, {"st": {"title": "Final"}}, now=NOW)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE ready_listings SET artifact = ? WHERE product_id = ?", (
            '{"st":{"title":"Tampered","title":"Final"}}', PRODUCT
        ))
    assert store.ready(now=NOW) == []
    assert store.claim(now=NOW) == []


def test_unknown_state_is_exposed_as_reconciliation_not_silently_lost(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), now=NOW)
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE ready_listings SET status = 'unknown_after_restart'")
    report = store.summary(now=NOW)
    assert report["needs_reconciliation_count"] == 1
    assert report["items"][0]["status"] == "needs_reconciliation"
    assert "unknown_status" in report["items"][0]["blockers"]
    assert store.put(PRODUCT, artifact("New"), now=NOW) == store.get(PRODUCT)
    assert store.claim(now=NOW) == []


def test_future_preparation_timestamp_is_not_ready_yet(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), now=NOW + timedelta(hours=1))
    assert store.ready(now=NOW) == []
    assert store.claim(now=NOW) == []
    assert store.summary(now=NOW)["ready_count"] == 0


def test_claim_without_explicit_now_rechecks_expiry_after_waiting_for_write_lock(tmp_path):
    store = make_store(tmp_path)
    store.put(PRODUCT, artifact(), ttl_seconds=1)
    started = threading.Event()

    def wait_and_claim():
        started.set()
        return store.claim()

    with sqlite3.connect(store.path) as writer, ThreadPoolExecutor(max_workers=1) as pool:
        writer.execute("BEGIN IMMEDIATE")
        result = pool.submit(wait_and_claim)
        assert started.wait(5)
        time.sleep(1.5)
        writer.commit()
        assert result.result(timeout=10) == []
    assert store.summary()["expired_count"] == 1
