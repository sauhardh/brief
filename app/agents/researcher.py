from openai import OpenAI
from ddgs import DDGS

from app.state import ResearchFinding, WorkflowState
import logging

log = logging.getLogger(__name__)


class Researcher:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

    def _generate_search_query(self, user_topic: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a search query optimizer. Convert the user's topic into a concise keyword search query less than 6 keywords"
                        "Include relevant geographic and industry terms. Return ONLY the search query keywords, without quotes or explanations."
                    ),
                },
                {"role": "user", "content": user_topic},
            ],
            temperature=0.0,
        )
        query = response.choices[0].message.content or user_topic
        return query.strip().strip('"')

    def run(self, state: WorkflowState) -> WorkflowState:
        optimized_query = self._generate_search_query(state.query)
        log.info(f"Optimized search query: '{optimized_query}'")

        findings: list[ResearchFinding] = []
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(optimized_query, max_results=5))

            for item in results:
                href = item.get("href", "")
                # Skip sponsored search ads
                if "aclick" in href or "ad." in href or "doubleclick" in href:
                    continue

                title = item.get("title", "")
                snippet = item.get("body", "")

                if snippet:
                    findings.append(
                        ResearchFinding(title=title, claim=snippet, source=href)
                    )

        except Exception as e:
            log.error(f"Could not search your request on web {e}")

        log.info(f"Findings: {findings}")

        if not findings:
            log.error("Your findings is empty.")

        state.findings = findings
        return state
