"""Real state machine (Production Reference Section 3) — build against this exactly."""
from __future__ import annotations


class InvalidTransition(Exception):
    pass


def apply_transition(current_state: str, event_type: str) -> str:
    """Return the resulting state or raise InvalidTransition."""
    if event_type == "FLAG":
        if current_state == "FLAGGED":
            raise InvalidTransition("Unit is already FLAGGED")
        return "FLAGGED"
    if current_state == "FLAGGED":
        if event_type == "UNFLAG":
            return "ISSUED"
        raise InvalidTransition("FLAGGED units are frozen until UNFLAG")

    if event_type == "DISPATCH":
        if current_state in ("ISSUED", "RECEIVED", "RETURNED"):
            return "IN_TRANSIT"
    elif event_type == "RECEIVE":
        if current_state == "IN_TRANSIT":
            return "RECEIVED"
    elif event_type == "SALE":
        if current_state == "RECEIVED":
            return "SOLD"
    elif event_type == "RETURN":
        if current_state == "SOLD":
            return "RETURNED"
    elif event_type == "UNFLAG":
        raise InvalidTransition("UNFLAG is only valid on FLAGGED units")
    else:
        raise InvalidTransition(f"Unknown event_type: {event_type}")
    raise InvalidTransition(f"Cannot apply {event_type} to state {current_state}")


VALID_EVENTS = ("DISPATCH", "RECEIVE", "SALE", "RETURN", "FLAG", "UNFLAG")
