"""Reported Paper 1 references supplied in task S2A; never computed results."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaskCode(StrEnum):
    T01 = "T01"
    T02 = "T02"
    T03 = "T03"
    T04 = "T04"
    T05 = "T05"


class Task(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    code: TaskCode
    genre: str
    form: Literal["paragraph", "essay"]

    @model_validator(mode="after")
    def validate_definition(self):
        expected = {
            TaskCode.T01: ("narrative", "paragraph"),
            TaskCode.T02: ("descriptive", "paragraph"),
            TaskCode.T03: ("expository", "paragraph"),
            TaskCode.T04: ("persuasive", "paragraph"),
            TaskCode.T05: ("persuasive", "essay"),
        }
        if (self.genre, self.form) != expected[self.code]:
            raise ValueError("Task definition must match the supplied Paper 1 task mapping")
        return self


TASKS = (
    Task(code=TaskCode.T01, genre="narrative", form="paragraph"),
    Task(code=TaskCode.T02, genre="descriptive", form="paragraph"),
    Task(code=TaskCode.T03, genre="expository", form="paragraph"),
    Task(code=TaskCode.T04, genre="persuasive", form="paragraph"),
    Task(code=TaskCode.T05, genre="persuasive", form="essay"),
)


class ReportedReference(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    key: str
    students: int = Field(ge=0)
    texts: int = Field(ge=0)
    potential_task_slots: int | None = Field(default=None, ge=0)
    basis: Literal["reported_reference_not_recomputed"] = "reported_reference_not_recomputed"
    source: Literal["user_supplied_S2A_context"] = "user_supplied_S2A_context"


REPORTED_CORPORA = (
    ReportedReference(key="source_inventory", students=46, texts=200, potential_task_slots=230),
    ReportedReference(key="primary_80", students=35, texts=163),
    ReportedReference(key="sensitivity_100", students=24, texts=110),
    ReportedReference(key="balanced_five_task", students=23, texts=115),
)

PRIMARY_MIN_WORDS = 80
PRIMARY_MIN_ELIGIBLE_TASKS = 4
INVENTORY_PASS_MIN_WORDS = 100
SENSITIVITY_MIN_WORDS = 100
REPORTED_DUPLICATE_PAIRS = 4
REPORTED_DUPLICATE_PROFILES = 2
# These references are not assertions against runtime snapshot membership.
