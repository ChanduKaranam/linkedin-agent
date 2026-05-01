# backend/src/backend/agent/

## Purpose
AI agent layer. Uses Google ADK (`google-adk`) with LiteLLM as the model backend (Mistral by default). Contains three distinct agent types — trend synthesis, chat — plus supporting tools and shared prompts.

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
| `post_writer.py` | `generate_linkedin_post()` and `generate_blog_post()`. Both accept trend + chat history + insights + style profile + few-shot samples; return parsed JSON via `litellm.acompletion`. |
| `prompts.py` | All LLM prompt strings. Now includes: `STYLE_DISTILL_*`, `LINKEDIN_POST_*`, `BLOG_POST_*` in addition to the original synthesis and chat prompts. |

## Key Design Decisions
- **Daily synthesis** replaced old cluster-then-summarize flow: one LLM call reads all articles and returns `DailyBriefs` (1–15 distinct stories). Prevents duplicate headlines for the same event.
- **Headline similarity dedup** (`_dedup_by_headline_similarity` in `pipeline.py`) uses `rapidfuzz.token_sort_ratio ≥ 80` as a post-LLM safety net.
- **Markdown fence stripping** (`_strip_fences`) handles Mistral's tendency to wrap JSON in ```` ```json ```` fences.
- **Chat tool budget**: controlled by `ChatBudget.max_tool_calls` (default 4) to prevent runaway API costs.

## Last Session Changes
**Session date:** 2026-05-01

**Changes made:**
- `prompts.py` — rewrote `LINKEDIN_POST_SYSTEM`, `LINKEDIN_POST_USER`, `BLOG_POST_SYSTEM`, `BLOG_POST_USER` to enforce a practitioner-voice writing style modelled on a real hands-on technical article. Key additions: explicit "WHAT GREAT LOOKS LIKE" section with concrete style rules; "BANNED PHRASES" list (no "excited to share", "game-changer", "rapidly evolving landscape", etc.); blog target bumped to 900–1400 words with required hard-won-lessons section; instructions now emphasise honest trade-offs, first-person "I built this" framing, and specific numbers/details over vague claims.
- `post_writer.py` — added `user_instructions: str = ""` keyword-only argument to both `generate_linkedin_post()` and `generate_blog_post()`. When non-empty, the instructions are appended to the user message as a `## Specific instructions for this version` section, giving the LLM a direct override on top of all style context.

**Reason:** Generated content was sounding generic/AI-polished. User provided a reference article as the target quality bar. Also needed a way to describe targeted changes when regenerating without losing the style context.

**Outcome:** Prompts updated and syntax verified. The `user_instructions` field is optional (default empty string) so existing callers are unaffected.

**Watch out for:** The "BANNED PHRASES" list in the prompts is advisory — the LLM occasionally ignores it on first attempt, especially with smaller models. If the style is still generic, consider adding 1–2 concrete examples of a good hook directly in the prompt (few-shot beats instructions for style).

## Change Log
| Date | File(s) Changed | Summary |
|---|---|---|
| 2026-05-01 | `prompts.py`, `post_writer.py` | Rewrote post prompts for practitioner-voice style; added `user_instructions` param for targeted regeneration |
| 2026-04-29 | `prompts.py`, `post_writer.py` (new) | Added style distillation, LinkedIn, and blog post prompts + generator functions |
| — | — | Initial documentation created |
