import logging
import requests
from dotenv import load_dotenv
from openai import OpenAI
from ddgs import DDGS
from app.state import ResearchFinding, WorkflowState
from app.searxng_manager import ensure_searxng_running

load_dotenv()

log = logging.getLogger(__name__)


class Researcher:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name
        self.searxng_url: str | None = None

        # Proactively check/warmup SearXNG
        try:
            self.searxng_url = ensure_searxng_running()
        except Exception as e:
            log.info(f"SearXNG warmup skipped: {e}")

    def _generate_search_query(self, user_topic: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert search query optimizer for search engines like Google and SearXNG.\n"
                        "Transform the user's research topic into a clean, high-intent web search query that retrieves market overviews, industry statistics, and competitors.\n\n"
                        "Rules:\n"
                        "1. Strip out command phrases (e.g. 'Analyze', 'Can you find', 'Write a report on', 'Brief on').\n"
                        "2. Keep the core subject, industry, and geographic location.\n"
                        "3. Add high-value market research terms if helpful (e.g. 'market size', 'competitors', 'industry overview').\n"
                        "4. Limit to 3 to 6 keywords.\n"
                        "5. Return ONLY the search query string. Never include quotes, punctuation, or explanations.\n\n"
                        "Examples:\n"
                        "- Input: 'Analyze the food delivery market in Nepal'\n"
                        "  Output: Nepal food delivery market competitors overview\n"
                        "- Input: 'Find top competitors of Airbnb in Southeast Asia'\n"
                        "  Output: Airbnb competitors Southeast Asia vacation rentals\n"
                        "- Input: 'Electric vehicle charging infrastructure growth in Norway'\n"
                        "  Output: Norway EV charging infrastructure market growth"
                    ),
                },
                {"role": "user", "content": user_topic},
            ],
            temperature=0.0,
        )
        query = response.choices[0].message.content or user_topic
        # Clean any quotes or extra whitespace
        cleaned_query = query.strip().strip('"').strip("'").strip("`")
        return cleaned_query

    def _search_searxng(
        self, query: str, max_results: int = 5
    ) -> list[ResearchFinding]:
        if not self.searxng_url:
            self.searxng_url = ensure_searxng_running()

        if not self.searxng_url:
            return []

        try:
            log.info(f"Attempting SearXNG search with query: '{query}'")
            res = requests.get(
                f"{self.searxng_url}/search",
                params={"q": query, "format": "json"},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=6,
            )
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])[:max_results]
                findings: list[ResearchFinding] = []
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("content", "")
                    url = item.get("url", "")
                    if snippet:
                        findings.append(
                            ResearchFinding(title=title, claim=snippet, source=url)
                        )
                return findings
            else:
                log.warning(f"SearXNG responded with HTTP status {res.status_code}")
                return []
        except Exception as e:
            log.warning(f"SearXNG search failed for query '{query}': {e}")
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

        # 1. Primary: Try Local SearXNG (Keyless, Unlimited)
        for q in queries_to_try:
            findings = self._search_searxng(q, max_results=5)
            if findings:
                log.info(
                    f"SearXNG successfully found {len(findings)} results with query: '{q}'"
                )
                break

        # 2. Fallback: Try DuckDuckGo (DDGS)
        if not findings:
            log.info("No findings from SearXNG. Falling back to DuckDuckGo (DDGS)...")
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
