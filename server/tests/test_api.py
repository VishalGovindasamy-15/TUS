"""End-to-end API flow against a file-based SQLite DB (Postgres in prod)."""
import asyncio
import os

os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret-" + "x" * 40
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:////tmp/trustus_test.db"
os.environ["REDIS_URL"] = ""
os.environ["EAGER_DETECTION"] = "true"

import pyotp  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Org, User  # noqa: E402

DB_PATH = "/tmp/trustus_test.db"
URL = os.environ["DATABASE_URL"]

MFG, DIST, ADMIN, STRANGER, TRANSPORT = (
    "+19900000001", "+19900000002", "+19900000003", "+19900000004", "+19900000005",
)

test_engine = create_async_engine(URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
STATE: dict = {}


async def _set_user(phone: str, **kw):
    async with TestSession() as s:
        u = (await s.execute(select(User).where(User.phone == phone))).scalars().first()
        for k, v in kw.items():
            setattr(u, k, v)
        await s.commit()


async def _approve_org(org_id: str):
    async with TestSession() as s:
        o = await s.get(Org, org_id)
        o.approval_status = "approved"
        await s.commit()


@pytest.fixture(scope="module")
def client():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    asyncio.run(_create_all())
    with TestClient(app) as c:
        yield c


async def _create_all():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def login(client: TestClient, phone: str) -> dict:
    r = client.post("/api/v1/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    otp = r.json()["debug_otp"]
    assert otp
    r = client.post("/api/v1/auth/otp/verify", json={"phone": phone, "otp": otp})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/health").status_code == 200
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["db"] is True


def test_org_onboarding(client):
    mfg = login(client, MFG)
    assert mfg["user"]["org_id"] is None
    STATE["mfg_token"] = mfg["access_token"]
    r = client.post("/api/v1/orgs", json={"name": "Acme", "org_type": "manufacturer"},
                    headers=auth(mfg["access_token"]))
    assert r.status_code == 200, r.text
    STATE["mfg_org"] = r.json()["id"]
    assert r.json()["approval_status"] == "pending"
    asyncio.run(_approve_org(STATE["mfg_org"]))

    admin = login(client, ADMIN)
    STATE["admin_token"] = admin["access_token"]
    asyncio.run(_set_user(ADMIN, role="platform_admin", org_id=None))


def test_product_batch_units(client):
    h = auth(STATE["mfg_token"])
    r = client.post("/api/v1/products",
                    json={"product_code": "PCM500", "name": "Para", "category": "pharma"},
                    headers=h)
    assert r.status_code == 200, r.text
    STATE["product"] = r.json()["id"]
    r = client.post("/api/v1/batches",
                    json={"product_id": STATE["product"], "batch_number": "B-001",
                          "quantity": 10, "mfg_date": "2026-01-10",
                          "expiry_date": "2027-12-31"},
                    headers=h)
    assert r.status_code == 200, r.text
    STATE["batch"] = r.json()["id"]
    r = client.post(f"/api/v1/batches/{STATE['batch']}/units", json={"count": 10}, headers=h)
    assert r.status_code == 200, r.text
    STATE["units"] = r.json()["unit_ids"]
    assert len(STATE["units"]) == 10
    # re-list (Fix Plan: must survive beyond the create response)
    r = client.get(f"/api/v1/batches/{STATE['batch']}/units", headers=h)
    assert r.status_code == 200 and len(r.json()) == 10


def test_events_and_sync_authz(client):
    mh = auth(STATE["mfg_token"])
    dist = login(client, DIST)
    STATE["dist_token"] = dist["access_token"]
    r = client.post("/api/v1/orgs", json={"name": "Dist", "org_type": "distributor_authorized"},
                    headers=auth(dist["access_token"]))
    STATE["dist_org"] = r.json()["id"]
    asyncio.run(_approve_org(STATE["dist_org"]))

    unit = STATE["units"][0]
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-dispatch-1", "target_type": "unit",
                          "target_id": unit, "event_type": "DISPATCH"},
                    headers=mh)
    assert r.status_code == 200, r.text
    assert r.json()["resulting_state"] == "IN_TRANSIT"

    # distributor has no network edge yet -> synchronous 403 (Fix Plan 2.1)
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-receive-1", "target_type": "unit",
                          "target_id": unit, "event_type": "RECEIVE"},
                    headers=auth(STATE["dist_token"]))
    assert r.status_code == 403 and r.json()["detail"]["code"] == "UNAUTHORIZED_ROUTE"

    # invite + accept -> edge -> receive works
    r = client.post("/api/v1/network/invites", json={}, headers=mh)
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    r = client.post(f"/api/v1/network/invites/{code}/accept", headers=auth(STATE["dist_token"]))
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-receive-1", "target_type": "unit",
                          "target_id": unit, "event_type": "RECEIVE"},
                    headers=auth(STATE["dist_token"]))
    assert r.status_code == 200, r.text
    assert r.json()["resulting_state"] == "RECEIVED"

    # idempotent retry of the dispatch returns the identical event
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-dispatch-1", "target_type": "unit",
                          "target_id": unit, "event_type": "DISPATCH"},
                    headers=mh)
    assert r.status_code == 200 and r.json()["client_event_id"] == "evt-dispatch-1"


def test_verify_states(client):
    mh = auth(STATE["mfg_token"])
    # untouched issued unit -> not_yet_in_circulation (Fix Plan 2.2)
    r = client.get(f"/api/v1/verify/{STATE['units'][1]}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "not_yet_in_circulation"
    # unit with custody events -> genuine, with last events + disclosures keys
    r = client.get(f"/api/v1/verify/{STATE['units'][0]}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "genuine"
    assert len(body["last_events"]) >= 2
    assert "disclosures" in body
    # unknown id -> generic 404
    r = client.get("/api/v1/verify/TU-NOPE-NOPE")
    assert r.status_code == 404
    # admin FLAG -> flagged
    ah = auth(STATE["admin_token"])
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-flag-1", "target_type": "unit",
                          "target_id": STATE["units"][2], "event_type": "FLAG"},
                    headers=ah)
    assert r.status_code == 200, r.text
    r = client.get(f"/api/v1/verify/{STATE['units'][2]}")
    assert r.json()["status"] == "flagged"
    # non-admin FLAG -> 403
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-flag-2", "target_type": "unit",
                          "target_id": STATE["units"][3], "event_type": "FLAG"},
                    headers=mh)
    assert r.status_code == 403
    # recall a batch -> recalled
    r = client.post("/api/v1/batches",
                    json={"product_id": STATE["product"], "batch_number": "B-REC",
                          "quantity": 1},
                    headers=mh)
    batch2 = r.json()["id"]
    r = client.post(f"/api/v1/batches/{batch2}/units", json={"count": 1}, headers=mh)
    uid_rec = r.json()["unit_ids"][0]
    r = client.post(f"/api/v1/batches/{batch2}/recall", json={"reason": "contamination"},
                    headers=mh)
    assert r.status_code == 200 and r.json()["affected_units"] == 1
    assert client.get(f"/api/v1/verify/{uid_rec}").json()["status"] == "recalled"


def test_impossible_travel_detection(client):
    mh = auth(STATE["mfg_token"])
    dh = auth(STATE["dist_token"])
    unit = STATE["units"][4]
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-gps-1", "target_type": "unit",
                          "target_id": unit, "event_type": "DISPATCH",
                          "gps_lat": 12.97, "gps_lng": 77.59},  # Bengaluru
                    headers=mh)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-gps-2", "target_type": "unit",
                          "target_id": unit, "event_type": "RECEIVE",
                          "gps_lat": 28.61, "gps_lng": 77.20},  # Delhi, seconds later
                    headers=dh)
    assert r.status_code == 200, r.text
    r = client.get("/api/v1/alerts?reason=impossible_travel", headers=mh)
    assert r.status_code == 200, r.text
    assert any(a["target_id"] == unit for a in r.json())
    # high-severity auto-flag froze the unit
    r = client.get(f"/api/v1/units/{unit}", headers=mh)
    assert r.json()["current_state"] == "FLAGGED"


def test_transfer_exception(client):
    mh = auth(STATE["mfg_token"])
    stranger = login(client, STRANGER)
    sh = auth(stranger["access_token"])
    r = client.post("/api/v1/orgs", json={"name": "Stranger", "org_type": "retailer"}, headers=sh)
    asyncio.run(_approve_org(r.json()["id"]))
    stranger_org = r.json()["id"]
    unit = STATE["units"][5]
    client.post("/api/v1/events",
                json={"client_event_id": "evt-exc-d", "target_type": "unit",
                      "target_id": unit, "event_type": "DISPATCH"},
                headers=mh)
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-exc-r", "target_type": "unit",
                          "target_id": unit, "event_type": "RECEIVE"},
                    headers=sh)
    assert r.status_code == 403
    r = client.post(f"/api/v1/units/{unit}/transfer-exception",
                    json={"recipient_org_id": stranger_org, "reason": "emergency reroute"},
                    headers=mh)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/events",
                    json={"client_event_id": "evt-exc-r", "target_type": "unit",
                          "target_id": unit, "event_type": "RECEIVE"},
                    headers=sh)
    assert r.status_code == 200, r.text


def test_containers_disclosures_exports(client):
    mh = auth(STATE["mfg_token"])
    ah = auth(STATE["admin_token"])
    # containers
    r = client.post("/api/v1/containers",
                    json={"container_type": "box", "child_unit_ids": STATE["units"][6:8]},
                    headers=mh)
    assert r.status_code == 200, r.text
    assert len(r.json()["children"]) == 2
    ctr = r.json()["id"]
    r = client.post(f"/api/v1/containers/{ctr}/disaggregate", headers=mh)
    assert r.status_code == 200 and r.json()["disaggregated"] is True
    # disclosure fields (admin) + product values
    r = client.post("/api/v1/disclosure-fields",
                    json={"category": "pharma", "field_key": "generic_name",
                          "label": "Generic name", "required": True},
                    headers=ah)
    assert r.status_code == 200, r.text
    r = client.put(f"/api/v1/products/{STATE['product']}/disclosures",
                   json={"values": {"generic_name": "Paracetamol"}}, headers=mh)
    assert r.status_code == 200, r.text
    r = client.get(f"/api/v1/verify/{STATE['units'][0]}")
    assert any(d["field_key"] == "generic_name" and d["value"] == "Paracetamol"
               for d in r.json()["disclosures"])
    # label exports
    for fmt, ctype in [("csv", "text/csv"), ("pdf_sheet", "application/pdf"),
                       ("zpl", "text/plain")]:
        r = client.post(f"/api/v1/batches/{STATE['batch']}/export-labels",
                        json={"format": fmt}, headers=mh)
        assert r.status_code == 200, (fmt, r.text)
        assert ctype in r.headers["content-type"]


def test_webhooks_and_sessions(client):
    mh = auth(STATE["mfg_token"])
    transporter = login(client, TRANSPORT)
    th = auth(transporter["access_token"])
    r = client.post("/api/v1/orgs", json={"name": "Trans", "org_type": "transporter"}, headers=th)
    torg = r.json()["id"]
    asyncio.run(_approve_org(torg))
    r = client.get("/api/v1/orgs/me", headers=th)
    secret = r.json()["webhook_secret"]
    assert secret
    # bad secret -> 401
    r = client.post(f"/api/v1/integrations/webhooks/transporter/{torg}",
                    json={"action": "pickup", "target_ids": [STATE["units"][8]]},
                    headers={"X-Webhook-Secret": "wrong"})
    assert r.status_code == 401
    # transporter has no edge -> 403 through the same check
    r = client.post(f"/api/v1/integrations/webhooks/transporter/{torg}",
                    json={"action": "pickup", "target_ids": [STATE["units"][8]]},
                    headers={"X-Webhook-Secret": secret})
    assert r.status_code == 403
    # sessions listing
    r = client.get("/api/v1/auth/sessions", headers=mh)
    assert r.status_code == 200 and len(r.json()) >= 1


def test_mfa_flow(client):
    mh = auth(STATE["mfg_token"])
    r = client.post("/api/v1/auth/mfa/enroll", headers=mh)
    assert r.status_code == 200, r.text
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/api/v1/auth/mfa/confirm", json={"code": code}, headers=mh)
    assert r.status_code == 200, r.text
    r = client.post("/api/v1/auth/otp/request", json={"phone": MFG})
    otp = r.json()["debug_otp"]
    r = client.post("/api/v1/auth/otp/verify", json={"phone": MFG, "otp": otp})
    assert r.status_code == 200 and r.json()["mfa_required"] is True
    r = client.post("/api/v1/auth/mfa/challenge",
                    json={"mfa_token": r.json()["mfa_token"],
                          "code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200 and r.json()["access_token"]
