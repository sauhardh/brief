from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import ValidationError
import logging
import json

from app.state import Criticism, WorkflowState

log = logging.getLogger(__name__)


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
                "2. Competitor Rule: Ensure there are at most TWO competitors (if relevant).\n"
                "3. Completeness: Check summary, observations, sources, and missing info.\n\n"
                "Return a valid JSON object with these EXACT keys:\n"
                "- approved: boolean (true if brief is good, false if changes needed)\n"
                "- feedback: list of strings (actionable feedback items)\n"
                "- revision_required: boolean (true if revision needed, false if acceptable)"
            ),
        }

    def run(
        self,
        state: WorkflowState,
        retries_left: int = 2,
        feedback_msg: str | None = None,
    ) -> WorkflowState:
        if not state.analysis:
            raise ValueError("Critic cannot run without a draft analysis in state.")

        user_content = self._build_critic_prompt(state)
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
            temperature=0.1,
        )

        content = completion.choices[0].message.content
        if not content:
            raise ValueError("Critic failed to generate structured critique.")

        try:
            state.criticism = Criticism.model_validate_json(content)
        except ValidationError as err:
            log.warning(f"Validation failed ({retries_left} retries left): {err}")

            if retries_left <= 0:
                raise ValueError(f"Critic failed validation: {err}")

            feedback_msg = (
                f"Your response had this validation error:\n{err}\n\n"
                "Please correct the JSON and return ALL required keys: "
                "'approved' (bool), 'feedback' (list of str), 'revision_required' (bool)."
            )

            return self.run(
                state, retries_left=retries_left - 1, feedback_msg=feedback_msg
            )
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
