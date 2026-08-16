"""Pydantic request/response models."""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    source_type: str = "url"           # url | upload | local | demo
    url: str = ""
    local_path: str = ""


class InvestigationCreate(BaseModel):
    project_id: str


class ApplyRequest(BaseModel):
    confirm: bool = False


class DemoRequest(BaseModel):
    bug: str = "auth"                  # which demo repository to run


class ProjectOut(BaseModel):
    id: str
    name: str
    source_type: str
    source_url: str = ""
    local_path: str
    overview: Optional[dict] = None
    created_at: float


class FailureOut(BaseModel):
    test_id: str
    error_type: str = ""
    error_msg: str = ""
    file: str = ""
    line: Optional[int] = None
    severity: str = "MEDIUM"
    stack_trace: str = ""
    reproducible: bool = False


class InvestigationOut(BaseModel):
    id: str
    project_id: str
    status: str
    branch: Optional[str] = None
    attempts: int = 0
    confidence: Optional[float] = None
    summary: Optional[dict] = None
    test_runs: list[dict] = []
    failures: list[dict] = []
    steps: list[dict] = []
    patches: list[dict] = []
    verifications: list[dict] = []
    created_at: float
    updated_at: float


class TraceFrame(BaseModel):
    func: str
    file: str
    line: int
    args: Optional[dict] = None
    return_value: Optional[str] = None
    exec_time: Optional[float] = None
    exception: Optional[str] = None
    source: Optional[list[dict]] = None   # [{line, text, failing}]


class Hypothesis(BaseModel):
    root_cause: str
    explanation: str
    confidence: float = Field(ge=0, le=1)
    risk: str = "MEDIUM"
    evidence: list[dict] = []
    rule: str = ""


class Patch(BaseModel):
    diff: str = ""
    files_changed: int = 0
    lines_added: int = 0
    lines_removed: int = 0
    risk: str = "MEDIUM"
    confidence: Optional[float] = None
    reason: str = ""
    status: str = "proposed"
    applied: bool = False


class VerificationOut(BaseModel):
    before: dict = {}
    after: dict = {}
    full: Optional[dict] = None
    passed: bool = False
