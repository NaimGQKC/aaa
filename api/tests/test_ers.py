"""Engaged Review System: M2 source gate, M7 calibrated trust, vigilance."""

import pytest


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        c.post("/api/auth/register",
               json={"email": "ana@fund.example", "name": "Ana", "password": "s3cret-pass"})
        yield c


def _deal_with_findings(client):
    from synthetic_docs import ALL_DOCS, build_pdf

    deal_id = client.post("/api/deals", json={"name": "d", "jurisdiction": ["ES", "FR"]}).json()["id"]
    for sdoc in ALL_DOCS:
        client.post(
            f"/api/deals/{deal_id}/upload",
            files={"file": (sdoc.filename, build_pdf(sdoc), "application/pdf")},
        )
    client.post(f"/api/deals/{deal_id}/process")
    return deal_id


def test_m2_high_severity_gate(client):
    deal_id = _deal_with_findings(client)
    findings = client.get(f"/api/deals/{deal_id}/findings").json()
    high = [f for f in findings if f["severity"] == "high"]
    assert high, "demo deal should produce high-severity findings"
    f = high[0]
    assert f["review_gated"] is True and f["source_viewed"] is False

    # cannot disposition before viewing source
    r = client.post(f"/api/findings/{f['id']}/review",
                    json={"status": "accepted", "reason": "looks right"})
    assert r.status_code == 409

    # open source -> gate clears -> disposition works
    client.post(f"/api/findings/{f['id']}/viewed")
    r2 = client.post(f"/api/findings/{f['id']}/review",
                     json={"status": "accepted", "reason": "confirmed on nota simple p.2"})
    assert r2.status_code == 200

    # the source-view is on the audit chain
    audit = client.get(f"/api/deals/{deal_id}/audit").json()
    assert any(a["event_type"] == "source_viewed" for a in audit)
    assert client.get("/api/audit/verify").json()["valid"] is True


def test_medium_and_low_not_gated(client):
    deal_id = _deal_with_findings(client)
    findings = client.get(f"/api/deals/{deal_id}/findings").json()
    non_high = [f for f in findings if f["severity"] != "high"]
    assert non_high
    f = non_high[0]
    assert f["review_gated"] is False
    r = client.post(f"/api/findings/{f['id']}/review",
                    json={"status": "accepted", "reason": "ok"})
    assert r.status_code == 200


def test_vigilance_flags_zero_override(client):
    deal_id = _deal_with_findings(client)
    findings = client.get(f"/api/deals/{deal_id}/findings").json()
    # accept everything (opening sources for high items) -> 0% override
    for f in findings:
        if f["severity"] == "high":
            client.post(f"/api/findings/{f['id']}/viewed")
        client.post(f"/api/findings/{f['id']}/review",
                    json={"status": "accepted", "reason": "accepted"})
    vig = client.get(f"/api/deals/{deal_id}/vigilance").json()
    assert vig["override_rate"] == 0.0
    assert vig["high_source_open_rate"] == 1.0
    assert any(fl["code"] == "zero_override_rate" for fl in vig["flags"])


def test_m7_reliability_from_dispositions(client):
    deal_id = _deal_with_findings(client)
    findings = client.get(f"/api/deals/{deal_id}/findings").json()
    # disposition enough title_charge findings to cross the sample floor
    tc = [f for f in findings if f["category"] == "title_charge"]
    for f in tc:
        client.post(f"/api/findings/{f['id']}/viewed")
        client.post(f"/api/findings/{f['id']}/review",
                    json={"status": "accepted", "reason": "verified"})
    refreshed = client.get(f"/api/deals/{deal_id}/findings").json()
    tc2 = [f for f in refreshed if f["category"] == "title_charge"]
    assert tc2 and tc2[0]["reliability"] is not None
    assert tc2[0]["reliability"]["verified"] >= 1


def test_certification_on_reviewed_report(client):
    deal_id = _deal_with_findings(client)
    findings = client.get(f"/api/deals/{deal_id}/findings").json()
    for f in findings:
        if f["severity"] == "high":
            client.post(f"/api/findings/{f['id']}/viewed")
        client.post(f"/api/findings/{f['id']}/review",
                    json={"status": "accepted", "reason": "reviewed"})
    for c in client.get(f"/api/deals/{deal_id}/spotchecks").json():
        client.post(f"/api/spotchecks/{c['id']}", json={"status": "match"})
    rep = client.post(f"/api/deals/{deal_id}/report").json()
    html = client.get(f"/api/reports/{rep['id']}.html").text
    assert "HUMAN-REVIEWED" in html
    assert "exercised independent professional judgment" in html
    audit = client.get(f"/api/deals/{deal_id}/audit").json()
    assert any(a["event_type"] == "certification" for a in audit)
