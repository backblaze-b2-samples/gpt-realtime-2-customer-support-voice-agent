"""CrmAdapter Protocol + MockCrmAdapter impl.

v1 ships the mock only. Real Zendesk / Intercom / Salesforce impls plug
in by implementing the Protocol in a new module in this package and
switching at config time. The service layer (`app/service/tool_executor.py`)
talks only to this Protocol — it MUST NOT import any vendor SDK directly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.types import CrmAccount, Order, OrderItem, Ticket


class CrmAdapter(Protocol):
    """Helpdesk operations the agent can invoke at runtime.

    Implementations live in `app/repo/`; the service layer never imports
    a concrete adapter, only this Protocol via dependency injection.
    """

    def account_lookup(self, email: str) -> CrmAccount | None: ...

    def order_status(self, order_id: str) -> Order | None: ...

    def create_ticket(self, account_id: str, subject: str, body: str) -> Ticket: ...

    def escalate(self, reason: str, account_id: str | None = None) -> dict: ...


# --- Mock impl with in-memory fixtures ---


def _seed_accounts() -> dict[str, CrmAccount]:
    rows = [
        CrmAccount(
            id="acc_001",
            name="Ada Lovelace",
            email="ada@example.com",
            tier="enterprise",
            contact_phone="+1-555-0100",
        ),
        CrmAccount(
            id="acc_002",
            name="Grace Hopper",
            email="grace@example.com",
            tier="pro",
            contact_phone="+1-555-0101",
        ),
        CrmAccount(
            id="acc_003",
            name="Alan Turing",
            email="alan@example.com",
            tier="free",
        ),
    ]
    return {a.email: a for a in rows}


def _seed_orders() -> dict[str, Order]:
    now = datetime.now(UTC)
    rows = [
        Order(
            id="ord_1001",
            account_id="acc_001",
            status="shipped",
            placed_at=now - timedelta(days=3),
            eta=now + timedelta(days=1),
            items=[OrderItem(sku="SKU-A", name="Widget", qty=2)],
        ),
        Order(
            id="ord_1002",
            account_id="acc_002",
            status="pending",
            placed_at=now - timedelta(hours=6),
            items=[OrderItem(sku="SKU-B", name="Gadget", qty=1)],
        ),
        Order(
            id="ord_1003",
            account_id="acc_001",
            status="delivered",
            placed_at=now - timedelta(days=10),
            items=[OrderItem(sku="SKU-C", name="Gizmo", qty=5)],
        ),
    ]
    return {o.id: o for o in rows}


def _normalize_order_id(raw: str) -> str:
    """Lowercase and strip everything except alphanumerics.

    Voice callers (and the model relaying them) phrase order numbers
    inconsistently — "ORD-1001", "ord_1001", "order 1001", "#1001". We
    canonicalize to a comparable token so the demo never dead-ends on
    formatting. `ord_1001` and `ORD 1001` both become `ord1001`.
    """
    return "".join(ch for ch in raw.lower() if ch.isalnum())


def _order_digits(raw: str) -> str:
    """Just the digits of an order reference, e.g. 'order 1001' -> '1001'."""
    return "".join(ch for ch in raw if ch.isdigit())


class MockCrmAdapter:
    """In-memory CrmAdapter with deterministic fixtures.

    A fresh instance per app boot — the mock state does NOT survive a
    process restart, by design. Tickets created during a call are
    persisted to the call bundle (`tools.jsonl`) so the artifact survives.
    """

    def __init__(self) -> None:
        self._accounts_by_email = _seed_accounts()
        self._accounts_by_id = {a.id: a for a in self._accounts_by_email.values()}
        self._orders = _seed_orders()
        # Lookup indexes tolerant of how a caller phrases an order number.
        self._orders_by_norm = {
            _normalize_order_id(o.id): o for o in self._orders.values()
        }
        # Digit-only index, kept only for suffixes that are unambiguous
        # across the fixture set (so "1001" resolves but a shared suffix
        # would not silently pick the wrong order).
        digit_groups: dict[str, list[Order]] = {}
        for o in self._orders.values():
            digit_groups.setdefault(_order_digits(o.id), []).append(o)
        self._orders_by_digits = {
            d: orders[0] for d, orders in digit_groups.items() if len(orders) == 1
        }
        self._tickets: dict[str, Ticket] = {}

    def account_lookup(self, email: str) -> CrmAccount | None:
        return self._accounts_by_email.get(email.lower().strip())

    def order_status(self, order_id: str) -> Order | None:
        # 1) exact key (back-compat), 2) normalized token, 3) unambiguous digits.
        hit = self._orders.get(order_id.strip())
        if hit is not None:
            return hit
        hit = self._orders_by_norm.get(_normalize_order_id(order_id))
        if hit is not None:
            return hit
        return self._orders_by_digits.get(_order_digits(order_id))

    def create_ticket(self, account_id: str, subject: str, body: str) -> Ticket:
        if account_id not in self._accounts_by_id:
            raise ValueError(f"unknown account_id: {account_id}")
        ticket = Ticket(
            id=f"tkt_{uuid4().hex[:8]}",
            account_id=account_id,
            subject=subject,
            body=body,
            status="open",
            created_at=datetime.now(UTC),
        )
        self._tickets[ticket.id] = ticket
        return ticket

    def escalate(self, reason: str, account_id: str | None = None) -> dict:
        return {
            "escalation_id": f"esc_{uuid4().hex[:8]}",
            "accepted": True,
            "reason": reason,
            "account_id": account_id,
        }


# Default adapter used by the service layer. Tests can monkeypatch this
# attribute to inject a different implementation without touching the
# service code.
default_adapter: CrmAdapter = MockCrmAdapter()
