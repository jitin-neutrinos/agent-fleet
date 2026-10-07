#!/usr/bin/env node
// ws-liveness-probe.mjs — is the WebSocket PATH healthy, or is the client broken?
//
// Hand-rolled RFC 6455 client that completes the upgrade, answers every server
// ping with a pong, and reports what arrived. Run it against BOTH endpoints:
//
//   node scripts/ws-liveness-probe.mjs                    # 127.0.0.1:3011 (proxy)
//   node scripts/ws-liveness-probe.mjs astra.jitinnair.com  # through CF tunnel
//
// INTERPRETATION
//   local survives + tunnel survives  -> proxy, relay and CF edge are HEALTHY.
//                                        The churn is entirely client-side; stop
//                                        editing server code.
//   local survives + tunnel dies      -> the edge/tunnel is dropping it (cache
//                                        rules, idle timeout, NAT).
//   local dies too                    -> the proxy itself is reaping a healthy
//                                        leg: check the ping/reap interval order.
//
// A survive-and-pong run prints `pingsIn=N` with N matching the elapsed seconds
// divided by the server ping round (~30s). Zero pings means the ping loop never
// ran for this socket.
//
// Env: ASTRA_WEBUI_PASSWORD (required), ASTRA_WEBUI_PORT (default 3011).

import { request } from "node:http";
import https from "node:https";
import net from "node:net";
import crypto from "node:crypto";

const password = process.env.ASTRA_WEBUI_PASSWORD;
if (!password) {
  console.error("ASTRA_WEBUI_PASSWORD not set");
  process.exit(1);
}

const PORT = Number(process.env.ASTRA_WEBUI_PORT || 3011);
const HOLD_MS = Number(process.env.PROBE_HOLD_MS || 115_000);
const target = process.argv[2] || null; // null = local; hostname = via tunnel

function login() {
  return new Promise((resolve, reject) => {
    const req = request({
      hostname: "127.0.0.1", port: PORT, path: "/api/login", method: "POST",
      headers: { "Content-Type": "application/json" },
    }, res => {
      const c = (res.headers["set-cookie"] || []).find(x => x.startsWith("astra_session="));
      res.resume();
      if (!c) return reject(new Error("no astra_session cookie (wrong password?)"));
      resolve(c.split(";")[0]);
    });
    req.on("error", reject);
    req.write(JSON.stringify({ password }));
    req.end();
  });
}

function encodeFrame(payload, opcode) {
  const p = Buffer.from(payload);
  const mask = crypto.randomBytes(4);
  const frame = Buffer.alloc(2 + 4 + p.length);
  frame[0] = 0x80 | opcode;
  frame[1] = 0x80 | p.length; // client frames MUST be masked (RFC 6455 §5.3)
  mask.copy(frame, 2);
  for (let i = 0; i < p.length; i++) frame[6 + i] = p[i] ^ mask[i % 4];
  return frame;
}

function run(sock, head, label) {
  const started = Date.now();
  let buf = Buffer.alloc(0);
  let pingsIn = 0, totalIn = 0, closed = false;

  function parse(chunk) {
    buf = Buffer.concat([buf, chunk]);
    while (buf.length >= 2) {
      const opcode = buf[0] & 0x0f;
      const masked = (buf[1] & 0x80) !== 0;
      let len = buf[1] & 0x7f, off = 2;
      if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
      else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
      if (masked) off += 4;
      if (buf.length < off + len) return;
      const payload = buf.subarray(off, off + len);
      buf = buf.subarray(off + len);
      const t = ((Date.now() - started) / 1000).toFixed(1);
      totalIn++;
      if (opcode === 0x9) { pingsIn++; console.log(`[${t}s] PING -> PONG`); sock.write(encodeFrame(payload, 0xa)); }
      else if (opcode === 0xa) console.log(`[${t}s] PONG`);
      else if (opcode === 0x8) console.log(`[${t}s] CLOSE frame from server`);
      else console.log(`[${t}s] text len=${len} :: ${payload.toString().slice(0, 90)}`);
    }
  }

  if (head && head.length) parse(head);
  sock.on("data", parse);
  sock.on("close", () => {
    closed = true;
    console.log(`CLOSED after ${((Date.now() - started) / 1000).toFixed(1)}s; pingsIn=${pingsIn} totalIn=${totalIn}`);
  });
  sock.on("error", e => console.log("ERR", e.message));

  setTimeout(() => {
    const secs = ((Date.now() - started) / 1000).toFixed(1);
    const verdict = (!closed && pingsIn > 0) ? "HEALTHY" : (closed ? "DROPPED" : "SILENT");
    console.log(`--- ${label}: ${verdict} after ${secs}s pingsIn=${pingsIn} totalIn=${totalIn} ---`);
    process.exit(verdict === "HEALTHY" ? 0 : 1);
  }, HOLD_MS);
}

const cookie = await login();
const key = crypto.randomBytes(16).toString("base64");
const headers = {
  "Connection": "Upgrade", "Upgrade": "websocket",
  "Sec-WebSocket-Key": key, "Sec-WebSocket-Version": "13",
  "Cookie": cookie,
};

if (!target) {
  console.log(`probing LOCAL 127.0.0.1:${PORT}/api/hx/ws …`);
  const sock = net.connect(PORT, "127.0.0.1", () => {
    sock.write(
      `GET /api/hx/ws HTTP/1.1\r\nHost: 127.0.0.1:${PORT}\r\n` +
      Object.entries(headers).map(([k, v]) => `${k}: ${v}`).join("\r\n") + "\r\n\r\n"
    );
  });
  let handshakeDone = false;
  let acc = Buffer.alloc(0);
  sock.on("data", chunk => {
    if (handshakeDone) return; // run() takes over via the listener below
    acc = Buffer.concat([acc, chunk]);
    const idx = acc.indexOf("\r\n\r\n");
    if (idx === -1) return;
    console.log("HANDSHAKE:", acc.subarray(0, idx).toString().split("\r\n")[0]);
    handshakeDone = true;
    sock.removeAllListeners("data");
    run(sock, acc.subarray(idx + 4), "local");
  });
} else {
  console.log(`probing TUNNEL ${target}/api/hx/ws …`);
  const req = https.request({ host: target, port: 443, path: "/api/hx/ws", method: "GET", headers });
  req.on("upgrade", (res, socket, head) => {
    console.log("UPGRADE:", res.statusCode);
    run(socket, head, "tunnel");
  });
  req.on("response", res => {
    console.log(`RESPONSE (no upgrade): ${res.statusCode} — is the session cookie valid for this host?`);
    process.exit(1);
  });
  req.end();
}
