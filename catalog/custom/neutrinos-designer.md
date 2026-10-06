---
slug: neutrinos-designer
title: Neutrinos Designer pack
kind: skill pack
summary: Seven-skill Neutrinos brand pack - brand core, documents, decks, print, social, web, and the handbook pipeline - with a one-command installer for every harness.
repo: jitin-neutrinos/neutrinos-designer
site: https://neutrinos-designer.jitinnair.com/
install: curl -fsSL https://neutrinos-designer.jitinnair.com/install.sh | bash
---

# Neutrinos Designer pack

A private skill pack that teaches every AI harness in the fleet the **Neutrinos brand system** —
colors, typography, logo rules, voice — and then applies it: documents, slide decks, print-ready
PDFs, social graphics and web UIs all ship on-brand without re-briefing.

## What is inside

| Skill | Use it for |
|---|---|
| `neutrinos-brand-core` | The brand system itself: hex values, Poppins, logo files, design principles, voice. Load first. |
| `neutrinos-documents` | Long-form documents — handbooks, playbooks, guides, SOPs, reports — as branded multi-page PDFs. |
| `neutrinos-handbook-pipeline` | End-to-end pipeline for long branded PDF handbooks: research with citations, branded HTML, render, verify. |
| `neutrinos-presentations` | Pitch decks, sales decks, webinar and QBR decks as PPTX or HTML slides. |
| `neutrinos-print` | Print-ready media — brochures, flyers, posters, business cards, letterhead, banners. |
| `neutrinos-social` | Correctly-sized social and ad graphics — LinkedIn, Facebook, covers, avatars, email signatures. |
| `neutrinos-web` | On-brand websites, landing pages and dashboards in HTML/CSS/JS or React. |

## Install

One command, every detected harness on the machine:

```bash
curl -fsSL https://neutrinos-designer.jitinnair.com/install.sh | bash
```

The TUI installer finds each harness (Hermes, Claude Code, OpenCode, Antigravity, and project-level
installs), shows what it will touch, and reports honestly what it skipped. Re-running is the repair
path; removal is `uninstall.sh` from the same host.

## Updates

The pack lives in the private repo `jitin-neutrinos/neutrinos-designer` and is versioned with tags
(current line: v1.4.x). The installer always serves the tagged release from
[neutrinos-designer.jitinnair.com](https://neutrinos-designer.jitinnair.com/).
