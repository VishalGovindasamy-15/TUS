import pytest

from app.core.state_machine import InvalidTransition, apply_transition


@pytest.mark.parametrize("current,event,expected", [
    ("ISSUED", "DISPATCH", "IN_TRANSIT"),
    ("RECEIVED", "DISPATCH", "IN_TRANSIT"),
    ("RETURNED", "DISPATCH", "IN_TRANSIT"),
    ("IN_TRANSIT", "RECEIVE", "RECEIVED"),
    ("RECEIVED", "SALE", "SOLD"),
    ("SOLD", "RETURN", "RETURNED"),
    ("ISSUED", "FLAG", "FLAGGED"),
    ("SOLD", "FLAG", "FLAGGED"),
    ("FLAGGED", "UNFLAG", "ISSUED"),
])
def test_valid_transitions(current, event, expected):
    assert apply_transition(current, event) == expected


@pytest.mark.parametrize("current,event", [
    ("ISSUED", "RECEIVE"),
    ("ISSUED", "SALE"),
    ("IN_TRANSIT", "SALE"),
    ("SOLD", "SALE"),
    ("FLAGGED", "DISPATCH"),
    ("FLAGGED", "RECEIVE"),
    ("RECEIVED", "UNFLAG"),
    ("ISSUED", "BOGUS"),
])
def test_invalid_transitions(current, event):
    with pytest.raises(InvalidTransition):
        apply_transition(current, event)
