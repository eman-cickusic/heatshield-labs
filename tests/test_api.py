import sys
from pathlib import Path

# Add project root to sys.path so we can import src.* packages
sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from src.api.main import app


def test_health_and_demo_risk():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json().get("ok") is True

    payload = {
        "schools": [
            {"name": "Riverdale Primary", "lat": 40.7128, "lon": -74.0060},
            {"name": "Coastal High", "lat": 37.7749, "lon": -122.4194},
        ],
        "date": "2024-07-01",
        "use_demo": True,
    }
    rr = c.post("/risk", json=payload)
    assert rr.status_code == 200
    body = rr.json()
    assert set(["date", "results", "units"]) <= set(body.keys())
    assert len(body["results"]) == 2
    first = body["results"][0]
    assert set(["school", "summary", "sources"]) <= set(first.keys())

    exp = c.post("/explain", json={"summary": first["summary"]})
    assert exp.status_code == 200
    assert isinstance(exp.json().get("text"), str)


def test_plan_llm_language_passthrough(monkeypatch):
    c = TestClient(app)
    calls = {}

    def fake_llm_plan(summary, language, user_prompt):
        calls["language"] = language
        calls["prompt"] = user_prompt
        calls["summary"] = summary
        return [f"{language} plan"]

    monkeypatch.setattr("src.api.main.llm_plan", fake_llm_plan)
    payload = {
        "risk_report": {"hours_by_tier": {"green": 24}, "peak_wbgt_c": 25.0},
        "mode": "llm",
        "language": "Spanish",
        "user_prompt": "Focus on hydration reminders",
    }
    resp = c.post("/plan", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["language"] == "Spanish"
    assert body["mode"] == "llm"
    assert body["actions"] == ["Spanish plan"]
    assert calls["language"] == "Spanish"
    assert calls["prompt"] == "Focus on hydration reminders"
    assert calls["summary"] == payload["risk_report"]


def test_plan_llm_fallback_to_rule(monkeypatch):
    c = TestClient(app)

    def fake_llm_plan(summary, language, user_prompt):
        return []

    def fake_plan_from_summary(summary):
        return ["Rule action"]

    monkeypatch.setattr("src.api.main.llm_plan", fake_llm_plan)
    monkeypatch.setattr("src.api.main.plan_from_summary", fake_plan_from_summary)

    resp = c.post(
        "/plan",
        json={
            "risk_report": {"hours_by_tier": {"red": 3}, "peak_wbgt_c": 33.0},
            "mode": "llm",
            "language": "English",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["actions"] == ["Rule action"]
    assert body["mode"] == "llm"
