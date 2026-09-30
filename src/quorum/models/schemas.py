from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Message(BaseModel):
    """
    Represents a single message in the LLM conversation.
    """
    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class DiscussionPhase(BaseModel):
    """
    Represents a phase in the Quorum discussion transcript.
    """
    phase: str
    model: str
    content: str

class DiscussionResult(BaseModel):
    """
    The final output of a Quorum orchestration round.
    """
    transcript: List[DiscussionPhase]
    final_synthesis: str
