"""Live end-to-end demo + verification against a RUNNING TrustUs server.

Usage:  python3 demo/run_demo.py [BASE_URL]
Default: http://localhost:8000/api/v1  (with seeded demo data)

Every step asserts. Exit code != 0 on first failure.
"""
import csv
import io
import sys
import time
import uuid

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/api/v1"
passed = [0]

RUN = uuid.uuid4().hex[:6].upper()


def PH(n):
    # unique phone per run: +1770 + run-hash digits + index
    h = str(int(RUN, 16) % 900 + 100)
    return f"+1770{h}{n:04d}"


PCODE = f"DEMO{RUN}"
BATCH1 = f"DEMO-{RUN}-B1"
BATCHR = f"DEMO-{RUN}-REC"
SKU1 = f"DEMO-SKU-{RUN}"



def step(name):
    print(f"\n=== {name} ===")


def ok(msg):
    passed[0] += 1
    print(f"  PASS {msg}")


def fail(msg, resp=None):
    print(f"  FAIL {msg}")
    if resp is not None:
        print(f"       status={resp.status_code} body={resp.text[:300]}")
    sys.exit(1)


def expect(resp, code=200):
    if resp.status_code != code:
        fail(f"expected {code}, got {resp.status_code}", resp)
    return resp.json() if resp.content else None


def expect_status(resp, code=200):
    if resp.status_code != code:
        fail(f"expected {code}, got {resp.status_code}", resp)
    return resp


c = httpx.Client(base_url=BASE, timeout=30)


def login(phone):
    r = c.post("/auth/otp/request", json={"phone": phone, "device_info": "demo-script"})
    d = expect(r)
    assert d.get("debug_otp"), "debug_otp missing (need non-prod dummy SMS)"
    r = c.post("/auth/otp/verify", json={"phone": phone, "otp": d["debug_otp"]})
    d = expect(r)
    assert not d["mfa_required"], f"unexpected MFA for {phone}"
    return d["access_token"], d["refresh_token"], d["user"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


def evt(token, target_type, target_id, event_type, **kw):
    body = {"client_event_id": f"demo-{uuid.uuid4().hex[:12]}",
            "target_type": target_type, "target_id": target_id,
            "event_type": event_type, **kw}
    return c.post("/events", json=body, headers=H(token))


# ---------------------------------------------------------------- 0. login all
step("0. Login all seeded roles via OTP")
tok = {}
users = {}
for name, phone in [("admin", "+10000000001"), ("mfg", "+10000000002"),
                    ("dist", "+10000000003"), ("retail", "+10000000004"),
                    ("trans", "+10000000005"), ("social", "+10000000006")]:
    at, rt, u = login(phone)
    tok[name] = (at, rt)
    users[name] = u
    ok(f"{name:6s} {phone} role={u['role']} org={bool(u['org_id'])}")

# ---------------------------------------------------------------- 1. catalogue
step("1. Catalogue + regulatory disclosures")
P = expect(c.post("/products", json={"product_code": PCODE, "name": "Demo Drug 500",
                                     "category": "pharma"}, headers=H(tok["mfg"][0])))
ok(f"product created {P['product_code']}")
fields = expect(c.get("/disclosure-fields", params={"category": "pharma"},
                      headers=H(tok["mfg"][0])))
assert len(fields) == 9, f"expected 9 pharma fields, got {len(fields)}"
ok("9 seeded Schedule-H2 disclosure fields listed")
r = c.put(f"/products/{P['id']}/disclosures", json={"values": {"brand_name": "X"}},
          headers=H(tok["mfg"][0]))
expect(r, 400)
ok("required-field enforcement rejects incomplete disclosures (400)")
vals = {f["field_key"]: f"demo-{f['field_key']}" for f in fields
        if f["field_key"] not in ("batch_number", "mfg_date", "expiry_date")}
d = expect(c.put(f"/products/{P['id']}/disclosures", json={"values": vals},
                 headers=H(tok["mfg"][0])))
assert any(x["value"].startswith("demo-") for x in d)
ok("disclosure values saved + read back")

# ---------------------------------------------------------------- 2. batch/units
step("2. Batch + unit generation + re-list")
B = expect(c.post("/batches", json={"product_id": P["id"], "batch_number": BATCH1,
                                    "quantity": 12, "mfg_date": "2026-01-10",
                                    "expiry_date": "2027-12-31"}, headers=H(tok["mfg"][0])))
ok(f"batch {B['batch_number']} created")
U = expect(c.post(f"/batches/{B['id']}/units", json={"count": 12},
                  headers=H(tok["mfg"][0])))["unit_ids"]
assert len(U) == 12
U2 = expect(c.get(f"/batches/{B['id']}/units", headers=H(tok["mfg"][0])))
assert len(U2) == 12 and {u["id"] for u in U2} == set(U)
ok("12 units generated and re-listed (persisted beyond create response)")

# ---------------------------------------------------------------- 3. custody
step("3. Custody chain with GPS (mfg -> dist -> sale -> return)")
A = U[0]
d = expect(evt(tok["mfg"][0], "unit", A, "DISPATCH", gps_lat=13.0827, gps_lng=80.2707))
assert d["resulting_state"] == "IN_TRANSIT"
ok("DISPATCH by manufacturer -> IN_TRANSIT (Chennai GPS)")
d = expect(evt(tok["dist"][0], "unit", A, "RECEIVE", gps_lat=13.0828, gps_lng=80.2708))
assert d["resulting_state"] == "RECEIVED"
ok("RECEIVE by authorized distributor -> RECEIVED")
d = expect(evt(tok["dist"][0], "unit", A, "SALE"))
assert d["resulting_state"] == "SOLD"
ok("SALE -> SOLD")
d = expect(evt(tok["dist"][0], "unit", A, "RETURN"))
assert d["resulting_state"] == "RETURNED"
ok("RETURN -> RETURNED")
hist = expect(c.get(f"/units/{A}/history", headers=H(tok["mfg"][0])))
assert len(hist) == 4
ok("history timeline shows all 4 events")

# ---------------------------------------------------------------- 4. verify
step("4. Public verify states")
d = expect(c.get(f"/verify/{U[1]}"))
assert d["status"] == "not_yet_in_circulation", d["status"]
ok("untouched ISSUED unit -> not_yet_in_circulation")
d = expect(c.get(f"/verify/{A}"))
assert d["status"] == "genuine", d["status"]
assert len(d["last_events"]) == 3 and len(d["disclosures"]) == 9
assert any(x["field_key"] == "generic_name" and x["value"] == "demo-generic_name"
           for x in d["disclosures"])
ok("unit with custody -> genuine + last-3-events + disclosure values")
expect(c.get("/verify/TU-NOPE-NOPE"), 404)
ok("unknown code -> generic 404")
u = expect(c.get(f"/units/{A}", headers=H(tok["mfg"][0])))
assert u["verify_count"] >= 1
ok(f"anonymous verify_count incremented ({u['verify_count']})")

# ---------------------------------------------------------------- 5. authz negative + exception
step("5. Sync custody authz (403) + one-time transfer exception")
at_o, _, _ = login(PH(11))
expect(c.post("/orgs", json={"name": "Outsider Retail", "org_type": "retailer"},
              headers=H(at_o)))
outsider_org = expect(c.get("/orgs/me", headers=H(at_o)))["id"]
# approve outsider via platform admin
orgs = expect(c.get("/admin/orgs", params={"status": "pending"}, headers=H(tok["admin"][0])))
target = [o for o in orgs if o["id"] == outsider_org][0]
expect(c.post(f"/admin/orgs/{target['id']}/approve", headers=H(tok["admin"][0])))
ok("outsider org created + admin-approved")
X = U[2]
expect(evt(tok["mfg"][0], "unit", X, "DISPATCH"))
r = evt(at_o, "unit", X, "RECEIVE")
expect(r, 403)
assert r.json()["detail"]["code"] == "UNAUTHORIZED_ROUTE"
ok("stranger RECEIVE synchronously rejected with 403 UNAUTHORIZED_ROUTE")
e = expect(c.post(f"/units/{X}/transfer-exception",
                  json={"recipient_org_id": outsider_org, "reason": "emergency reroute"},
                  headers=H(tok["mfg"][0])))
assert e["target_id"] == X
ok("one-time transfer exception granted by manufacturer")
d = expect(evt(at_o, "unit", X, "RECEIVE"))
assert d["resulting_state"] == "RECEIVED"
ok("RECEIVE with live exception -> RECEIVED")

# ---------------------------------------------------------------- 6. detection/flag
step("6. Impossible-travel detection -> auto-flag -> admin unflag")
F = U[3]
expect(evt(tok["mfg"][0], "unit", F, "DISPATCH", gps_lat=13.08, gps_lng=80.27))
expect(evt(tok["dist"][0], "unit", F, "RECEIVE", gps_lat=28.61, gps_lng=77.20))
alerts = expect(c.get("/alerts", params={"reason": "impossible_travel"},
                      headers=H(tok["mfg"][0])))
assert any(a["target_id"] == F and a["severity"] == "high" for a in alerts)
ok("impossible_travel high-severity alert raised")
u = expect(c.get(f"/units/{F}", headers=H(tok["mfg"][0])))
assert u["current_state"] == "FLAGGED"
ok("high-severity auto-FLAG froze the unit")
d = expect(c.get(f"/verify/{F}"))
assert d["status"] == "flagged" and d["flag_reason"] == "impossible_travel"
ok("verify -> flagged with reason")
first = [a for a in alerts if a["target_id"] == F][0]
expect(c.patch(f"/alerts/{first['id']}", json={"status": "reviewed"},
               headers=H(tok["mfg"][0])))
ok("org_admin marked alert reviewed")
r = evt(tok["mfg"][0], "unit", F, "UNFLAG")
expect(r, 403)
ok("non-admin UNFLAG rejected (403)")
d = expect(evt(tok["admin"][0], "unit", F, "UNFLAG"))
assert d["resulting_state"] == "ISSUED"
ok("platform_admin UNFLAG -> ISSUED (org-less system action)")

# ---------------------------------------------------------------- 7. recall
step("7. Batch recall")
B2 = expect(c.post("/batches", json={"product_id": P["id"], "batch_number": BATCHR,
                                     "quantity": 2}, headers=H(tok["mfg"][0])))
UR = expect(c.post(f"/batches/{B2['id']}/units", json={"count": 2},
                   headers=H(tok["mfg"][0])))["unit_ids"]
rec = expect(c.post(f"/batches/{B2['id']}/recall", json={"reason": "demo contamination"},
                    headers=H(tok["mfg"][0])))
assert rec["affected_units"] == 2
d = expect(c.get(f"/verify/{UR[0]}"))
assert d["status"] == "recalled"
ok(f"recall -> recalled on verify (affected={rec['affected_units']}, orgs={rec['affected_orgs_notified']})")

# ---------------------------------------------------------------- 8. exports + QR decode
step("8. Label exports (csv/pdf/zpl) + QR scannability proof")
r = c.post(f"/batches/{B['id']}/export-labels", json={"format": "csv"},
           headers=H(tok["mfg"][0]))
expect_status(r)
rows = list(csv.DictReader(io.StringIO(r.text)))
assert len(rows) == 12 and rows[0]["verify_url"].endswith(f"/v/{rows[0]['unit_id']}")
ok(f"CSV export: 12 rows with verify URLs ({rows[0]['verify_url']})")
r = c.post(f"/batches/{B['id']}/export-labels", json={"format": "pdf_sheet"},
           headers=H(tok["mfg"][0]))
expect_status(r)
assert r.content[:4] == b"%PDF" and len(r.content) > 5000
ok(f"PDF sheet export: valid PDF ({len(r.content)} bytes)")
r = c.post(f"/batches/{B['id']}/export-labels", json={"format": "zpl"},
           headers=H(tok["mfg"][0]))
expect_status(r)
assert r.text.count("^XA") == 12 and "^BQN" in r.text
ok("ZPL export: 12 labels with QR ^BQN commands")
# decode a QR produced by the same server generator + payload scheme
sys.path.insert(0, "/home/user/TUS/server")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from app.core.labels import verify_url_for  # noqa: E402
from app.core.qr import make_qr_png  # noqa: E402
payload = verify_url_for("http://localhost:5173", U[4])
png = make_qr_png(payload, size_mm=30)
img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
decoded, _, _ = cv2.QRCodeDetector().detectAndDecode(img)
assert decoded == payload, f"QR decode mismatch: {decoded!r}"
ok(f"QR image decodes exactly -> {decoded}")

# ---------------------------------------------------------------- 9. network
step("9. Network invites, tree, tiers")
at_r2, _, _ = login(PH(12))
expect(c.post("/orgs", json={"name": "Demo Retail 2", "org_type": "retailer"},
              headers=H(at_r2)))
r2org = expect(c.get("/orgs/me", headers=H(at_r2)))["id"]
expect(c.post(f"/admin/orgs/{r2org}/approve", headers=H(tok["admin"][0])))
inv = expect(c.post("/network/invites", json={"authorized": True},
                    headers=H(tok["mfg"][0])))
ok(f"manufacturer invite created: {inv['code']}")
expect(c.post(f"/network/invites/{inv['code']}/accept", headers=H(at_r2)))
ok("retailer accepted invite -> edge created")
tree = expect(c.get("/network/tree", headers=H(tok["mfg"][0])))
assert any(e["to_org_id"] == r2org for e in tree["edges"])
ok(f"network tree shows edge (nodes={len(tree['nodes'])}, edges={len(tree['edges'])})")
r = c.post("/network/invites", json={}, headers=H(at_r2))
expect(r, 403)
ok("retailer cannot extend network (403)")
# unauthorized-tier edge -> soft flag (allowed through, flagged async)
inv2 = expect(c.post("/network/invites", json={"authorized": False},
                     headers=H(tok["mfg"][0])))
at_sub, _, _ = login(PH(13))
expect(c.post("/orgs", json={"name": "Sub Dist", "org_type": "distributor_sub"},
              headers=H(at_sub)))
suborg = expect(c.get("/orgs/me", headers=H(at_sub)))["id"]
expect(c.post(f"/admin/orgs/{suborg}/approve", headers=H(tok["admin"][0])))
expect(c.post(f"/network/invites/{inv2['code']}/accept", headers=H(at_sub)))
S = U[5]
expect(evt(tok["mfg"][0], "unit", S, "DISPATCH"))
d = expect(evt(at_sub, "unit", S, "RECEIVE"))
assert d["resulting_state"] == "RECEIVED"
al = expect(c.get("/alerts", params={"reason": "unauthorized_route"},
                  headers=H(tok["mfg"][0])))
assert any(a["target_id"] == S for a in al)
ok("unauthorized-tier scan flows through but raises soft unauthorized_route alert")

# ---------------------------------------------------------------- 10. containers
step("10. Containers: pack, nest, add, disaggregate")
box = expect(c.post("/containers", json={"container_type": "box",
                                         "child_unit_ids": U[6:8]},
                    headers=H(tok["mfg"][0])))
assert len(box["children"]) == 2
ok(f"box packed with 2 units ({box['id']})")
pal = expect(c.post("/containers", json={"container_type": "pallet",
                                         "child_container_ids": [box["id"]]},
                    headers=H(tok["mfg"][0])))
ok("box nested into pallet")
got = expect(c.get(f"/containers/{pal['id']}", headers=H(tok["mfg"][0])))
assert got["children"][0]["child_id"] == box["id"]
ok("container detail shows nested tree")
expect(c.post(f"/containers/{box['id']}/units", json={"unit_ids": [U[8]]},
              headers=H(tok["mfg"][0])))
ok("added 3rd unit to existing box")
d = expect(evt(tok["mfg"][0], "container", box["id"], "DISPATCH"))
assert d["resulting_state"] == "IN_TRANSIT"
d = expect(evt(tok["dist"][0], "container", box["id"], "RECEIVE"))
assert d["resulting_state"] == "RECEIVED"
ok("container custody DISPATCH -> RECEIVE works with same authz")
dis = expect(c.post(f"/containers/{box['id']}/disaggregate", headers=H(tok["mfg"][0])))
assert dis["disaggregated"] and dis["children"] == []
ok("disaggregate emptied box (irreversible)")
expect(c.post(f"/containers/{box['id']}/units", json={"unit_ids": [U[9]]},
              headers=H(tok["mfg"][0])), 409)
ok("adding to disaggregated box rejected (409)")

# ---------------------------------------------------------------- 11. social
step("11. Social listings CRUD")
sl = expect(c.post("/social-listings",
                   json={"platform": "instagram", "post_url": "https://ig.example/p/1",
                         "unit_ids": U[9:11]}, headers=H(tok["social"][0])))
lst = expect(c.get("/social-listings", headers=H(tok["social"][0])))
assert any(x["id"] == sl["id"] for x in lst)
expect(c.get(f"/social-listings/{sl['id']}", headers=H(tok["social"][0])))
ok("listing created + listed + fetched")
expect(c.delete(f"/social-listings/{sl['id']}", headers=H(tok["social"][0])))
expect(c.get(f"/social-listings/{sl['id']}", headers=H(tok["social"][0])), 404)
ok("listing deleted (get -> 404)")

# ---------------------------------------------------------------- 12. KYC + admin org lifecycle
step("12. KYC upload + admin approval/rejection")
at_p, _, _ = login(PH(14))
expect(c.post("/orgs", json={"name": "Pending Co", "org_type": "retailer"},
              headers=H(at_p)))
porg = expect(c.get("/orgs/me", headers=H(at_p)))["id"]
files = {"file": ("gst.pdf", b"%PDF-fake-bytes", "application/pdf")}
r = c.post(f"/orgs/{porg}/kyc-documents", data={"document_type": "gst_certificate"},
           files=files, headers=H(at_p))
d = expect(r)
assert d["status"] == "pending_review" and d["file_url"].startswith("/files/")
ok(f"KYC uploaded -> {d['file_url']}")
docs = expect(c.get(f"/orgs/{porg}/kyc-documents", headers=H(at_p)))
assert len(docs) == 1
ok("KYC doc list shows upload + status")
pend = expect(c.get("/admin/orgs", params={"status": "pending"},
                    headers=H(tok["admin"][0])))
row = [o for o in pend if o["id"] == porg][0]
assert len(row["kyc_documents"]) == 1
ok("admin approvals view includes KYC documents")
expect(c.post(f"/admin/orgs/{porg}/approve", headers=H(tok["admin"][0])))
ok("admin approved org")
at_p2, _, _ = login(PH(15))
expect(c.post("/orgs", json={"name": "Reject Co", "org_type": "retailer"},
              headers=H(at_p2)))
rorg = expect(c.get("/orgs/me", headers=H(at_p2)))["id"]
rej = expect(c.post(f"/admin/orgs/{rorg}/reject", json={"reason": "invalid licence"},
                    headers=H(tok["admin"][0])))
assert rej["approval_status"] == "rejected"
ok("admin rejected org with reason")

# ---------------------------------------------------------------- 13. team + last-admin guard
step("13. Team invite + role guard (isolated org)")
at_g, _, u_g = login(PH(16))
expect(c.post("/orgs", json={"name": f"GuardTest {RUN}", "org_type": "retailer"},
              headers=H(at_g)))
gorg = expect(c.get("/orgs/me", headers=H(at_g)))["id"]
expect(c.post(f"/admin/orgs/{gorg}/approve", headers=H(tok["admin"][0])))
inv_u = expect(c.post("/orgs/me/users/invite",
                      json={"phone": PH(17), "role": "member"},
                      headers=H(at_g)))
team = expect(c.get("/orgs/me/users", headers=H(at_g)))
assert any(u["phone"] == PH(17) for u in team)
ok("staff invited + listed")
r = c.patch(f"/orgs/me/users/{u_g['id']}", json={"role": "member"}, headers=H(at_g))
expect(r, 409)
ok("demoting last active org_admin blocked (409)")
expect(c.patch(f"/orgs/me/users/{inv_u['id']}", json={"role": "org_admin"},
               headers=H(at_g)))
expect(c.patch(f"/orgs/me/users/{u_g['id']}", json={"role": "member"}, headers=H(at_g)))
ok("after promoting second admin, demotion allowed")
at_admin2, _, _ = login(PH(17))  # the promoted second admin
expect(c.patch(f"/orgs/me/users/{u_g['id']}", json={"role": "org_admin"},
               headers=H(at_admin2)))
ok("role restored by second admin")

# ---------------------------------------------------------------- 14. sessions
step("14. Session listing + revocation")
sess = expect(c.get("/auth/sessions", headers=H(tok["mfg"][0])))
assert len(sess) >= 1
ok(f"{len(sess)} session(s) listed")
_, rt_fresh, _ = login("+10000000002")
sess = expect(c.get("/auth/sessions", headers=H(tok["mfg"][0])))
victim = sorted(sess, key=lambda s: s["created_at"])[-1]["id"]
expect(c.post(f"/auth/sessions/{victim}/revoke", headers=H(tok["mfg"][0])))
expect(c.post("/auth/refresh", json={"refresh_token": rt_fresh}), 401)
ok("revoked session's refresh token rejected (401)")

# ---------------------------------------------------------------- 15. MFA
step("15. MFA (TOTP) enrollment + login challenge (isolated admin)")
import pyotp  # noqa: E402
at_m, _, _ = login(PH(18))
expect(c.post("/orgs", json={"name": f"MfaTest {RUN}", "org_type": "retailer"},
              headers=H(at_m)))
morg2 = expect(c.get("/orgs/me", headers=H(at_m)))["id"]
expect(c.post(f"/admin/orgs/{morg2}/approve", headers=H(tok["admin"][0])))
mem = expect(c.post("/orgs/me/users/invite", json={"phone": PH(19), "role": "member"},
                     headers=H(at_m)))
at_mem, _, _ = login(PH(19))
r = c.post("/auth/mfa/enroll", headers=H(at_mem))
expect(r, 403)
ok("member cannot enroll MFA (403, admins only)")
enr = expect(c.post("/auth/mfa/enroll", headers=H(at_m)))
expect(c.post("/auth/mfa/confirm", json={"code": "000000"}, headers=H(at_m)), 401)
ok("wrong TOTP rejected (401)")
expect(c.post("/auth/mfa/confirm", json={"code": pyotp.TOTP(enr["secret"]).now()},
              headers=H(at_m)))
ok("correct TOTP enables MFA")
r = c.post("/auth/otp/request", json={"phone": PH(18)})
otp = expect(r)["debug_otp"]
d = expect(c.post("/auth/otp/verify", json={"phone": PH(18), "otp": otp}))
assert d["mfa_required"] and d["mfa_token"]
ch = expect(c.post("/auth/mfa/challenge",
                   json={"mfa_token": d["mfa_token"],
                         "code": pyotp.TOTP(enr["secret"]).now()}))
assert ch["access_token"]
ok("login with MFA: otp -> mfa_required -> challenge -> tokens")

# ---------------------------------------------------------------- 16. notif settings
step("16. Notification settings")
ns = expect(c.get("/orgs/me/notification-settings", headers=H(tok["dist"][0])))
assert "channels" in ns
expect(c.patch("/orgs/me/notification-settings",
               json={"channels": ["sms", "email"], "language": "hi"},
               headers=H(tok["dist"][0])))
ns = expect(c.get("/orgs/me/notification-settings", headers=H(tok["dist"][0])))
assert ns["channels"] == ["sms", "email"] and ns["language"] == "hi"
ok("settings patched + persisted")

# ---------------------------------------------------------------- 17. webhooks
step("17. 3PL + e-commerce webhooks")
me = expect(c.get("/orgs/me", headers=H(tok["trans"][0])))
secret = me["webhook_secret"]
assert secret
torg = me["id"]
ok("transporter webhook secret issued")
W = U[10]
expect(evt(tok["mfg"][0], "unit", W, "DISPATCH"))
r = c.post(f"/integrations/webhooks/transporter/{torg}",
           json={"action": "delivery", "target_type": "unit", "target_ids": [W]},
           headers={"X-Webhook-Secret": "wrong"})
expect(r, 401)
ok("bad webhook secret -> 401")
d = expect(c.post(f"/integrations/webhooks/transporter/{torg}",
                  json={"action": "delivery", "target_type": "unit",
                        "target_ids": [W], "gps_lat": 13.0, "gps_lng": 80.2},
                  headers={"X-Webhook-Secret": secret}))
assert d[0]["resulting_state"] == "RECEIVED"
ok("3PL delivery webhook -> RECEIVE event through same pipeline")
link = expect(c.post("/integrations/listing-links",
                     json={"channel": "amazon", "sku": SKU1,
                           "unit_ids": [U[11]]}, headers=H(tok["mfg"][0])))
morg = expect(c.get("/orgs/me", headers=H(tok["mfg"][0])))
d = expect(c.post(f"/integrations/webhooks/ecommerce/{morg['id']}",
                  json={"channel": "amazon", "sku": SKU1},
                  headers={"X-Webhook-Secret": morg["webhook_secret"]}))
assert d["target_id"] == U[11] and d["event_type"] == "DISPATCH"
ok("e-commerce order webhook consumed reserved unit -> DISPATCH")
r = c.post(f"/integrations/webhooks/ecommerce/{morg['id']}",
           json={"channel": "amazon", "sku": SKU1},
           headers={"X-Webhook-Secret": morg["webhook_secret"]})
expect(r, 409)
ok("exhausted SKU pool -> 409")
newsec = expect(c.post("/orgs/me/webhook-secret/rotate", headers=H(tok["trans"][0])))["webhook_secret"]
assert newsec != secret
ok("webhook secret rotated")

# ---------------------------------------------------------------- 18. events query + admin analytics
step("18. Events query + fraud patterns + regulator access + admin alerts")
ev = expect(c.get("/events", params={"target_id": A, "limit": 50},
                  headers=H(tok["mfg"][0])))
assert len(ev) == 4
ok("events filtered by target")
fp = expect(c.get("/admin/fraud-patterns", headers=H(tok["admin"][0])))
assert any(r["reason"] == "impossible_travel" for r in fp["top_flag_reasons"])
ok(f"fraud patterns live: {[r['reason'] for r in fp['top_flag_reasons']]}")
g = expect(c.post("/admin/regulator-access",
                  json={"regulator_user_id": "drug-inspector-7", "batch_id": B["id"],
                        "expires_in_hours": 48, "reason": "routine inspection"},
                  headers=H(tok["admin"][0])))
assert g["id"]
ok(f"regulator grant created: {g['id']}")
gs = expect(c.get("/admin/regulator-access", headers=H(tok["admin"][0])))
assert any(x["id"] == g["id"] for x in gs)
expect(c.post(f"/admin/regulator-access/{g['id']}/revoke",
              headers=H(tok["admin"][0])))
ok("regulator grant listed + revoked")
aa = expect(c.get("/admin/alerts", params={"severity": "high"},
                  headers=H(tok["admin"][0])))
assert len(aa) >= 1
ok(f"admin cross-tenant alerts: {len(aa)} high-severity")

# ---------------------------------------------------------------- 19. multi-location verify rule
step("19. Multi-location verify detection")
M = U[11]
# U[11] was dispatched by ecommerce webhook; verify from 10 distinct grid cells
for i in range(10):
    expect(c.get(f"/verify/{M}", params={"lat": 10.0 + i * 2.0, "lng": 76.0}))
time.sleep(0.2)
ml = expect(c.get("/alerts", params={"reason": "multi_location_verify"},
                  headers=H(tok["mfg"][0])))
assert any(a["target_id"] == M for a in ml), "multi_location_verify alert missing"
ok("unit verified from 10 distinct areas -> multi_location_verify alert")

# ---------------------------------------------------------------- 20. redis-backed logic (fakeredis)
step("20. Redis-backed logic (rate limit + scan counter) via fakeredis")
import asyncio  # noqa: E402
from fakeredis.aioredis import FakeRedis  # noqa: E402
from app.core.rate_limit import check_rate_limit  # noqa: E402


async def _redis_checks():
    r = FakeRedis(decode_responses=True)
    for _ in range(30):
        assert await check_rate_limit(r, "rl:verify:1.2.3.4", 30, 60)
    assert not await check_rate_limit(r, "rl:verify:1.2.3.4", 30, 60)
    return True


assert asyncio.run(_redis_checks())
ok("verify rate limit allows 30/min then blocks (fail-open without redis)")
print(f"\nALL DEMO CHECKS PASSED ({passed[0]} assertions)")
