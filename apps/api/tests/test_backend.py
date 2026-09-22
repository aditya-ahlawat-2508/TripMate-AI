import pytest

import backend


def test_get_database_url_local_no_sslmode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/travel_db")
    assert "sslmode" not in backend.get_database_url()


def test_get_database_url_remote_adds_sslmode(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@db.render.com:5432/travel_db")
    assert backend.get_database_url().endswith("?sslmode=require")


def test_get_database_url_remote_respects_existing_sslmode(monkeypatch):
    url = "postgresql://user:pass@db.render.com:5432/travel_db?sslmode=disable"
    monkeypatch.setenv("DATABASE_URL", url)
    assert backend.get_database_url() == url


def test_get_database_url_missing_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValueError):
        backend.get_database_url()


def test_describe_airport_known():
    assert "NRT" in backend.describe_airport("NRT")
    assert "Tokyo" in backend.describe_airport("NRT")


def test_describe_airport_none():
    assert backend.describe_airport(None) == "could not be determined from the request"


def test_describe_airport_unknown_code_falls_back_to_code():
    assert backend.describe_airport("ZZZ") == "ZZZ"
