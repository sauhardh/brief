from pydantic import BaseModel, model_validator
from typing import Optional


class ResearchFinding(BaseModel):
    title: str
    claim: str
    source: Optional[str] = None


class Analysis(BaseModel):
    summary: str
    key_observations: list[str]
    competitors: list[str]
    missing_info: list[str]
    confidence: str
    sources: list[str] = []


class Criticism(BaseModel):
    approved: bool
    feedback: list[str]
    revision_required: bool

    @model_validator(mode="after")
    def auto_set_revision(self):
        if not self.approved:
            self.revision_required = True
        return self


class WorkflowState(BaseModel):
    query: str
    findings: list[ResearchFinding] = []
    analysis: Optional[Analysis] = None
    criticism: Optional[Criticism] = None
    revision_count: int = 0
    final_brief: Optional[Analysis] = None
