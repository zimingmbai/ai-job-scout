# AI job scout

Every morning at 6:07 AM Singapore time, while you are still asleep, this Claude routine looks for new AI and
innovation roles in Singapore, keeps every role it has seen in `data/jobs.json`, writes one line about each run in
`data/runs.json`, pushes both files to this repository, and emails you the roles that are new. `index.html` shows
them as a dashboard.

MGMT 6110 · Week 8 AI in Action Studio. The full step-by-step guide, with pictures, is on eLearn.

## What is in this repository

| File | What it is |
|---|---|
| `PROMPT.md` | The routine's job, step by step. The routine reads it at the start of every run. |
| `CLAUDE.md` | The house rules for every run, including what the scout must never do. |
| `config.json` | Your email address, your dashboard address, the title words that decide what counts, the company boards. |
| `tools/scout.py` | The script the routine runs to check the sources and update the memory files. |
| `data/jobs.json` | Every role seen so far. This file is the scout's memory from one run to the next. |
| `data/runs.json` | A record of the runs, with one entry per run. |
| `data/manual_roles.json` | Roles you add by hand, for example from a career fair. This file is optional. |
| `index.html` | The dashboard. |

## Set-up values for the routine

| Field | Value |
|---|---|
| Name | `AI job scout` |
| Instructions | `Read PROMPT.md and CLAUDE.md in this repository and do the job in PROMPT.md. Push your changes to main.` |
| Repository | your copy of `ai-job-scout` |
| Environment | Network access **Custom**, allowed domains `api.mycareersfuture.gov.sg`, `boards-api.greenhouse.io`, `api.lever.co`, and tick **Also include default list of common package managers** |
| Trigger | Schedule, daily, 6:07 AM |
| Connectors | Gmail only. Remove every other connector. |

## Where the roles come from

- **MyCareersFuture**, Singapore's national jobs portal.
- **Company job boards** that the companies publish for job sites (Greenhouse and Lever). Add or remove companies in
  `config.json`.
- **LinkedIn**, only through your own LinkedIn job alert emails, read with the Gmail connector. The scout never visits
  linkedin.com, because LinkedIn's User Agreement forbids bots and scraping.

## Before you act on a role

Open the post yourself. The scout keeps a role when its title contains one of your words; it does not read the
description and it cannot tell you whether the role suits you.
