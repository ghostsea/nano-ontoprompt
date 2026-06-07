"""Pipeline 추상 기반"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

@dataclass
class PipelineContext:
    dataset_id: str
    version_no: int
    route: str  # A | B | C
    spec: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    result_uri: str | None = None
    rows_in: int = 0
    rows_out: int = 0
    error: str | None = None

class PipelineStep(ABC):
    @abstractmethod
    def run(self, ctx: PipelineContext, data: list[dict]) -> list[dict]:
        """데이터를 변환하고 새 데이터를 반환"""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__
