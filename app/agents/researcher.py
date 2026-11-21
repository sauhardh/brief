from openai import OpenAI
from duckduckgo_search import DDGS

from app.state import ResearchFinding, WorkflowState
import logging

log = logging.getLogger(__name__)


class Researcher:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

    def run(self, state: WorkflowState) -> WorkflowState:
        findings: list[ResearchFinding] = []
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(state.query, max_results=5))

            for item in results:
                title = item.get("title", "")
                snippet = item.get("body", "")
                href = item.get("href", "")

                findings.append(
                    ResearchFinding(title=title, claim=snippet, source=href)
                )
        except Exception as e:
            log.error(f"Could not search your request on web {e}")

        if not findings:
            log.error("Your findings is empty.")

        state.findings = findings
        return state
