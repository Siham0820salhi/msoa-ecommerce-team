import pytest

from app.services import status as st


@pytest.mark.parametrize(
    "current,new",
    [
        ("PENDING_PAYMENT", "PAID"),
        ("PENDING_PAYMENT", "CANCELLED"),
        ("PAID", "SHIPPED"),
        ("PAID", "CANCELLED"),
        ("SHIPPED", "DELIVERED"),
    ],
)
def test_allowed_transitions(current, new):
    assert st.can_transition(current, new)


@pytest.mark.parametrize(
    "current,new",
    [
        ("PENDING_PAYMENT", "SHIPPED"),
        ("PENDING_PAYMENT", "DELIVERED"),
        ("PAID", "PENDING_PAYMENT"),
        ("PAID", "DELIVERED"),
        ("SHIPPED", "CANCELLED"),
        ("SHIPPED", "PAID"),
        ("DELIVERED", "CANCELLED"),
        ("CANCELLED", "PAID"),
        ("PAID", "PAID"),
    ],
)
def test_forbidden_transitions(current, new):
    assert not st.can_transition(current, new)


def test_shipped_order_is_not_cancellable():
    assert "SHIPPED" not in st.CANCELLABLE
    assert "DELIVERED" not in st.CANCELLABLE
