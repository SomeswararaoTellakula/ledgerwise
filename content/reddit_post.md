# Reddit link post

**Subreddit:** r/aiagents (fallbacks: r/LLMDevs, r/SideProject, r/aimemory)
**Post type:** Link post → paste the article URL

**Title:**
I built an accounts-payable agent that learns vendor quirks from past decisions — and refuses to act on memory when it shouldn't

**If the sub asks for a body / first comment:**
Ledgerwise sits after a 3-way invoice match. For each exception it recalls how the same vendor's same exception was resolved before (Hindsight memory), auto-resolves only with 2+ consistent human precedents inside the amount range humans approved, and escalates otherwise. Bank-account changes always go to a human, and the agent never counts its own decisions as precedent. On an 8-week replay it goes from 0% to 60–100% auto-resolution from week 3 with zero calls the AP lead would overturn. Code: https://github.com/SomeswararaoTellakula/ledgerwise — happy to answer questions about the policy design.
