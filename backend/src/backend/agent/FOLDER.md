# backend/src/backend/agent/

## Purpose
AI agent layer. Uses LiteLLM as the model backend (Mistral by default). Contains three distinct agent types — trend synthesis, chat — plus supporting tools and shared prompts.

## Subfolders
| Folder | Role |
|---|---|
| `tools/` | Reusable async tools: web search, page scraping, robots.txt checking |

## Files in this Directory
| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `trend_agent.py` | `synthesize_daily` (one LLM call → `DailyBriefs`, 5–15 stories) and `synthesize_all` (search pipeline → single `TrendSummary`) |
| `chat_agent.py` | Stateless RAG chat turn. Retrieves top-k chunks via hybrid search, builds system prompt, runs tool-calling loop (`web_search`, `web_scrape`). Returns `{reply, citations, used_web}` |
| `post_writer.py` | `generate_linkedin_post()` and `generate_blog_post()`. Both accept trend + chat history + insights + style profile + few-shot samples + user_instructions. `_format_user_content()` structures user messages into labelled sections (questions / opinions / saved insights) so the LLM understands the user's angle. |
| `prompts.py` | All LLM prompt strings. Includes `STYLE_DISTILL_*`, `LINKEDIN_POST_*`, `BLOG_POST_*` in addition to the original synthesis and chat prompts. |

## Key Design Decisions
- **Daily synthesis** replaced old cluster-then-summarize flow: one LLM call reads all articles and returns `DailyBriefs` (1–15 distinct stories). Prevents duplicate headlines for the same event.
- **Headline similarity dedup** (`_dedup_by_headline_similarity` in `pipeline.py`) uses `rapidfuzz.token_sort_ratio ≥ 80` as a post-LLM safety net.
- **Markdown fence stripping** (`_strip_fences`) handles Mistral's tendency to wrap JSON in ```` ```json ```` fences.
- **Chat tool budget**: controlled by `ChatBudget.max_tool_calls` (default 4) to prevent runaway API costs.
- **`_format_user_content`**: separates user messages into (1) questions asked, (2) opinions/statements, (3) saved insights. Filters out short messages (<15 chars) like "thanks" or "yes". Labels each section clearly so the LLM uses them as the post's angle rather than just filler.

## Last Session Changes
**Session date:** 2026-05-08

**Changes made:**
- `post_writer.py` — fixed a bug in `_format_user_content`. The insight tags were being appended to `parts[-1]` after the `parts.append(entry)` call. If all insights in the loop were filtered (length < 10 chars), `parts[-1]` would modify the previous section header instead of the insight entry. Fixed by building the `entry` string fully (including tags) before calling `parts.append(entry)`.

**Reason:** A `post_writer.py` edge case: when all saved insights were short (< 10 chars) and the outer `for ins in insights[:20]` loop `continue`d for all items, the `if ins.get("tags")` check at the end of the loop still referenced the last `ins` value. `parts[-1]` then mutated whatever string was last added to `parts` (likely a section header). This would corrupt the LLM prompt context for that post.

**Outcome:** Fixed. The bug only manifested when all insights were < 10 characters, which is unlikely in practice but was a real crash path.

**Watch out for:** `_format_user_content` is called in both `generate_linkedin_post` and `generate_blog_post` — the fix covers both.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-08 | `post_writer.py` | Fixed `parts[-1]` bug: tags for an insight were appended to the wrong list entry when all insights were filtered by length; moved tag append inside the entry-building loop before `parts.append(entry)` |
| 2026-05-02 | `trend_agent.py`, `prompts.py` | Tightened LLM recency cutoff to 1 day; added "skip if no date signal" rule to synthesis prompt |
| 2026-05-01 | `post_writer.py` | Rewrote _format_user_content to structure user messages into questions/opinions/insights sections; added _is_question helper; improved LLM context quality |
| 2026-05-01 | `prompts.py`, `post_writer.py` | Rewrote post prompts for practitioner-voice style; added `user_instructions` param for targeted regeneration |
| 2026-04-29 | `prompts.py`, `post_writer.py` (new) | Added style distillation, LinkedIn, and blog post prompts + generator functions |
| — | — | Initial documentation created |
