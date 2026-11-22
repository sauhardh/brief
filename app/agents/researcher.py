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

        queries_to_try = [optimized_query, state.query]
        findings: list[ResearchFinding] = []
        for q in queries_to_try:
            log.info(f"Attempting web search with query: '{q}'")
            try:
                with DDGS() as ddgs:
                    results = list(ddgs.text(q, max_results=5))

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

                if findings:
                    log.info(f"Found {len(findings)} results with query: '{q}'")
                    break
            except Exception as e:
                log.warning(f"Search failed for query '{q}': {e}")

        if not findings:
            log.error("All search queries failed; findings list is empty.")

        state.findings = findings
        return state
