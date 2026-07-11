import pytest
from app.services import integration_tester


def test_api_football_uses_direct_host_and_header(monkeypatch):
    seen = {}
    def fake(url, headers=None):
        seen.update(url=url, headers=headers)
        return {"ok": True, "status": 200, "data": {"response": {}}, "error": None, "content_type": "application/json"}
    monkeypatch.setattr(integration_tester.http_client, "request_json", fake)
    result = integration_tester.test_candidate("api_football", "api_key", "  secret  ")
    assert result["ok"]
    assert seen["url"].endswith("/status")
    assert seen["headers"] == {"x-apisports-key": "secret"}
    assert "X-Auth-Token" not in seen["headers"] and "x-rapidapi-key" not in seen["headers"]

@pytest.mark.parametrize("result,code", [
 ({"ok": False,"status":401,"error":"HTTP 401","content_type":"application/json"}, "invalid_key"),
 ({"ok": False,"status":403,"error":"HTTP 403","content_type":"application/json"}, "forbidden"),
 ({"ok": False,"status":429,"error":"HTTP 429","content_type":"application/json"}, "quota_exceeded"),
 ({"ok": False,"status":None,"error":"timeout","content_type":None}, "timeout"),
 ({"ok": True,"status":200,"data":"bad","error":None,"content_type":"application/json"}, "invalid_response"),
])
def test_api_football_failures_are_sanitized(monkeypatch, result, code):
    monkeypatch.setattr(integration_tester.http_client, "request_json", lambda *args, **kwargs: result)
    assert integration_tester.test_candidate("api_football", "api_key", "secret")["error_code"] == code
