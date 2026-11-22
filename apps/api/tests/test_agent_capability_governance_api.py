"""ENG-P06 capability governance routes enforce operator scope and durable decisions."""
from fastapi import Request
from fastapi.testclient import TestClient
from allpha_api.main import app, _capability_review_operator

CAPABILITY = "11111111-1111-4111-8111-111111111111"
AGENT = "22222222-2222-4222-8222-222222222222"

async def _operator(request: Request):
    return {"id": "33333333-3333-4333-8333-333333333333", "scopes": ["platform:capabilities.review"]}

def _client(monkeypatch, rpc):
    monkeypatch.setattr("allpha_api.main.privileged_rest_request", rpc)
    async def audit(*args, **kwargs):
        return None
    monkeypatch.setattr("allpha_api.main.write_operator_audit", audit)
    app.dependency_overrides[_capability_review_operator] = _operator
    return TestClient(app)

def test_low_risk_capability_decision_is_server_reviewed(monkeypatch):
    calls=[]
    current={"id":CAPABILITY,"agent_id":AGENT,"capability_key":"calendar.read","risk_level":"low","status":"requested"}
    async def rpc(method,table,*,params=None,body=None,prefer=None):
        calls.append((method,table,params,body,prefer))
        return [current] if method=="GET" else [{**current,**body}]
    client=_client(monkeypatch,rpc)
    try:
        response=client.post(f"/v1/admin/agent-capabilities/{CAPABILITY}/decision",json={"decision":"approved","reason":"Scope reviewed and bounded."})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==200
    assert response.json()["capability"]["status"]=="approved"
    assert response.json()["runtime_authorized"] is False
    assert calls[0][0:2]==("GET","agent_capabilities")
    assert calls[1][0:2]==("PATCH","agent_capabilities")
    assert calls[1][3]["reviewed_by"]=="33333333-3333-4333-8333-333333333333"

def test_high_risk_capability_requires_separate_scope(monkeypatch):
    calls=[]
    current={"id":CAPABILITY,"agent_id":AGENT,"capability_key":"payments.execute","risk_level":"critical","status":"requested"}
    async def rpc(method,table,*,params=None,body=None,prefer=None):
        calls.append((method,table,params,body,prefer))
        return [current]
    client=_client(monkeypatch,rpc)
    try:
        response=client.post(f"/v1/admin/agent-capabilities/{CAPABILITY}/decision",json={"decision":"approved","reason":"Critical scope review."})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==403
    assert len(calls)==1

def test_capability_revocation_requires_approved_state(monkeypatch):
    calls=[]
    current={"id":CAPABILITY,"agent_id":AGENT,"capability_key":"calendar.read","risk_level":"low","status":"approved"}
    async def rpc(method,table,*,params=None,body=None,prefer=None):
        calls.append((method,table,params,body,prefer))
        return [current] if method=="GET" else [{**current,**body}]
    client=_client(monkeypatch,rpc)
    try:
        response=client.post(f"/v1/admin/agent-capabilities/{CAPABILITY}/decision",json={"decision":"revoked","reason":"Owner permission withdrawn."})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code==200
    assert response.json()["capability"]["status"]=="revoked"
    assert calls[1][3]["review_reason"]=="Owner permission withdrawn."
