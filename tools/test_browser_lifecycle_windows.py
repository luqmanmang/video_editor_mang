"""Regression: active browser viewer reuses tab; closed viewer reopens exactly once."""
import json
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from repo.tools import studio_dashboard as d

server=ThreadingHTTPServer(("127.0.0.1",0),d.Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True)
thread.start()
original_port=d.PORT
d.PORT=server.server_port
d.BROWSER_VIEWERS.clear()
d.BROWSER_LAST_OPEN_CLAIM["at"]=0.0

def post(url,data):
    req=Request(
        f"http://127.0.0.1:{d.PORT}"+url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type":"application/json"},
        method="POST")
    with urlopen(req, timeout=2) as response:
        return json.loads(response.read())

try:
    assert d.claim_browser_open() is True, "Fresh instance must claim one browser opening"
    assert d.claim_browser_open() is False, "Second rapid claim must not open a duplicate"
    assert post("/api/browser-heartbeat",{"viewer_id":"viewer_test_tab123"})["active_viewers"]==1
    d.BROWSER_LAST_OPEN_CLAIM["at"]=0.0
    assert d.claim_browser_open() is False, "Live tab must block repeated browser opening"
    assert post("/api/browser-close",{"viewer_id":"viewer_test_tab123"})["active_viewers"]==0
    assert d.claim_browser_open() is True, "Closed tab must cause next job to reopen dashboard"
    assert d.claim_browser_open() is False, "Concurrent job must not spawn second tab"

    args=SimpleNamespace(title="Singleton test",stage="TEST",target="local",
                         codespace=d.DEFAULT_CS,command="Write-Output hello")
    with tempfile.TemporaryDirectory() as td:
        base=Path(td)
        with patch.object(d,"RUNS",base/"runs"),patch.object(d,"CURRENT",base/"current.json"):
            with patch.object(d,"spawn_detached",return_value=1234),patch.object(d,"ensure_server"):
                with patch.object(d,"claim_browser_open",return_value=False),patch.object(d.webbrowser,"open") as opened:
                    d.run_task(args)
                    assert opened.call_count==0, "Active tab: no browser.open"
                with patch.object(d,"claim_browser_open",return_value=True),patch.object(d.webbrowser,"open",return_value=True) as opened:
                    d.run_task(args)
                    assert opened.call_count==1, "Missing tab: exactly one browser.open"

    assert "/api/browser-heartbeat" in d.PAGE, "Browser must emit heartbeat"
    assert "/api/browser-close" in d.PAGE, "Browser must signal tab close"
    print("DASHBOARD_BROWSER_LIFECYCLE_PASS")
finally:
    server.shutdown()
    server.server_close()
    d.PORT=original_port
