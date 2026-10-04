from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import NormalizedModel


class BaseProvider(ABC):
    # pyrefly: ignore [unannotated-return]
    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    async def get_models(self) -> List[NormalizedModel]:
        """
        Fetch models from the provider and convert them to the NormalizedModel format.
        """
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """
        Validate that the provided API key works.
        """
        pass
