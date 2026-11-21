"""
Receives the query and start the workflow
"""

from dotenv import load_dotenv
from openai import OpenAI
import logging
import os

from app.agents.analyst import Analyst
from app.agents.critic import Critic
from app.agents.researcher import Researcher
from app.state import WorkflowState

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, model_name: str | None = None):
        load_dotenv()

        self.api_key = os.getenv("OPENAI_API_KEY")
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")

        # Select either api (groq way) or local ollama (ollama as fallback)
        self.__select_method(model_name)
        self.__ensure_ok()

        # Initialize all other agents
        log.info("Initializing other clients")
        self.researcher = Researcher(self.client, self.model_name)
        self.analyst = Analyst(self.client, self.model_name)
        self.critic = Critic(self.client, self.model_name)

    def start_workflow(self, query: str) -> WorkflowState:
        if not query or not query.strip():
            raise ValueError("Query must not be empty")

        self.query = query
        return WorkflowState(query=query.strip())

    def __select_method(self, model_name: str | None):
        if self.api_key:
            log.info("Going with Groq api key")
            self.provider = "openai"
            base_url = os.getenv("OPENAI_BASE_URL")  # or GROQ_BASE_URL
            self.model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

            self.client = OpenAI(api_key=self.api_key, base_url=base_url)
        else:
            log.info("Going with local ollama model")
            self.provider = "ollama"
            self.model_name = model_name or os.getenv("OLLAMA_MODEL", "mistral:latest")

            self.client = OpenAI(base_url=self.ollama_url, api_key="ollama")

    def __ensure_ok(self):
        try:
            models = self.client.models.list()
            available_models = {model.id for model in models.data}

            if self.provider == "ollama":
                if self.model_name not in available_models:
                    raise ValueError(
                        f"Model '{self.model_name}' not found in Ollama. "
                        f"Run: ollama pull {self.model_name}"
                    )

            log.info(
                f"Connected to {self.provider.upper()} using model: {self.model_name}"
            )
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to LLM provider({self.provider}): \n Error: {e}"
            )
