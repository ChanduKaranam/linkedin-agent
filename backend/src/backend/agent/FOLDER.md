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
**Session date:** 2026-05-02

**Changes made:**
- `trend_agent.py` — changed `cutoff = today - timedelta(days=2)` → `timedelta(days=1)` in `synthesize_daily`. The LLM is now told to discard anything older than yesterday.
- `prompts.py` — `DAILY_SYNTHESIS_INSTRUCTION`: (1) "2 days" → "1 day" in the recency rule; (2) added new bullet: "If you cannot determine the article's publication date from its content, ASSUME it is stale and SKIP IT"; (3) added recency signal guidance (explicit dates, "today"/"yesterday", etc.). `DAILY_SYNTHESIS_USER_TEMPLATE`: updated to "1 day" and "no clear date signal" wording.

**Reason:** LLM was accepting articles it couldn't date because the prompt said "use content's recency signals" — too soft. Tightening to 1-day cutoff and requiring date signals before accepting an article reduces stale news slipping through.

**Outcome:** Combined with the cache TTL and search recency fixes, the LLM now has much less stale content to process, and is more aggressive about skipping undated articles.

**Watch out for:** With a 1-day cutoff, breaking news from exactly 24h ago may occasionally be dropped. If the topic has slow news days, the LLM may struggle to find 5 distinct stories (the minimum). In that case raise `cutoff` back to 2 days.

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-02 | `trend_agent.py`, `prompts.py` | Tightened LLM recency cutoff to 1 day; added "skip if no date signal" rule to synthesis prompt |
| 2026-05-01 | `post_writer.py` | Rewrote _format_user_content to structure user messages into questions/opinions/insights sections; added _is_question helper; improved LLM context quality |
| 2026-05-01 | `prompts.py`, `post_writer.py` | Rewrote post prompts for practitioner-voice style; added `user_instructions` param for targeted regeneration |
| 2026-04-29 | `prompts.py`, `post_writer.py` (new) | Added style distillation, LinkedIn, and blog post prompts + generator functions |
| — | — | Initial documentation created |
