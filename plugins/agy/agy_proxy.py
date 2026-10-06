#!/usr/bin/env python3
"""Local header-injector: agy -> 8016 -> (adds Authorization) -> laya-mcp 8015."""
import os, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = 'laya_-rXctm3rQLEKieWsL_8kMHHSCx2tZaPX'
UPSTREAM = "http://127.0.0.1:8015"

class H(BaseHTTPRequestHandler):
    def _proxy(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(UPSTREAM + self.path, data=body, method=self.command)
        for k, v in self.headers.items():
            if k.lower() in ("host", "authorization", "content-length"):
                continue
            req.add_header(k, v)
        req.add_header("Authorization", f"Bearer {TOKEN}")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                self.send_response(r.status)
                self.send_header("Content-Type", r.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            data = e.read()
            self.send_response(e.code)
            self.send_header("Content-Type", e.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(502); self.end_headers()

    def do_POST(self): self._proxy()
    def do_GET(self): self._proxy()
    def do_DELETE(self): self._proxy()
    def log_message(self, *a): pass

if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8016), H).serve_forever()
