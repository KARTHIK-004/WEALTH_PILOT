"""Builds the provider-neutral request for one item from the approved input fields and the registered rubric.

The user message contains only the five approved fields of one item. Nothing else (no record ID, batch stamp,
overlap flag, duplicate mark, key information or human label) can reach a prompt: ``build_request`` accepts a
``SourceItem`` and reads only ``item.fields``.
"""

from __future__ import annotations

from math import ceil

from wealthpilot.data.gdelt.ai import OUTPUT_VERSION
from wealthpilot.data.gdelt.ai.fingerprints import canonical_json, sha256_obj
from wealthpilot.data.gdelt.ai.provider import ExecutionBlocked, SuggestionRequest
from wealthpilot.data.gdelt.ai.rubric import Rubric
from wealthpilot.data.gdelt.ai.schema import APPROVED_INPUT_FIELDS, SourceItem, output_json_schema

PROMPT_VERSION = "b2t_prompt_v1"
USER_TEMPLATE = "Label this item using the rubric. Item fields (JSON):\n{item_json}\n"
REPAIR_INSTRUCTION = ("Your previous answer did not satisfy the output schema. Answer again with ONE JSON object only, "
                      "following the Output section exactly, with no commentary and no markdown.")


def prompt_sha256() -> str:
    """Fingerprint of the prompt templates and the output schema (the rubric text has its own hash)."""
    return sha256_obj({"version": PROMPT_VERSION, "system": "{rubric}", "user": USER_TEMPLATE,
                       "repair": REPAIR_INSTRUCTION, "output_version": OUTPUT_VERSION,
                       "output_schema_sha256": sha256_obj(output_json_schema())})


def build_request(item: SourceItem, rubric: Rubric, *, max_output_tokens: int, reask: bool = False,
                  temperature: float | None = None) -> SuggestionRequest:
    if not item.sendable:
        raise ExecutionBlocked(f"{item.item_id} has input problems and is never sent: {'; '.join(item.input_problems)}")
    fields = {k: item.fields[k] for k in APPROVED_INPUT_FIELDS}
    user = USER_TEMPLATE.format(item_json=canonical_json(fields))
    if reask:
        user += "\n" + REPAIR_INSTRUCTION
    return SuggestionRequest(item.item_id, rubric.text, user, output_json_schema(), max_output_tokens, temperature)


def estimate_tokens(text: str) -> int:
    """A rough character-based estimate (about 4 characters per token). ESTIMATED, not a provider count."""
    return ceil(len(text) / 4)
