import asyncio
import os
from main import run_agent


def build_context(messages, new_message):
    """
    Convert saved session history into a prompt
    compatible with Member 1's run_agent(query).
    """

    history = []

    for message in messages[-10:]:
        role = message["role"]
        content = message["content"]

        history.append(f"{role}: {content}")

    history.append(f"user: {new_message}")

    return (
        "Use the following conversation context "
        "to understand the user's current request.\n\n"
        + "\n".join(history)
        + "\n\nRespond to the latest user message."
    )


async def execute_agent(
    message,
    history=None,
    dry_run=False
):
    """
    Execute Member 1's synchronous agent
    without blocking FastAPI's event loop.
    """

    history = history or []

    query = build_context(history, message)

    use_dry_run = dry_run or (
        os.getenv("AGENTX_DRY_RUN", "").lower()
        in ("1", "true", "yes")
    )

    answer, trace = await asyncio.to_thread(
        run_agent,
        query,
        dry_run=use_dry_run,
        verbose=False
    )

    return {
        "answer": str(answer),
        "trace": trace
    }
