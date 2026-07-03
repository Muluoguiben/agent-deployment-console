"""LLM-as-judge: scores an answer 1-5 against a case rubric. Provider-agnostic."""

import json
import re

from ..llm import make_chat_model

JUDGE_PROMPT = """\
You are grading a customer-support triage agent's reply.

Customer message:
{message}

Agent reply:
{answer}

Grading rubric:
{rubric}

Score the reply from 1 to 5:
5 = fully meets the rubric, grounded and precise
3 = acceptable: core diagnosis/behavior right, minor gaps
1 = wrong, ungrounded, fabricated, or violates the rubric

Respond with ONLY a JSON object: {{"score": <1-5>, "reason": "<one sentence>"}}\
"""


def judge_answer(judge_model: str, message: str, answer: str, rubric: str) -> float | None:
    """Returns the score, or None when judging is unavailable (no key / provider error)."""
    try:
        model = make_chat_model(judge_model)
        reply = model.invoke(
            JUDGE_PROMPT.format(message=message, answer=answer or "(empty)", rubric=rubric)
        )
        text = str(reply.content)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        data = json.loads(match.group(0))
        return float(data["score"])
    except Exception:
        return None
