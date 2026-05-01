# backend/src/backend/style/

## Purpose
Writing-style learning package. Maintains an append-only corpus of the user's own writing (chat messages, saved insights, post edits) and periodically distils it into a concise **Style Profile** using an LLM. The profile is fed into every LinkedIn and blog post generation so the output converges on the user's voice over time.

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `collector.py` | `record_sample(session, source, text, source_ref)` — appends one piece of user writing to `style_samples`. Skips texts shorter than 20 chars. Called from `routes_chat.py` after every user message and insight save. |
| `profile.py` | `refresh_profile_if_stale(session, force=False)` — checks if sample count has grown ≥20% since last refresh; if so, sends last 80 samples to LiteLLM with `STYLE_DISTILL_PROMPT`, stores result in `style_profile` (singleton row). `get_profile_text(session)` — returns the current distilled Markdown guide. |

## Style Refresh Logic
```
Every chat turn → record_sample() → style_samples table grows
                                           │
                               count ≥ 1.2 × last_refresh_count?
                                    │ Yes
                                    ▼
                     LiteLLM → STYLE_DISTILL_SYSTEM/USER prompt
                     (last 80 samples → Markdown style guide)
                                    │
                              style_profile table (singleton id=1)
                                    │
                     Fed into next generate_linkedin_post() / generate_blog_post()
```

## Key Constants
- `_MIN_TEXT_LEN = 20` — texts shorter than 20 chars are skipped (e.g., single-word replies)
- `_REFRESH_GROWTH_RATIO = 1.20` — refresh when corpus is 20% larger than at last refresh
- `_MIN_SAMPLES_TO_PROFILE = 3` — don't generate a profile until at least 3 samples exist

## Last Session Changes
**Session date:** 2026-04-29

**Changes made:**
- Created this folder and all files (`__init__.py`, `collector.py`, `profile.py`)

**Reason:** Post Studio feature — needed a lightweight system to accumulate user writing samples and produce a stable style guide without blocking the request path.

**Outcome:** Working. The refresh runs asynchronously via `BackgroundTasks` so the user never waits. A future improvement could be to trigger a forced refresh from the frontend (e.g., a "Refresh style profile" button in settings).

**Watch out for:** The profile is a singleton (id=1 in `style_profile`). This is a single-user app design. If multi-user auth is added later, this table needs a `user_id` column and the upsert logic must change.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-04-29 | `__init__.py`, `collector.py`, `profile.py` | Initial creation — style corpus collection and LLM-distilled profile for Post Studio |
