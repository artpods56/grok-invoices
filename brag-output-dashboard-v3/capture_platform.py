"""Run an isolated fixture-backed API for filming the real dashboard. No network intake."""
import os
import tempfile
os.environ['DATA_DIR'] = tempfile.mkdtemp(prefix='grok-film-')
os.environ['SAMPLE_DATA'] = 'true'
os.environ['PLATFORM_API_KEY'] = ''
os.environ.pop('RELEASE', None)
from fastapi.testclient import TestClient
from grok_invoices.entrypoints.http import app
import uvicorn
with TestClient(app) as api:
    rows = api.post('/api/ksef/sync?source=fixtures').json()
    it, fuel, unknown = rows
    body = dict(account='402',vat_deduction_percent=100,rationale='Synthetic IT service fixture',confidence=0.95,actor='invoice_agent',source='rule')
    assert api.post(f"/api/invoices/{it['id']}/postings",json=body).status_code == 201
    match = api.get(f"/api/invoices/{fuel['id']}/precedents").json()[0]
    body.update(account='403',vat_deduction_percent=50,source='precedent',precedent_id=match['precedent']['id'],rationale='Matching fleet vehicle and use')
    assert api.post(f"/api/invoices/{fuel['id']}/postings",json=body).status_code == 201
    case=api.post(f"/api/invoices/{unknown['id']}/escalate",json={'reason':'Vehicle GD 9R247 is not in the fleet. Business context is missing.','actor':'invoice_agent'}).json()
    assert api.post(f"/api/cases/{case['id']}/questions",json={'text':'Which vehicle is GD 9R247, how is it used, and what was the business purpose?','actor':'regulations_agent'}).status_code == 201
print('Isolated film platform ready', flush=True)
uvicorn.run(app,host='127.0.0.1',port=8018,access_log=False)
