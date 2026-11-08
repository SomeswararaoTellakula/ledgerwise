# Submission plan — deadline Mon 9 Nov 2026, 11:59 PM IST

Only ONE final submission per team. Every team member fills the profile form.

## Order of work (≈ 4–5 hours)

| # | Do this | Time | Notes |
|---|---|---|---|
| 1 | Profile Review Form — every member | 5 min | https://forms.gle/BGcky3M6Nw1pBEPw6 (skip if done). Mandatory: teams aren't reviewed without it. |
| 2 | Install **Band AI desktop** | 5 min | Required by the problem statement: https://www.band.ai |
| 3 | Push repo to GitHub as **public** `ledgerwise` | 10 min | `git init && git add . && git commit -m "Ledgerwise" && gh repo create ledgerwise --public --source . --push` |
| 4 | Hindsight Cloud account → add promo **MEMHACK99** in Billing → copy API URL + key into `.env` | 10 min | Then `python app.py` and confirm the badge says `Hindsight · ledgerwise-ap-…` |
| 5 | Run `python scripts/replay.py` on Hindsight; if numbers differ from README, update the table | 10 min | Re-take `docs/screenshots/*` from the live Hindsight run (badge visible) |
| 6 | Record video (script in `video_script.md`) → YouTube **public**, Nano Banana thumbnail | 60 min | 2–5 min, 1080p, screen + face cam preferred |
| 7 | Publish article (`article.md`) on Medium or Dev.to — **public** | 30 min | Upload the 4 images; check the 3 Hindsight links render; tag Code.in |
| 8 | LinkedIn post (`linkedin_post.md`) → comment 1: article URL, comment 2: Hindsight repo | 10 min | Repo link must be in the main post (it is) |
| 9 | Reddit link post (`reddit_post.md`) on r/aiagents | 5 min | |
| 10 | Each teammate: own article + own LinkedIn post (different angle) | — | Angles: the guardrails / the GST + duplicate quirks / the UI & recall trace |
| 11 | Fill the final form (answers below) — team lead only | 5 min | https://forms.gle/7eSw5Dz2oT2MhymX7 |

**Never write "hackathon"** in the article, post, hashtags or video title — that's a disqualification rule.

## Final submission form — answers

| Field | Answer |
|---|---|
| Email ID | someshtellakula@gmail.com |
| Phone Number | *(yours)* |
| Team Name | *(exactly as registered)* |
| Team Members | Someswara Rao Tellakula, *(others)* |
| GitHub Repository | https://github.com/SomeswararaoTellakula/ledgerwise |
| Social Media Post on LinkedIn | *(post URL)* |
| Article link | *(Medium/Dev.to URL)* |
| Video Link | *(YouTube URL)* |
| Reddit Post Link | *(Reddit URL)* |
| Feedback | The problem statement's "make memory the star" and before/after framing made scoping easy, and the content prompts saved real time. Two improvements: publish the Hindsight Cloud API URL format in the brief (it took a minute to find), and give a sample judged demo so teams can calibrate depth. |

## Live demo to judges — 60-second version
1. "Every AP desk answers the same invoice questions monthly. Matching flags them; nobody remembers the answers."
2. Memory OFF → Run all → flat 0%.
3. Memory ON → decide 2 invoices with reasons → Run to week 4 → 75%, open a Kaveri card: auto-reject citing my 2 earlier rejections + drafted email.
4. Week 5 Tata +3.1% escalates ("outside learned range, leaning approve"). Week 6 bank change held regardless of history.
5. Brief → Hindsight reflect. "Zero automatic calls the AP lead would overturn."

Likely judge questions:
- *Why not just rules?* The rules aren't known upfront — clause 7.2, the ₹2,500 Ops agreement, Nilgiri's short trucks are learned from decisions, not configured.
- *What if a human makes a mistake?* Disagreement in the last 3 decisions resets to escalation; a single decision is never enough.
- *Why parse a structured line instead of trusting extracted facts?* The policy compares exact amounts; `include_chunks=True` returns the source so numbers survive extraction, while the prose powers reflect.
- *Scale?* One bank per AP desk/entity; recall is per vendor + exception type, so cost is per exception, not per invoice.
