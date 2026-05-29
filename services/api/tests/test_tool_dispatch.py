"""Unit tests for tool dispatch."""

from app.service.tool_executor import ToolDispatchError, dispatch
from app.types import ToolCallRequest


def _req(tool: str, args: dict) -> ToolCallRequest:
    return ToolCallRequest(
        call_id="01HZ000000000000000000000Z",
        tool_call_id="call_test",
        tool_name=tool,
        args=args,
    )


def test_account_lookup_ok():
    response, event = dispatch(_req("account_lookup", {"email": "ada@example.com"}))
    assert response.ok is True
    assert response.result is not None
    assert event.status == "ok"
    assert event.tool == "account_lookup"


def test_account_lookup_miss_still_ok():
    """A miss is `ok=true result=None` — the model needs to know we asked."""
    response, _ = dispatch(_req("account_lookup", {"email": "nobody@example.com"}))
    assert response.ok is True
    assert response.result is None


def test_account_lookup_bad_args():
    try:
        dispatch(_req("account_lookup", {}))
        raise AssertionError("expected ToolDispatchError")
    except ToolDispatchError as exc:
        assert exc.status_code == 400


def test_unknown_tool_raises():
    """Defense-in-depth: tool_name is a Literal so the Pydantic boundary
    rejects unknown tools before dispatch runs. We bypass that validation
    with model_construct to confirm dispatch still guards its own branch."""
    bad = ToolCallRequest.model_construct(
        call_id="01HZ000000000000000000000Z",
        tool_call_id="call_test",
        tool_name="not_a_tool",  # type: ignore[arg-type]
        args={},
    )
    try:
        dispatch(bad)
        raise AssertionError("expected ToolDispatchError")
    except ToolDispatchError:
        pass


def test_create_ticket_unknown_account_returns_error_event():
    response, event = dispatch(
        _req(
            "create_ticket",
            {"account_id": "acc_missing", "subject": "x", "body": "y"},
        )
    )
    # Adapter raises -> we surface as ok=false (NOT a 5xx) so the model can apologize.
    assert response.ok is False
    assert event.status == "error"
    assert response.error
