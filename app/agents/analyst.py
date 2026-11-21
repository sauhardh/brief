from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError
import logging

from app.state import Analysis, WorkflowState

log = logging.getLogger(__name__)


class Analyst:
    def __init__(self, client: OpenAI, model_name: str):
        self.client = client
        self.model_name = model_name

        self.prompt: ChatCompletionMessageParam = {
            "role": "system",
            "content": (
                "You are a market analyst. Synthesize the provided research findings "
                "into a concise research brief. Follow strict evidence grounding. "
                "Identify up to 2 competitors if relevant. Never invent facts or sources.\n\n"
                "Return a valid JSON object with these EXACT keys:\n"
                "- summary: string (concise overview of the market/topic)\n"
                "- key_observations: list of strings (key insights/trends)\n"
                "- competitors: list of strings (maximum 2 competitors, or empty list)\n"
                "- sources: list of strings (source URLs or descriptions)\n"
                "- missing_info: list of strings (uncertainties or data gaps)\n"
                "- confidence: string ('high', 'medium', or 'low')"
            ),
        }

    def run(
        self,
        state: WorkflowState,
        retries_left: int = 2,
        feedback_msg: str | None = None,
    ) -> WorkflowState:
        if state.criticism and state.criticism.revision_required and state.analysis:
            user_content = self._build_revision_prompt(state)
        else:
            user_content = self._build_draft_prompt(state)

        if feedback_msg:
            user_content += f"\n\nPREVIOUS ERROR TO FIX:\n{feedback_msg}"

        messages: list[ChatCompletionMessageParam] = [
            self.prompt,
            {
                "role": "user",
                "content": user_content,
            },
        ]

        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Analyst returned an empty response.")

        try:
            analysis = Analysis.model_validate_json(content)
            analysis.competitors = analysis.competitors[:2]
            state.analysis = analysis
        except ValidationError as err:
            log.warning(
                f"Analyst validation failed ({retries_left} retries left): {err}"
            )

            if retries_left <= 0:
                raise ValueError(f"Analyst failed schema validation: {err}")

            feedback_msg = (
                f"Your response had this validation error:\n{err}\n\n"
                "Please correct the JSON and return ALL required keys: "
                "- summary: str\n"
                "- key_observations: list of str\n"
                "- competitors: list of str (max 2)\n"
                "- sources: list of str\n"
                "- missing_info: list of str\n"
                "- confidence: str ('high', 'medium', or 'low')"
            )

            return self.run(
                state, retries_left=retries_left - 1, feedback_msg=feedback_msg
            )
        return state

    def _build_draft_prompt(self, state: WorkflowState) -> str:
        findings_text = (
            "\n".join(
                f"- [{f.title}] {f.claim} (Source: {f.source})" for f in state.findings
            )
            or "No web findings available. State that no findings were retrieved."
        )
        return (
            f"Market Query: {state.query}\n\n"
            f"Research Findings:\n{findings_text}\n\n"
            "Synthesize the findings into the required JSON research brief."
        )

    def _build_revision_prompt(self, state: WorkflowState) -> str:
        feedback_text = "\n".join(
            f"- {fb}" for fb in (state.criticism.feedback if state.criticism else [])
        )
        previous_brief = (
            state.analysis.model_dump_json(indent=2) if state.analysis else "{}"
        )
        return (
            f"Market Query: {state.query}\n\n"
            f"Previous Brief:\n{previous_brief}\n\n"
            f"Critic Feedback to resolve:\n{feedback_text}\n\n"
            "Revise the brief addressing all feedback. Return ONLY the valid JSON research brief."
        )
