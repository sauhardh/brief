from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.state import Criticism, WorkflowState


class Critic:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

        self.prompt: ChatCompletionMessageParam = {
            "role": "system",
            "content": (
                "You are a rigorous Research Brief Critic and Fact-Checker. "
                "Evaluate the draft research brief against the provided research findings.\n\n"
                "Criteria:\n"
                "1. Evidence Grounding: Are all claims strictly supported by findings?\n"
                "2. Competitor Rule: Ensure if there are competitors or not\n"
                "3. Completeness: Check summary, observations, sources, and missing info.\n\n"
                "If acceptable: approved=true, revision_required=false.\n"
                "If flaws exist: approved=false, revision_required=true, with specific actionable feedback."
            ),
        }

    def run(self, state: WorkflowState) -> WorkflowState:
        if not state.analysis:
            raise ValueError("Critic cannot run without a draft analysis in state.")

        user_content = self._build_critic_prompt(state)
        messages: list[ChatCompletionMessageParam] = [
            self.prompt,
            {
                "role": "user",
                "content": user_content,
            },
        ]

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name, messages=messages, response_format=Criticism
        )

        response = completion.choices[0].message.parsed
        if not response:
            raise ValueError("Critic failed to generate structured critique.")

        state.criticism = response
        return state

    def _build_critic_prompt(self, state: WorkflowState) -> str:
        findings_text = (
            "\n".join(
                f"- [{f.title}] {f.claim} (Source: {f.source})" for f in state.findings
            )
            or "No research findings available."
        )
        draft_json = (
            state.analysis.model_dump_json(indent=2) if state.analysis else "{}"
        )

        return (
            f"User Query: {state.query}\n\n"
            f"Original Research Findings:\n{findings_text}\n\n"
            f"Draft Brief from Analyst:\n{draft_json}\n\n"
            "Evaluate this draft brief against the original findings and provide your review."
        )
