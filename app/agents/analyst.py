from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.state import Analysis, WorkflowState


class Analyst:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

        self.prompt: ChatCompletionMessageParam = {
            "role": "system",
            "content": (
                "You are a market analyst. "
                "Synthesize the provided research findings "
                "into a research brief. "
                "Follow strict evidence grounding. "
                "Identify up to 2 competitors if relevant. "
                "Never invent facts or sources."
            ),
        }

    def run(self, state: WorkflowState) -> WorkflowState:
        if state.criticism and state.criticism.revision_required and state.analysis:
            user_content = self._build_revision_prompt(state)
        else:
            user_content = self._build_draft_prompt(state)

        messages: list[ChatCompletionMessageParam] = [
            self.prompt,
            {
                "role": "user",
                "content": user_content,
            },
        ]

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name, messages=messages, response_format=Analysis
        )

        response = completion.choices[0].message.parsed
        if not response:
            raise ValueError("Analyst returned an empty response.")

        state.analysis = response
        return state

    def _build_draft_prompt(self, state: WorkflowState) -> str:
        findings_text = (
            "\n".join(
                f"- [{f.title}] {f.claim} (Source: {f.source})" for f in state.findings
            )
            or "No findings available."
        )
        return f"""Market Query: {state.query} Research Findings: {findings_text}. Generate the structured JSON research brief."""

    def _build_revision_prompt(self, state: WorkflowState) -> str:
        feedback_text = "\n".join(
            f"- {fb}" for fb in (state.criticism.feedback if state.criticism else [])
        )
        previous_brief = (
            state.analysis.model_dump_json(indent=2) if state.analysis else "{}"
        )
        return f"""Market Query: {state.query} Previous Brief: {previous_brief}. Critic Feedback to address {feedback_text}. Produce a revised structured JSON research brief resolving the issues."""
