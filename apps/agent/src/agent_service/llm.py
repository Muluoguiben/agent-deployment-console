"""Provider-agnostic chat-model factory.

Model strings are provider-prefixed and live in the versioned agent config:
    anthropic:claude-haiku-4-5 | openai:gpt-* | google_genai:gemini-* | ...
Anything LangChain's init_chat_model supports works; usable providers are determined by
which API keys are present in the environment.

"scripted:" is a test/demo pseudo-provider backed by ScriptedChatModel.
"""

from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

# Registry for scripted models used by tests and the demo seed: name -> list of AIMessages.
SCRIPTS: dict[str, list[AIMessage]] = {}


class ScriptedChatModel(BaseChatModel):
    """Replays a fixed sequence of AIMessages; tolerates bind_tools. For tests and seeding."""

    script: list[AIMessage]
    cursor: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedChatModel":
        return self

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        if self.cursor >= len(self.script):
            reply = AIMessage(content="(script exhausted)")
        else:
            reply = self.script[self.cursor]
        # Bypass pydantic assignment validation for the cursor bump.
        object.__setattr__(self, "cursor", self.cursor + 1)
        return ChatResult(generations=[ChatGeneration(message=reply)])


def make_chat_model(model_str: str) -> BaseChatModel:
    if model_str.startswith("scripted:"):
        name = model_str.split(":", 1)[1]
        if name not in SCRIPTS:
            raise ValueError(f"no script registered under {name!r}")
        return ScriptedChatModel(script=list(SCRIPTS[name]))
    from langchain.chat_models import init_chat_model

    return init_chat_model(model_str)
