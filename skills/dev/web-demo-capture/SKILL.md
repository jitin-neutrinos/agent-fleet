---
name: web-demo-capture
description: "Use when recording browser demos or web screenshots."
version: 1.0.0
author: hermes-curator
license: internal
metadata:
  hermes:
    tags: [recording, demo, pagecast, playwright, ffmpeg]
    related_skills: [demo-recorder]
---

# Web demo capture (browser recordings + stills)

## When to Use
Use when the task is producing demo media of a web app: a screen-recorded walkthrough (video/GIF), theme or state screenshots, loop GIFs, or product-portfolio capture. Triggers: "record a demo", "make a gif of the app", "screen recording for the portfolio/docs page", "screenshot each theme".

Class skill for polished demo assets of a web app: narrative screen recordings with a human-like cursor, GIFs, MP4s, and themed stills. Primary tool is the pagecast MCP (record_page / interact_page / stop_recording / convert_to_gif / convert_to_mp4); Playwright from the pagecast fork covers stills and state manipulation. The demo-recorder skill documents the MCP itself; this skill carries the capture WORKFLOW that survives contact with real apps.

## Always-on rules

- **Recon every selector in the app's source before recording.** Grep for input ids, `aria-label`s, section/class names, and nav button text (Playwright selectors support `:has-text()`). A guessed selector burns a 30s per-action timeout, and 3 rejected MCP calls in a row trip a ~48s circuit breaker mid-recording — the take keeps rolling through all of it.
- **Never block a recording take waiting on server-side AI work.** If the demo subject is an agent composing a real answer, split takes: take 1 records the setup (login, typing the prompt, a short beat), poll the app's API from outside for completion (look for a sessions/turn-state field flipping true→false), take 2 records the tour of the finished result, merge in ffmpeg. `interact_page` actions cap at 30s; an agent turn runs minutes.
- **A turn that looks finished may be parked on an approval gate.** Agent demos pause mid-turn on shell-command approval cards; approve via the app's gate API so the deliverable completes, then verify the actual artifact (message count / reply payload contains the rendered output) before starting the tour take. From the outside, a gated turn and a finished turn look identical.
- **Frame-verify every take before converting.** Extract one probe frame per story beat (`ffmpeg -y -ss <t> -i take.webm -frames:v 1 probe.png`) and vision-check them. File size and duration look healthy even when the take sat on the wrong app state for minutes.
- **Credentials never appear on camera in clear text.** Confirm on a probe frame that password inputs render as bullets. Read the password from the app's env/service config; never type it in chat or commit it anywhere.
- **Don't send raw file paths to the user — deliver assets as MEDIA attachments** (this user has said so explicitly for media deliverables).
- Story pacing: 1–2s waits between actions; GIFs 10–15 fps, 640–800px wide; keep individual GIFs short — split long demos into multiple assets.

## Procedures

Recipes with concrete commands live in `references/recipes.md`: headless auth via storage-state JSON (no human login), theme/screenshot loops through the fork's Playwright, ffmpeg merge/fade patterns, and the polling pattern for long agent turns.
