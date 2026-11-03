"""The Desktop half's HTTP routes, served by FastAPI exactly as Hermes mounts them."""

from __future__ import annotations

import json


def test_routes_connect_list_install_and_refuse_in_plain_words(hermes, kb):
    api = hermes.plugin / "dashboard" / "plugin_api.py"
    code = f"""
import importlib.util, json, sys
from fastapi import FastAPI
from fastapi.testclient import TestClient
spec = importlib.util.spec_from_file_location("kbapi", {str(api)!r})
mod = importlib.util.module_from_spec(spec); sys.modules["kbapi"] = mod; spec.loader.exec_module(mod)
app = FastAPI(); app.include_router(mod.router, prefix="/api/plugins/requrv-kb")
c = TestClient(app)
out = {{}}
out["before"] = c.get("/api/plugins/requrv-kb/connection").json()
out["bad"] = c.post("/api/plugins/requrv-kb/connection", json={{"roots": ["/nope"]}}).json()
out["connect"] = c.post("/api/plugins/requrv-kb/connection", json={{"roots": [{str(kb['library'])!r}, {str(kb['area'])!r}],
                                                                  "personal": {str(kb['personal'])!r}}}).status_code
out["names"] = [e["name"] for e in c.get("/api/plugins/requrv-kb/library").json()["entries"]]
out["install"] = c.post("/api/plugins/requrv-kb/library/install", json={{"name": "marketing"}}).json()
out["again"] = c.post("/api/plugins/requrv-kb/library/install", json={{"name": "marketing"}})
out["again"] = [out["again"].status_code, out["again"].json()["detail"]]
out["bots"] = c.get("/api/plugins/requrv-kb/bots").json()
print(json.dumps(out))
"""
    out = json.loads(hermes.python(code, hermes.root))
    assert out["before"] == {"connection": None, "check": None}
    assert "non esiste" in out["bad"]["detail"]
    assert out["connect"] == 200
    assert out["names"] == ["marketing"]
    assert out["install"]["profile"] == "marketing"
    assert out["again"][0] == 400 and "Esiste già" in out["again"][1]
    assert [b["profile"] for b in out["bots"]["bots"]] == ["marketing"]
