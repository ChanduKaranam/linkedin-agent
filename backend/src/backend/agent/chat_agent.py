from __future__ import annotations

import json
from pathlib import Path

import litellm
from sqlalchemy.ext.asyncio import AsyncSession

from ..logging_setup import get_logger
from ..models import PersistedTrend
from ..rag.indexer import index_trend
from ..rag.retriever import retrieve
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


async def _build_system_prompt(
    trend: PersistedTrend,
    user_query: str,
    session: AsyncSession,
) -> str:
    """Retrieve the most relevant chunks for this query and build a focused system prompt."""
    if trend.id is None:
        sources_text = "(No indexed sources available — use web tools if needed.)"
    else:
        chunks = await retrieve(session, trend.id, user_query, k=6)
        if chunks:
            parts = []
            for chunk in chunks:
                parts.append(
                    f"### {chunk.source_title} ({chunk.source_domain})\n"
                    f"URL: {chunk.source_url}\n\n{chunk.text}"
                )
            sources_text = "\n\n".join(parts)
        else:
            sources_text = "(No relevant source excerpts found — use web tools if needed.)"

    key_points_text = "\n".join(f"- {p}" for p in trend.key_points)
    return CHAT_SYSTEM.format(
        headline=trend.headline,
        one_liner=trend.one_liner,
        key_points=key_points_text,
        detailed_markdown=trend.detailed_markdown,
        sources_text=sources_text,
    )


async def _exec_web_search(query: str) -> list[dict]:
    results = await search_web(query, max_results=5)
    return [{"url": r.url, "title": r.title, "snippet": r.snippet} for r in results]


async def _exec_web_scrape(url: str, cache_dir: Path, trend: PersistedTrend, session: AsyncSession) -> dict:
    page = await scrape_url(url)
    if page is None:
        return {"url": url, "title": "", "markdown": "", "error": "Could not retrieve content."}

    # Cache to disk
    import hashlib
    cache_file = cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.md"
    try:
        cache_file.write_text(page.markdown, encoding="utf-8")
    except OSError:
        pass

    # Index new page into chunks so follow-up retrieval benefits from it
    if trend.id is not None:
        from ..models import Source
        import tldextract
        ext = tldextract.extract(url)
        domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
        source = Source(url=page.url, title=page.title or domain, domain=domain)
        try:
            await index_trend(session, trend.id, trend.run_id, [source], cache_dir)
        except Exception as exc:
            log.warning("chat_scrape_index_failed", url=url, error=str(exc))

    return {"url": page.url, "title": page.title, "markdown": page.markdown[:6000]}


async def answer(
    trend: PersistedTrend,
    history: list[dict],
    user_message: str,
    model_str: str,
    cache_dir: Path,
    max_tool_calls: int = 4,
    session: AsyncSession | None = None,
    # source_chars_per_doc kept for backwards compat but no longer used
    source_chars_per_doc: int = 6000,
) -> dict:
    """Run one chat turn. Returns {reply, citations, used_web}."""
    if session is None:
        raise ValueError("session is required for hybrid RAG retrieval")

    system_prompt = await _build_system_prompt(trend, user_message, session)

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
                result = await _exec_web_scrape(args.get("url", ""), cache_dir, trend, session)
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
