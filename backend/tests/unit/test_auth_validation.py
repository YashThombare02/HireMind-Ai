import pytest
from pydantic import ValidationError

from app.routers.auth import RegisterRequest


def test_register_rejects_password_under_8_chars():
    with pytest.raises(ValidationError):
        RegisterRequest(name="Priya Sharma", email="priya@example.com", password="short1")


def test_register_accepts_password_exactly_8_chars():
    req = RegisterRequest(name="Priya Sharma", email="priya@example.com", password="exactly8")
    assert req.password == "exactly8"


def test_register_rejects_blank_name_after_strip():
    with pytest.raises(ValidationError):
        RegisterRequest(name="   ", email="priya@example.com", password="password123")


def test_register_strips_surrounding_whitespace_from_name():
    req = RegisterRequest(name="  Priya Sharma  ", email="priya@example.com", password="password123")
    assert req.name == "Priya Sharma"


def test_register_rejects_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(name="Priya Sharma", email="not-an-email", password="password123")
