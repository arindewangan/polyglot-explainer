"""
pytest suite for Polyglot Explainer (Hack Apertus Track 2B, track_2b/src layout).

Runs entirely in demo mode (no LLM_API_KEY / APERTUS_API_KEY): clears key env
vars before importing the app so live mode is never triggered. No network calls.
"""
import os
import sys

import pytest

# Force demo mode before the app module is imported. The template-mandated
# LLM_* names are read FIRST, so they must be popped alongside the legacy
# APERTUS_* names.
for _var in (
    "LLM_API_KEY", "APERTUS_API_KEY",
    "LLM_BASE_URL", "APERTUS_BASE_URL",
    "LLM_NAME", "APERTUS_MODEL",
):
    os.environ.pop(_var, None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module  # noqa: E402


@pytest.fixture()
def client():
    assert app_module.DEMO_MODE, "tests must run in demo mode (no API key)"
    app_module.app.config["TESTING"] = True
    app_module._CACHE.clear()
    with app_module.app.test_client() as c:
        yield c


def test_index_returns_200_with_demo_badge(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Polyglot Explainer" in resp.data
    assert b"Demo mode" in resp.data
    # interactive UI elements are present
    for marker in (b'id="topic"', b'id="chips"', b'id="depth"', b'id="result"'):
        assert marker in resp.data


def test_languages_returns_200_and_non_empty(client):
    resp = client.get("/api/languages")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["count"] >= 12
    assert len(data["languages"]) == data["count"]
    codes = {l["code"] for l in data["languages"]}
    for expected in ("en", "hi", "ta", "bn", "kn", "te", "ml", "mr", "gu", "fr", "de", "ja", "sw"):
        assert expected in codes


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["demo"] is True


def test_explain_works_in_demo_mode(client):
    resp = client.post(
        "/api/explain",
        json={"topic": "photosynthesis", "language": "hi", "depth": "eli5"},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["demo"] is True
    assert data["model"] == "demo"
    assert data["topic"] == "photosynthesis"
    assert data["language"] == "hi"
    assert data["depth"] == "eli5"
    assert data["explanation"], "explanation must be non-empty"
    assert data["cached"] is False


def test_explain_demo_response_labeled_simulated(client):
    resp = client.post(
        "/api/explain",
        json={"topic": "photosynthesis", "language": "ta", "depth": "eli5"},
    )
    data = resp.get_json()
    assert "SIMULATED DEMO" in data["explanation"]


def test_explain_cached_flag_on_repeat(client):
    body = {"topic": "black holes", "language": "fr", "depth": "eli5"}
    first = client.post("/api/explain", json=body).get_json()
    second = client.post("/api/explain", json=body).get_json()
    assert first["cached"] is False
    assert second["cached"] is True
    assert first["explanation"] == second["explanation"]


def test_explain_empty_topic_returns_400(client):
    for body in ({}, {"topic": ""}, {"topic": "   "}, {"language": "hi"}):
        resp = client.post("/api/explain", json=body)
        assert resp.status_code == 400, f"expected 400 for body {body}"
        assert "topic" in resp.get_json()["error"].lower()


def test_explain_unknown_language_returns_400(client):
    resp = client.post(
        "/api/explain",
        json={"topic": "gravity", "language": "xx", "depth": "standard"},
    )
    assert resp.status_code == 400
    assert "language" in resp.get_json()["error"].lower()


def test_explain_unknown_depth_returns_400(client):
    resp = client.post(
        "/api/explain",
        json={"topic": "gravity", "language": "en", "depth": "quantum"},
    )
    assert resp.status_code == 400
    assert "depth" in resp.get_json()["error"].lower()


def test_demo_responses_contain_no_credential_values(client):
    # Demo-mode outputs must never carry a credential *value*. (The index page
    # legitimately names the LLM_API_KEY env var to explain demo mode —
    # only a Bearer token value would be a leak.)
    import re

    bearer_pat = re.compile(r"Bearer\s+\S+")
    for route in ("/", "/api/languages"):
        body = client.get(route).data.decode()
        assert not bearer_pat.search(body)
    data = client.post(
        "/api/explain",
        json={"topic": "photosynthesis", "language": "en", "depth": "standard"},
    ).get_json()
    blob = str(data)
    assert not bearer_pat.search(blob)
    assert "api_key" not in str(data.keys()).lower()
    assert app_module.APERTUS_API_KEY == "", "demo mode means no key is configured"


def test_live_client_never_echoes_key(client, monkeypatch):
    # Verify request construction without network: the key goes into the
    # Authorization header only, never into the URL/body, and the parsed
    # response can't contain it.
    sentinel = "sk-test-sentinel-12345"
    monkeypatch.setattr(app_module, "APERTUS_API_KEY", sentinel)
    monkeypatch.setattr(app_module, "APERTUS_BASE_URL", "https://example.invalid/v1")
    captured = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResp()

    import requests as rq

    monkeypatch.setattr(rq, "post", fake_post)
    out = app_module._live_explain("gravity", "en", "standard")
    assert out == "ok"
    assert captured["headers"]["Authorization"] == f"Bearer {sentinel}"
    assert sentinel not in captured["url"]
    assert sentinel not in str(captured["json"])
    assert sentinel not in out


def test_live_client_refuses_placeholder_base_url(client, monkeypatch):
    import requests as rq

    monkeypatch.setattr(app_module, "APERTUS_API_KEY", "sk-test")
    monkeypatch.setattr(
        app_module, "APERTUS_BASE_URL", "https://api.infomaniak.com/2/ai/<product>/openai/v1"
    )
    with pytest.raises(rq.RequestException):
        app_module._live_explain("gravity", "en", "standard")


def test_explain_all_depths_valid(client):
    for depth in ("eli5", "standard", "deep"):
        resp = client.post(
            "/api/explain",
            json={"topic": "black holes", "language": "en", "depth": depth},
        )
        assert resp.status_code == 200
        assert resp.get_json()["depth"] == depth
