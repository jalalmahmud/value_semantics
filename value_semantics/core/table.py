from typing import Any

from pydantic import BaseModel, Field


class ColumnStats(BaseModel):
    sample_values: list[Any] = Field(default_factory=list)
    min: Any | None = None
    max: Any | None = None
    distinct_count: int | None = None
    null_count: int | None = None
    row_count: int | None = None


class ColumnProfile(BaseModel):
    name: str
    declared_type: str | None = None
    stats: ColumnStats = Field(default_factory=ColumnStats)


class TableProfile(BaseModel):
    table_name: str
    columns: list[ColumnProfile]
    row_samples: list[dict[str, Any]] = Field(default_factory=list)
