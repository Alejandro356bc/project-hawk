from typing import List, Optional

from pydantic import BaseModel


class NormalizedModel(BaseModel):
    provider: str
    id: str
    name: str
    context_length: Optional[int] = None
    input_price: Optional[float] = None
    output_price: Optional[float] = None
    capabilities: List[str] = []
