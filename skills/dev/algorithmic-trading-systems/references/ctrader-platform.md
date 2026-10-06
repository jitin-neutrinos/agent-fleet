# cTrader as an automation target

Verified on kurama-core (Nobara 44, x86_64) against the official Docker image.
Re-verify version-gated claims before relying on them; the platform ships fast.

## Automation surfaces (three, pick deliberately)

| Surface | Runs where | Use when |
|---|---|---|
| cBots (in cTrader Algo) | inside the platform: desktop, cloud, or headless CLI | you want in-platform charting, indicators, backtester |
| Open API | external app, sockets to broker backend | you want trading OUTSIDE cTrader, or bulk data pulls |
| MCP servers (local/remote) | AI agent talks to cTrader in natural language | you are the agent; ad-hoc ops and research, not the bot |

Spotware renamed "cTrader Automate" to "cTrader Algo". API version was 5.9 with
5.10 in alpha when checked. Python cBots are first-class (CPython via a .NET
bridge, not IronPython) — but the engine is .NET/C#, so customisable parameters
must be declared in a companion generated `.cs` file. Docs:
`help.ctrader.com/ctrader-algo`.

## Linux: no blocker

The desktop GUI is Windows/macOS only — every "install cTrader on Linux with
Wine" guide found was third-party SEO content with no official backing. That
does NOT block automation. Spotware publishes an official headless image:

    ghcr.io/spotware/ctrader-console:<version>

It carries `ctrader-cli`, the .NET runtime AND SDK, reference packs, Python
3.12 with `ash`, and the out-of-process algo host. Multi-arch amd64/arm64.
Inside the container the CLI is invoked as `dotnet /app/ctrader-cli.dll ...` —
there is no `ctrader-cli` on PATH, so scripts that call it bare will fail with
`command not found` even though the CLI works.

This image builds, backtests, optimises and runs live. Official CI recipes
(GitHub Actions, Kubernetes CronJob) exist. `--exit-on-stop` is required for
container use.

## VERIFIED: Python dependencies do NOT get bundled by the CLI/Docker build

This is the finding that changes architecture, and it contradicts the docs.

Test: a Python cBot with `requirements.txt` containing `numpy==2.3.4` and
`onnxruntime==1.23.0`, built with `dotnet build MLProbe.csproj -c Release`
inside the official image.

- Build **succeeds** (0 errors) and emits a `.algo`.
- `EmbeddedResources.manifest.json` lists only the Python *source* files:
  `{"PythonFiles":["http_requests.py","MLProbe_main.py","robot_wrapper.py"]}`
- Output directory: 284K. No site-packages, no numpy, no onnxruntime, no `.so`.
- The image ships pip 25.0.1, but nothing in the build invokes it.

So the help-centre claim that "pandas and numpy are resolved automatically when
you build your project" holds for the desktop/cloud builder, not for the
headless CLI/Docker path. A green build proves compilation, never packaging.

**Consequence:** do not plan to run a trained model in-process inside the cBot.
Keep the bot a thin deterministic executor and the model in a separate process.

## Build-path gotchas (each one cost a probe cycle)

- `requirements.txt` belongs at the **project root**, as a sibling of the
  `.csproj`. Placing it one level deeper fails with
  `error CT0001: Could not find file '<project>/requirements.txt'`.
- Writing inside a host bind mount creates root-owned files the host user
  cannot then edit or delete, and there is no passwordless sudo to fix it.
  Copy the project to a container-local path (`cp -r /src/. /root/cAlgo/...`)
  and write there. Mount sources read-only.
- Scaffold commands may demand a cTrader login even for purely local work.
  Hand-author the project files from a known-good sample instead.

## Cloud has limits that matter for a model layer

- Cloud cBots **cannot make outbound HTTP/API calls**, so a cloud bot can never
  reach a locally-hosted model or LLM. Self-hosted CLI/Docker is required for
  that architecture. (Vendor-stated, twice-stated — verify if it is decisive.)
- Cloud is free but capped: 1 concurrent instance on demo, up to 10 on live,
  varying by broker. Newer versions add a per-account concurrency cap and can
  auto-stop instances whose account does not meet a trading-activity
  requirement.
- On **Linux there is no algo sandbox** — `--full-access` is a real gate only
  on Windows; omitting it on Linux prints a warning and delays start. Run your
  own algo in an isolated container (no host mounts, no host network, dropped
  caps).

## Open API maintenance state (research it before depending on it)

- The official Python SDK `ctrader-open-api` (0.9.2) had not been pushed since
  2024; 0.9.3 was yanked on PyPI. Open protobuf-deserialisation complaints
  exist against it.
- The most actively pushed community option was `ctrader-api-client`
  (anyio-based, v0.11.0) but it requires Python >= 3.12 and was very low
  adoption — its own README calls it early development.
- There is no documented Open API v3/v4; versioning moved to numeric payload
  tags. Open API v1 was withdrawn years ago.
- Rate limits: 50 req/s non-historical, 5 req/s historical, per connection.
  Trendbar requests hard-cap at 14,000 bars, so multi-year pulls must be
  chunked with gap detection. Tick responses silently truncate at an
  unpublished backend limit — never assume you got everything.
- Python SDK is TCP only, no WebSocket. Ports 5035 (protobuf) / 5036 (JSON).
- The Python SDK is fine for market-data pipelines and dashboards; prefer a
  cBot for the execution loop.

## Backtester and optimiser

- Data modes: server ticks (most accurate), server M1, M1 from CSV, server H1.
  Spread can be Fixed or a Random min/max band — use the Random band for gold,
  a single spread number hides the cost of a bad fill.
- Recent versions fixed equity-curve and margin/stop-out realism, so pre-fix
  backtests understate risk. Re-run old results.
- Optimiser offers Exhaustive / Grid / Genetic only. **No walk-forward, no
  out-of-sample split.** Implement it yourself over disjoint windows or via a
  custom fitness function.
- Backtesting cannot simulate latency — entry is the server tick time.
- Machine-readable output: per-run folders with Events (JSON), Log (TXT),
  Parameters (.cbotset), Report (HTML), plus `--report-json`. Feed this
  directly into a research pipeline.
- Backtest output is available on the CLI too, so the GUI-only restriction does
  not apply to automation.

## Symbol, size and account gotchas

- Symbol naming is broker-specific: `XAUUSD`, `XAUUSD.m` (micro), `XAUUSD.c`
  (cent), `XAUUSD.raw`, and legacy `GOLD`. Contract size differs per variant,
  so the same "1.0 lot" can move 1 ounce or 100. In cTrader an asset and a
  symbol are different objects — `GOLD` appears in the asset list, not the
  symbol list.
- On gold-type instruments a pip is commonly a $0.01 price move with a
  100-unit contract, so naive FX pip logic is wrong by 100×. Read the venue's
  own `PipSize`/contract size at runtime.
- Minimum tradable volume is broker-controlled and can differ between cTrader
  and MT4/MT5 at the same broker.
- **Account mode decides whether hedging is possible.** On a netting account an
  opposite-side order closes or partially closes rather than opening a second
  position. A swing bot wanting both sides needs a hedged account.
- Dynamic leverage tiers: margin is computed per tier and summed; leverage
  falls as exposure grows.
- Swap is charged at broker server-time rollover, commonly triple-charged on
  Wednesday for weekend value dates.
- Trailing stops come in two flavours: server-side (needs broker support,
  survives the bot stopping) and client-side (lives in the bot, dies with it).
  Know which one your logic depends on across restarts.

## CLI auth has two non-interchangeable conventions

Mixing them fails immediately:

- Batch commands (`accounts`, `symbols`, `metadata`, `run`, `backtest`,
  `optimize`) take `--pwd-file` and **reject** `--password`.
- Interactive commands (`orders`, `positions`, `price`, `candles`,
  `indicators`, `alerts`, `account-stats`) take `--password` with `-q` and
  **reject** `--pwd-file`.
- cBot parameter names from the environment are case-sensitive; run
  `metadata <file>` and match the `.algo` declaration exactly.

Never put the password on the command line; it lives in a plaintext file that
must be `chmod 600`, mounted read-only, kept out of version control and out of
image layers.

## Events and unattended operation

- `on_tick` fires per tick and is CPU-heavy; the bar-close hook is the right
  level for a swing strategy.
- Crashed cBots are restarted automatically; `OnException` lets you define
  behaviour.
- Network access, WebSockets and SMTP notifications are available to algos —
  so a swing bot can push state out to your own services when self-hosted.
- Several API members silently degrade under CLI: `MessageBox` returns None,
  window methods are ignored, `PlaySound` does nothing, chart screenshots
  return null.
- Verify early whether `LoadMoreHistory()` works inside backtesting on your
  version. Long-standing reports say it does not, and the documented workaround
  is to start the backtest earlier and gate logic on a start-date check. This
  matters a lot for multi-timeframe swing logic needing long warmup.