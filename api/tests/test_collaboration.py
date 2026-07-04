"""GitHub-style collaboration: per-deal membership, roles, identity binding."""

import pytest


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def _register(client, email, name="User", password="s3cret-pass"):
    r = client.post("/api/auth/register",
                    json={"email": email, "name": name, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def test_deal_isolation_between_users(client):
    _register(client, "ana@fund.example", "Ana")
    deal = client.post("/api/deals", json={"name": "Ana's deal", "jurisdiction": ["ES"]}).json()

    # switch identity: Bruno registers (cookie replaced)
    _register(client, "bruno@bank.example", "Bruno")
    # Bruno sees no deals and cannot open Ana's
    assert client.get("/api/deals").json() == []
    assert client.get(f"/api/deals/{deal['id']}").status_code == 404
    assert client.get(f"/api/deals/{deal['id']}/findings").status_code == 404


def test_roles_enforced_and_membership_audited(client):
    from synthetic_docs import NOTA_SIMPLE, build_pdf

    _register(client, "viewer@counterparty.example", "Vera")
    _register(client, "ana@fund.example", "Ana")
    deal_id = client.post("/api/deals", json={"name": "d", "jurisdiction": ["ES"]}).json()["id"]
    up = client.post(
        f"/api/deals/{deal_id}/upload",
        files={"file": ("nota.pdf", build_pdf(NOTA_SIMPLE), "application/pdf")},
    )
    assert up.status_code == 200
    client.post(f"/api/deals/{deal_id}/process")

    # Ana (owner) invites Vera read-only
    inv = client.post(f"/api/deals/{deal_id}/members",
                      json={"email": "viewer@counterparty.example", "role": "viewer"})
    assert inv.status_code == 200

    # Vera logs in: can read, cannot write
    client.post("/api/auth/login",
                json={"email": "viewer@counterparty.example", "password": "s3cret-pass"})
    assert client.get(f"/api/deals/{deal_id}").status_code == 200
    findings = client.get(f"/api/deals/{deal_id}/findings")
    assert findings.status_code == 200 and findings.json()
    fid = findings.json()[0]["id"]
    # viewer cannot adjudicate, upload, or invite
    assert client.post(f"/api/findings/{fid}/review",
                       json={"status": "accepted", "reason": "ok"}).status_code == 403
    assert client.post(
        f"/api/deals/{deal_id}/upload",
        files={"file": ("x.pdf", b"%PDF-1.4 fake", "application/pdf")},
    ).status_code == 403
    assert client.post(f"/api/deals/{deal_id}/members",
                       json={"email": "ana@fund.example", "role": "viewer"}).status_code == 403

    # membership changes are on the audited record
    client.post("/api/auth/login",
                json={"email": "ana@fund.example", "password": "s3cret-pass"})
    audit = client.get(f"/api/deals/{deal_id}/audit").json()
    assert any(a["event_type"] == "access_granted" for a in audit)
    assert client.get("/api/audit/verify").json()["valid"] is True


def test_cannot_remove_last_owner(client):
    _register(client, "solo@fund.example", "Solo")
    deal = client.post("/api/deals", json={"name": "d", "jurisdiction": []}).json()
    me = client.get("/api/auth/me").json()
    r = client.delete(f"/api/deals/{deal['id']}/members/{me['id']}")
    assert r.status_code == 409
