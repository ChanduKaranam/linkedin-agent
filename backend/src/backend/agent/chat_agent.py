from __future__ import annotations

import hashlib
import json
from pathlib import Path

import litellm

from ..logging_setup import get_logger
from ..models import PersistedTrend
from .prompts import CHAT_SYSTEM
from .tools.scrape import scrape_url
from .tools.search import search_web

log = get_logger(__name__)

_TOOL_DEFS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for more information about this topic. Only use for questions related to the current topic.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query, focused on the current topic"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_scrape",
            "description": "Fetch the full content of a specific URL. Use after web_search to get article details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"}
                },
                "required": ["url"],
            },
        },
    },
]


def _build_system_prompt(trend: PersistedTrend, cache_dir: Path, source_chars: int) -> str:
    sources_text = ""
    for source in trend.sources:
        cache_file = cache_dir / f"{hashlib.md5(source.url.encode()).hexdigest()}.md"
        if cache_file.exists():
            try:
                content = cache_file.read_text(encoding="utf-8", errors="replace")[:source_chars]
                sources_text += f"\n\n### {source.title} ({source.domain})\nURL: {source.url}\n\n{content}"
            except OSError:
                pass

    key_points_text = "\n".join(f"- {p}" for p in trend.key_points)
    return CHAT_SYSTEM.format(
        headline=trend.headline,
        one_liner=trend.one_liner,
        key_points=key_points_text,
        detailed_markdown=trend.detailed_markdown,
        sources_text=sources_text or "(No cached source content available — use web tools if needed.)",
    )


async def _exec_web_search(query: str) -> list[dict]:
    results = await search_web(query, max_results=5)
    return [{"url": r.url, "title": r.title, "snippet": r.snippet} for r in results]


async def _exec_web_scrape(url: str, cache_dir: Path) -> dict:
    page = await scrape_url(url)
    if page is None:
        return {"url": url, "title": "", "markdown": "", "error": "Could not retrieve content."}
    cache_file = cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.md"
    try:
        cache_file.write_text(page.markdown, encoding="utf-8")
    except OSError:
        pass
    return {"url": page.url, "title": page.title, "markdown": page.markdown[:6000]}


async def answer(
    trend: PersistedTrend,
    history: list[dict],
    user_message: str,
    model_str: str,
    cache_dir: Path,
    max_tool_calls: int = 4,
    source_chars_per_doc: int = 6000,
) -> dict:
    """Run one chat turn. Returns {reply, citations, used_web}."""
    system_prompt = _build_system_prompt(trend, cache_dir, source_chars_per_doc)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in history:
        messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_message})

    citations: list[dict] = []
    used_web = False

    for iteration in range(max_tool_calls + 1):
        response = await litellm.acompletion(
            model=model_str,
            messages=messages,
            tools=_TOOL_DEFS if iteration < max_tool_calls else None,
            tool_choice="auto" if iteration < max_tool_calls else None,
        )

        msg = response.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            reply = msg.content or ""
            log.info("chat_answer_complete", used_web=used_web, citations=len(citations))
            return {"reply": reply, "citations": citations, "used_web": used_web}

        # Append assistant message with tool_calls
        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        assistant_entry["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in tool_calls
        ]
        messages.append(assistant_entry)

        for tc in tool_calls:
            fn = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}

            if fn == "web_search":
                result = await _exec_web_search(args.get("query", ""))
                used_web = True
                for r in result:
                    if not any(c["url"] == r["url"] for c in citations):
                        citations.append({"url": r["url"], "title": r["title"], "snippet": r["snippet"]})
                tool_content = json.dumps(result)
            elif fn == "web_scrape":
                result = await _exec_web_scrape(args.get("url", ""), cache_dir)
                used_web = True
                url = result.get("url", "")
                if url and not any(c["url"] == url for c in citations):
                    citations.append({"url": url, "title": result.get("title", ""), "snippet": ""})
                tool_content = json.dumps(result)
            else:
                tool_content = json.dumps({"error": f"Unknown tool: {fn}"})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_content,
            })

    return {
        "reply": "I was unable to find a complete answer. Please try rephrasing your question.",
        "citations": citations,
        "used_web": used_web,
    }
