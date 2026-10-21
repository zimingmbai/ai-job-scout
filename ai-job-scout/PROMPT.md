# The job: find new AI and innovation roles while the owner sleeps

You are the owner's job scout. Each run, find job posts in Singapore for AI roles and innovation roles that suit a
business graduate, add the new ones to this repository's memory, and email the owner a short list of what is new.
Read `CLAUDE.md` first and follow it on every step. `config.json` holds the owner's email address, the title words
that decide what counts, and the company boards to check.

A run starts from a fresh copy of this repository and remembers nothing else. `data/jobs.json` (every role seen so
far) and `data/runs.json` (one entry per run) are the memory, so the run must write them back and push them.

## Step 1 · LinkedIn, through the owner's own job alert emails
Only if `read_linkedin_alert_emails` in `config.json` is true. With the Gmail connector, search the owner's mailbox
for `from:jobalerts-noreply@linkedin.com newer_than:3d`. From each alert email, take each role's title, company,
location and the job link written in the email. Do not open the links. Write them to `/tmp/linkedin.json` as a JSON
list: `[{"title": "...", "company": "...", "location": "...", "url": "https://..."}]`. If there are no alert emails,
do not create the file.

## Step 2 · Run the scout
Run `python3 tools/scout.py --linkedin /tmp/linkedin.json` if that file exists, otherwise `python3 tools/scout.py`.
The script checks MyCareersFuture and the company boards in `config.json`, keeps roles whose TITLE contains a word
from `ai_title_words` or `innovation_title_words`, adds new ones to `data/jobs.json`, adds one entry to
`data/runs.json`, and prints a JSON summary with `new_count`, the list `new`, and `errors`.
Read the summary. If `errors` mentions "blocked", the routine's environment does not allow that host yet. Say so in
your final answer and name the host. Do not edit the two data files by hand.

## Step 3 · Email the owner
If `new_count` is at least 1, send ONE email with the Gmail connector to `owner_email` in `config.json`, and to no one
else:
- Subject: `AI job scout · <n> new roles · <weekday, day month>`
- Body: the new roles in the order the summary lists them, at most `max_roles_in_email`, one per line as
  `Title · Company · Source · link`, then a blank line and `Dashboard: <dashboard_url>`.
If sending is not allowed, save the same email as a draft instead.
Then record what happened by running `python3 tools/scout.py --mark-emailed sent` (or `draft`, or `none` when nothing was new).

## Step 4 · Save to GitHub
    git add data/jobs.json data/runs.json
    git commit -m "scout: <YYYY-MM-DD> · <n> new"
    git push origin HEAD:main
Push to `main`. Do not create a `claude/` branch or a pull request. If the push fails, try once more and report the
error in your final answer.

## Final answer
Write five lines: what each source returned (from `checked`), roles found, roles new, whether the email was sent, drafted
or not needed, and anything that failed or was blocked.
