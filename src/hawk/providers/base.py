import abc
from typing import AsyncGenerator, List

from hawk.models.schemas import Message


class BaseProvider(abc.ABC):
    """
    Abstract base class for all LLM providers in Hawk.
    """
    def __init__(
        self,
        name: str,
        model_name: str,
        color: str = "white",
        uses_custom_tools: bool = False,
    ) -> None:
        self.name = name
        self.model_name = model_name
        self.color = color
        # Whether this provider relies on Hawk's own function-calling tools
        # (read_file, run_command, ...) that execute through the local shell.
        # CLI providers (Claude Code, Codex) have their own native tools and
        # leave this False so we don't advertise Hawk's tool schema to them.
        self.uses_custom_tools = uses_custom_tools

    async def start_session(self, system_prompt: str) -> None:
        """
        Initializes a persistent background session if required by the provider.
        """
        pass

    async def close_session(self) -> None:
        """
        Cleans up resources and gracefully terminates background sessions.
        """
        pass

    @abc.abstractmethod
    async def generate_response(self, system_prompt: str, messages: List[Message]) -> str:
        """
        Generates a complete response from the LLM.
        """
        pass

    @abc.abstractmethod
    def async_stream_response(
        self, system_prompt: str, messages: List[Message]
    ) -> AsyncGenerator[str, None]:
        """
        Generates a streaming response from the LLM, yielding chunks of text as they arrive.
        """
        pass
