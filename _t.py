import importlib.util, json, sys, tempfile, pathlib

spec = importlib.util.spec_from_file_location("postcard", "scripts/postcard.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

tmp = pathlib.Path(tempfile.mkdtemp())
m.TOKEN_FILE = tmp / "token.json"
m.POLLI_CREDENTIALS = tmp / "missing.json"
import os
os.environ.pop("POLLINATIONS_API_KEY", None)
assert m.api_key() == "" and m.key_source() == "anonymous"

calls = {"n": 0}
def fake_post(url, payload, timeout=60):
    calls["n"] += 1
    if url.endswith("/api/device/code"):
        assert payload["scope"] == m.LOGIN_SCOPE
        return 200, {"device_code": "d1", "user_code": "ABC", "interval": 0, "expires_in": 30,
                     "verification_uri_complete": "https://enter.pollinations.ai/device?user_code=ABC"}
    if calls["n"] < 4:
        return 400, {"error": "authorization_pending"}
    return 200, {"access_token": "tok_test"}

m.post_json = fake_post
m.time.sleep = lambda s: None
m.webbrowser.open = lambda url: True
assert m.login() == 0
assert m.api_key() == "tok_test", m.api_key()
assert m.key_source() == "signed in (postcard token)"
mode = oct(m.TOKEN_FILE.stat().st_mode)[-3:]
assert mode == "600", mode
# polli credentials reuse, no token
m.TOKEN_FILE.unlink()
m.POLLI_CREDENTIALS.write_text(json.dumps({"apiKey": "polli_key"}))
assert m.api_key() == "polli_key" and m.key_source() == "signed in (polli)"
# env last
os.environ["POLLINATIONS_API_KEY"] = "env_key"
assert m.api_key() == "polli_key"
print("ok: token store, 600 mode, polli reuse, precedence, pending loop")
