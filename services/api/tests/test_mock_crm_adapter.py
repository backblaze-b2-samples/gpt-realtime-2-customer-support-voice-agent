"""Unit tests for the MockCrmAdapter fixtures."""

from app.repo.helpdesk_adapter import MockCrmAdapter


def test_account_lookup_hit():
    adapter = MockCrmAdapter()
    acc = adapter.account_lookup("ada@example.com")
    assert acc is not None
    assert acc.id == "acc_001"
    assert acc.tier == "enterprise"


def test_account_lookup_miss():
    adapter = MockCrmAdapter()
    assert adapter.account_lookup("nobody@example.com") is None


def test_order_status_hit():
    adapter = MockCrmAdapter()
    order = adapter.order_status("ord_1001")
    assert order is not None
    assert order.account_id == "acc_001"
    assert order.status == "shipped"


def test_order_status_miss():
    adapter = MockCrmAdapter()
    assert adapter.order_status("ord_9999") is None


def test_order_status_tolerates_caller_phrasing():
    """Voice callers phrase order numbers inconsistently; all of these
    should resolve to the same fixture so the demo never dead-ends."""
    adapter = MockCrmAdapter()
    for phrasing in ["ord_1001", "ORD-1001", "order 1001", "1001", "#1001", " ord 1001 "]:
        order = adapter.order_status(phrasing)
        assert order is not None, f"{phrasing!r} should resolve"
        assert order.id == "ord_1001", f"{phrasing!r} resolved to {order.id}"


def test_order_status_unknown_digits_still_miss():
    adapter = MockCrmAdapter()
    assert adapter.order_status("order 9999") is None


def test_create_ticket_persists_for_session():
    adapter = MockCrmAdapter()
    ticket = adapter.create_ticket("acc_001", "Billing question", "Refund please")
    assert ticket.account_id == "acc_001"
    assert ticket.status == "open"
    # The mock keeps tickets in-process so multiple calls in one call_id
    # can reference the same ticket id (the bundle is the durable artifact).
    assert ticket.id.startswith("tkt_")


def test_create_ticket_unknown_account_raises():
    adapter = MockCrmAdapter()
    try:
        adapter.create_ticket("acc_missing", "x", "y")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_escalate_returns_id():
    adapter = MockCrmAdapter()
    result = adapter.escalate("very angry caller", "acc_001")
    assert result["accepted"] is True
    assert result["escalation_id"].startswith("esc_")
