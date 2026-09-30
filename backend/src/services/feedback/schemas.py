from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.services.feedback.scoring import VALID_ACTIONS


class InteractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    listing_id: int
    action_type: str = Field(min_length=1, max_length=32)
    source: Optional[str] = Field(default=None, max_length=32)
    dwell_time_seconds: Optional[float] = Field(default=None, ge=0)
    raw_query: Optional[str] = None
    conversation_id: Optional[int] = None
    session_id: Optional[str] = Field(default=None, max_length=64)

    def normalized_action(self) -> Optional[str]:
        action = self.action_type.strip().lower()
        return action if action in VALID_ACTIONS else None
