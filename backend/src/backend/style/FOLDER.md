# backend/src/backend/style/

## Purpose
Writing-style learning package. Maintains an append-only corpus of the user's own writing (chat messages, saved insights, post edits) and periodically distils it into a concise **Style Profile** using an LLM. The profile is fed into every LinkedIn and blog post generation so the output converges on the user's voice over time.

## Files
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `collector.py` | `record_sample(session, source, text, source_ref)` — appends one piece of user writing to `style_samples`. Skips texts shorter than 20 chars. Called from `routes_chat.py` after every user message and insight save. |
| `profile.py` | `refresh_profile_if_stale(session, force=False)` — checks if sample count has grown ≥5% since last refresh; if so, sends last 80 samples to LiteLLM with `STYLE_DISTILL_PROMPT`, stores result in `style_profile` (singleton row). `get_profile_text(session)` — returns the current distilled Markdown guide. |

## Style Refresh Logic
```
Every chat turn → record_sample() → style_samples table grows
                                           │
                               count ≥ 1.05 × last_refresh_count?
                                    │ Yes
                                    ▼
                     LiteLLM → STYLE_DISTILL_SYSTEM/USER prompt
                     (last 80 samples → Markdown style guide)
                                    │
                              style_profile table (singleton id=1)
                                    │
                     Fed into next generate_linkedin_post() / generate_blog_post()
                     via _load_context() in routes_posts.py (background refresh after generation)
```

## Key Constants
- `_MIN_TEXT_LEN = 20` — texts shorter than 20 chars are skipped (e.g., single-word replies)
- `_REFRESH_GROWTH_RATIO = 1.05` — refresh when corpus is 5% larger than at last refresh (was 1.20)
- `_MIN_SAMPLES_TO_PROFILE = 3` — don't generate a profile until at least 3 samples exist

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `profile.py` — changed `_REFRESH_GROWTH_RATIO` from `1.20` (20% growth) to `1.05` (5% growth) so the style profile stays more current as the user chats.

**Reason:** With 1.20, the profile would barely refresh in normal usage — a user would need to send many messages before the profile updated. At 1.05, any small burst of activity triggers a refresh, keeping the voice model accurate.

**Outcome:** Profile refreshes much more frequently. The refresh itself runs as a background task (not on the hot path) so it doesn't add latency to post generation.

**Watch out for:** The profile is a singleton (id=1 in `style_profile`). This is a single-user app design. If multi-user auth is added later, this table needs a `user_id` column and the upsert logic must change. The forced-refresh (`force=True`) was removed from `_load_context` in `routes_posts.py` because it caused generation timeouts — do not re-add it there.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `profile.py` | Lowered _REFRESH_GROWTH_RATIO from 1.20 to 1.05 for more frequent style profile updates |
| 2026-04-29 | `__init__.py`, `collector.py`, `profile.py` | Initial creation — style corpus collection and LLM-distilled profile for Post Studio |
