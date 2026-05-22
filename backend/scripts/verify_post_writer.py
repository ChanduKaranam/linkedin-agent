import asyncio
import sys
import time
from pathlib import Path
from datetime import date

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Ensure environment variables are loaded
from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env")

from src.backend.models import PersistedTrend, Source
from src.backend.agent.post_writer import (
    generate_linkedin_post,
    generate_blog_post,
    evaluate_post_draft,
)

async def test_generation_and_evaluation():
    print("Starting verification test for post generation and evaluation...")
    
    # 1. Setup mock trend and inputs
    trend = PersistedTrend(
        run_id="test-run-id",
        run_date=date.today(),
        slug="google-unveils-project-astra-agent-capabilities",
        headline="Google Unveils Project Astra: Advanced Agentic AI Assistant",
        one_liner="Google DeepMind showcases Project Astra, a real-time agent capable of seeing, hearing, and remembering context.",
        detailed_markdown="""## Project Astra: DeepMind's Next-Gen Agent
Google showcased Project Astra at I/O, showing real-time video understanding, spatial memory, and low latency responses.
It represents a major milestone in agentic workflows and interactive assistants, combining multimodal inputs seamlessly.
        """,
        key_points=[
            "Project Astra is a real-time multimodal AI assistant.",
            "It has spatial memory and remembers where you put objects.",
            "Operates with very low latency, feeling like a natural human conversation.",
            "Runs on device and in cloud using next-gen Gemini models."
        ],
        sources=[
            Source(url="https://deepmind.google/astra", title="Project Astra", domain="deepmind.google")
        ],
        fingerprint="fingerprint-astra-123"
    )
    
    chat_messages = [
        {"role": "user", "content": "I think Project Astra is going to change how we interact with mobile apps daily."},
        {"role": "assistant", "content": "Indeed, real-time multimodal interaction is a game-changer."},
        {"role": "user", "content": "Can we talk about the latency challenge? What makes it so fast?"}
    ]
    
    insights = [
        {
            "user_perspective": "Low latency is critical. Local/on-device processing or highly optimized edge serving is the key constraint.",
            "summary": "Project Astra showcases extremely fast responses",
            "tags": ["AI", "Edge Computing"]
        }
    ]
    
    style_profile = "Authoritative yet accessible technical voice. Direct, clear, uses bullet points, minimal jargon, highly actionable."
    style_samples = [
        "Building a reliable LLM agent requires more than prompts. It requires deterministic check-loops. Here is why:",
        "Multimodal models are cool, but the real magic is in how you orchestrate the frame processing loops."
    ]

    # Test Cases
    tests = [
        ("linkedin", "leadership"),
        ("linkedin", "technical"),
        ("blog", "leadership"),
        ("blog", "technical")
    ]
    
    for kind, style in tests:
        print(f"\n--- Testing Kind: {kind} | Style: {style} ---")
        
        # Cool-down to prevent rate limit
        await asyncio.sleep(5)
        
        if kind == "linkedin":
            result = await generate_linkedin_post(
                trend=trend,
                chat_messages=chat_messages,
                insights=insights,
                style_profile=style_profile,
                style_samples=style_samples,
                style=style,
                user_instructions="Highlight operational latency and spatial memory."
            )
            content = result["content"]
            print(f"Generated {kind} post length: {len(content)}")
        else:
            result = await generate_blog_post(
                trend=trend,
                chat_messages=chat_messages,
                insights=insights,
                style_profile=style_profile,
                style_samples=style_samples,
                style=style,
                user_instructions="Add a section on performance trade-offs."
            )
            content = result["content_markdown"]
            print(f"Generated {kind} post length: {len(content)}")

        # Cool-down to prevent rate limit
        await asyncio.sleep(5)

        # Evaluate the draft
        print("Evaluating the draft...")
        evaluation = await evaluate_post_draft(
            content=content,
            kind=kind,
            style=style,
            trend_headline=trend.headline,
            trend_summary=trend.one_liner
        )
        
        print(f"Evaluation Score: {evaluation['score']}/10")
        print(f"Strengths: {len(evaluation['strengths'])}")
        print(f"Critiques: {len(evaluation['critique'])}")
        print(f"Suggestions: {len(evaluation['suggestions'])}")
        
        # Basic validation
        assert "score" in evaluation, "Evaluation must have a score"
        assert "strengths" in evaluation and isinstance(evaluation["strengths"], list), "Strengths must be a list"
        assert "critique" in evaluation and isinstance(evaluation["critique"], list), "Critiques must be a list"
        assert "suggestions" in evaluation and isinstance(evaluation["suggestions"], list), "Suggestions must be a list"
        assert 0.0 <= evaluation["score"] <= 10.0, "Score must be clamped between 0 and 10"

    print("\nAll post generation and evaluation tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_generation_and_evaluation())
