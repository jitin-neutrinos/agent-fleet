#!/usr/bin/env python3
"""Assert-based health check for a Hermes memory + context stack.

Read-only: opens every store `mode=ro`, touches no config, writes nothing.
Exit 0 when green, 1 on any FAIL, so it doubles as a regression gate.

Adapt the store paths at the top when $HERMES_HOME is a profile dir, and extend
the assertion list when auditing a subsystem this does not cover. Failures print
the measured value, not just the name, so the output stands as evidence.

    python3 check-memory-context.py
"""
import os
import re
import sqlite3
import subprocess
import sys
import time

H = os.path.expanduser(os.environ.get("HERMES_HOME", "~/.hermes"))
FACTS = os.path.join(H, "memory_store.db")
STATE = os.path.join(H, "state.db")
MEMDIR = os.path.join(H, "memories")

R = []


def ck(name, ok, detail=""):
    R.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


print("A. Files exist before concluding anything is missing")
for p in (STATE, FACTS, os.path.join(MEMDIR, "MEMORY.md"), os.path.join(MEMDIR, "USER.md")):
    ck(f"exists {os.path.basename(p)}", os.path.exists(p), p)
if not all(os.path.exists(p) for p in (STATE, FACTS)):
    print("  (store missing — remaining checks skipped)")
    sys.exit(1)

print("B. state.db integrity + growth")
c = ro(STATE)
q = lambda s, *a: c.execute(s, a).fetchall()
ck("integrity ok", q("pragma integrity_check")[0][0] == "ok", q("pragma integrity_check")[0][0])
msgs = q("select count(*) from messages")[0][0]
mb = os.path.getsize(STATE) / 1048576
span = (q("select max(timestamp) from messages")[0][0]
        - q("select min(timestamp) from messages")[0][0]) / 86400
per_day = msgs / max(span, 1)
comp = q("select count(*) from messages where _compressed_summary=1")[0][0]
ck("compression has fired", comp > 0, f"{comp} summarised rows")
ck("auto_vacuum enabled", q("pragma auto_vacuum")[0][0] != 0,
   f"auto_vacuum={q('pragma auto_vacuum')[0][0]} (0 = file only ever grows)")
print(f"       growth: {mb:.0f} MB, {msgs} msgs, {per_day:.0f}/day -> ~{mb/max(span,1)*365/1024:.1f} GB/yr")
t0 = time.perf_counter()
q("select count(*) from messages_fts where messages_fts match 'compression'")
ck("FTS answers a MATCH", True, f"{(time.perf_counter()-t0)*1000:.1f}ms")

print("C. Memory budget: configured limit AND code default")
CODE_DEFAULT = {"MEMORY.md": 2200, "USER.md": 1375}
try:
    import yaml
    cfg = yaml.safe_load(open(os.path.join(H, "config.yaml"))) or {}
    mem = cfg.get("memory") or {}
except Exception:
    mem, cfg = {}, {}
for name, key in (("MEMORY.md", "memory_char_limit"), ("USER.md", "user_char_limit")):
    p = os.path.join(MEMDIR, name)
    if not os.path.exists(p):
        continue
    txt = open(p).read()
    lim_cfg = mem.get(key) or 0
    lim_code = CODE_DEFAULT[name]
    ck(f"{name} under configured limit", not lim_cfg or len(txt) <= lim_cfg,
       f"{len(txt)}/{lim_cfg}" if lim_cfg else f"{len(txt)} (no config limit)")
    ck(f"{name} under code default", len(txt) <= lim_code, f"{len(txt)}/{lim_code}")
    ck(f"{name} has consolidation headroom", len(txt) < 0.95 * lim_cfg if lim_cfg else True,
       f"{100*len(txt)/lim_cfg:.0f}% full" if lim_cfg else "n/a")

print("D. Fact store: distributions, provenance, truncation")
f = ro(FACTS)
fq = lambda s, *a: f.execute(s, a).fetchall()
total = fq("select count(*) from facts")[0][0]
if total:
    ck("trust scoring has run", fq("select count(distinct trust_score) from facts")[0][0] > 1,
       f"{fq('select count(distinct trust_score) from facts')[0][0]} distinct value(s)")
    ck("retrieval_count is written", fq("select coalesce(sum(retrieval_count),0) from facts")[0][0] > 0,
       f"sum={fq('select coalesce(sum(retrieval_count),0) from facts')[0][0]}")
    # timestamps are TEXT — strftime(...,'unixepoch') returns NULL on them
    nulls = fq("select count(*) from facts where created_at is null")[0][0]
    ck("facts carry created_at", nulls == 0, f"{nulls} null of {total}")
    months = fq("select count(distinct strftime('%Y-%m', created_at)) from facts")[0][0]
    ck("created_at is groupable as TEXT", months > 0, f"{months} distinct month(s)")
    # envelope noise — infrastructure framing stored as remembered facts
    env = fq("""select count(*) from facts where content like 'Gateway message origin%'
                or content like '[OUT-OF-BAND%' or content like '[System:%'
                or content like '[Surface:%' or content like '[ASYNC DELEGATION%'""")[0][0]
    ck("no envelope framing stored as facts", env == 0, f"{env}/{total} ({100*env/total:.1f}%)")
    # fixed-length truncation residue + colliding prefixes
    n400 = fq("select count(*) from facts where length(content)=400")[0][0]
    ck("no fixed-length truncation residue", n400 / total < 0.10, f"{n400}/{total} at exactly 400")
    dup = fq("""select count(*) from (select substr(lower(trim(content)),1,70) k, count(*) n
               from facts group by k having n>1)""")[0][0]
    ck("no colliding content prefixes", dup == 0, f"{dup} prefix group(s) with >1 row")
    # entity coverage gates contradiction detection
    linked = fq("select count(distinct fact_id) from fact_entities")[0][0]
    ck("entity coverage supports contradiction detection", linked / total > 0.8,
       f"{linked}/{total} linked ({100*linked/total:.0f}%)")
    prov = fq("""select count(*) from facts where content like '%msg\\_%' escape '\\'
                or content like '%message_id%'""")[0][0]
    ck("facts carry provenance", prov > total * 0.5, f"{prov}/{total} name a source id")
    ck("no dangling entity links",
       fq("""select count(*) from fact_entities fe left join facts x on x.fact_id=fe.fact_id
            where x.fact_id is null""")[0][0] == 0)

failed = [n for n, ok in R if not ok]
print()
print(f"{len(R)-len(failed)}/{len(R)} passed")
if failed:
    print("FAILING: " + "; ".join(failed))
sys.exit(1 if failed else 0)