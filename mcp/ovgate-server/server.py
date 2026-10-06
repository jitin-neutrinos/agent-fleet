#!/usr/bin/env python3
"""ovgate server — filtering reverse proxy: 127.0.0.1:1934 -> OpenViking 127.0.0.1:1933.

MCP streamable-HTTP aware: buffers the JSON body of /mcp POSTs, inspects
tools/call payloads, applies the Laya memory gate, forwards upstream with the
original session headers, streams the response back.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import gate_call  # noqa: E402

UPSTREAM = os.environ.get("OV_UPSTREAM", "http://127.0.0.1:1933")
HOP_HEADERS = {"connection", "keep-alive", "transfer-encoding", "content-length", "host"}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _forward(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""

        # MCP gate: inspect tools/call on /mcp
        if self.path.rstrip("/").endswith("/mcp") and raw:
            try:
                payload = json.loads(raw)
                if payload.get("method") == "tools/call":
                    params = payload.get("params", {})
                    tool = str((params.get("name") or "")).lower()
                    args = params.get("arguments") or {}
                    allowed, reason = gate_call(tool, args)
                    if not allowed:
                        deny = json.dumps({
                            "jsonrpc": "2.0", "id": payload.get("id"),
                            "result": {"content": [{"type": "text", "text": reason}],
                                       "isError": True},
                        }).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/event-stream")
                        self.send_header("Content-Length", str(len(deny)))
                        self.end_headers()
                        self.wfile.write(deny)
                        return
            except Exception:
                pass  # never break the stream on a gate bug

        req = urllib.request.Request(UPSTREAM + self.path, data=raw if raw else None,
                                     method=self.command)
        for k, v in self.headers.items():
            if k.lower() not in HOP_HEADERS:
                req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = r.read()
                self.send_response(r.status)
                ct = r.headers.get("Content-Type", "application/json")
                self.send_header("Content-Type", ct)
                if "text/event-stream" in ct:
                    self.send_header("Cache-Control", "no-cache")
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
            self.send_response(502)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        self._forward()

    def do_GET(self):
        self._forward()

    def do_DELETE(self):
        self._forward()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("OVGATE_PORT", "1934"))
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
