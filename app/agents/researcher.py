import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from ddgs import DDGS
from app.state import ResearchFinding, WorkflowState
from tavily import TavilyClient, TavilyKeylessLimitError

load_dotenv()

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

    def _search_tavily(self, query: str, max_results: int = 5) -> list[ResearchFinding]:
        tavily_api_key = os.getenv("TAVILY_API_KEY")

        try:
            if tavily_api_key:
                log.info(
                    f"Attempting Tavily search (API key mode) for query: '{query}'"
                )
                client = TavilyClient(api_key=tavily_api_key)
            else:
                log.info(
                    f"Attempting Tavily search (Keyless mode) for query: '{query}'"
                )
                client = TavilyClient()

            response = client.search(query=query, max_results=max_results)

            findings: list[ResearchFinding] = []
            for item in response.get("results", []):
                title = item.get("title", "")
                snippet = item.get("content", "")
                url = item.get("url", "")

                if snippet:
                    findings.append(
                        ResearchFinding(title=title, claim=snippet, source=url)
                    )
            return findings
        except TavilyKeylessLimitError as e:
            retry_after = getattr(e, "retry_after_seconds", "unknown")
            log.warning(
                f"Tavily keyless limit reached: {e} (retry after {retry_after}s). Falling back..."
            )
            return []
        except Exception as e:
            log.warning(f"Tavily search failed for query '{query}': {e}")
            return []

    def _search_ddgs(self, query: str, max_results: int = 5) -> list[ResearchFinding]:
        try:
            log.info(f"Attempting DDGS search with query: '{query}'")
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))

            findings: list[ResearchFinding] = []
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
            return findings
        except Exception as e:
            log.warning(f"DDGS search failed for query '{query}': {e}")
            return []

    def run(self, state: WorkflowState) -> WorkflowState:
        optimized_query = self._generate_search_query(state.query)
        log.info(f"Optimized search query: '{optimized_query}'")

        queries_to_try = [optimized_query]
        if state.query.strip().lower() != optimized_query.strip().lower():
            queries_to_try.append(state.query.strip())

        findings: list[ResearchFinding] = []

        # 1. Primary: Try Tavily Search
        for q in queries_to_try:
            findings = self._search_tavily(q, max_results=5)
            if findings:
                log.info(
                    f"Tavily successfully found {len(findings)} results with query: '{q}'"
                )
                break

        # 2. Fallback: Try DuckDuckGo (DDGS) if Tavily produced no results
        if not findings:
            log.info("No findings from Tavily. Falling back to DuckDuckGo (DDGS)...")
            for q in queries_to_try:
                findings = self._search_ddgs(q, max_results=5)
                if findings:
                    log.info(
                        f"DDGS successfully found {len(findings)} results with query: '{q}'"
                    )
                    break

        if not findings:
            log.error("All search methods and queries failed; findings list is empty.")

        state.findings = findings
        return state
