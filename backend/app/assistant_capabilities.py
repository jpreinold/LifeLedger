from __future__ import annotations

from typing import Any


PROPOSE_ACTIONS_TOOL_NAME = "propose_lifeledger_actions"


def action_tool(schema: dict[str, Any]) -> dict[str, Any]:
    """The assistant can propose this closed action plan; it cannot mutate data."""
    return {
        "type": "function",
        "name": PROPOSE_ACTIONS_TOOL_NAME,
        "description": (
            "Propose a confirmation-gated LifeLedger action plan using only the supplied "
            "action types, item types, candidate IDs, and normal detail keys."
        ),
        "strict": True,
        "parameters": schema,
    }


def domain_automation_context() -> dict[str, Any]:
    """Stable domain behavior the model may rely on instead of duplicating bookkeeping."""
    return {
        "birthday_pairing": {
            "supported_item_types": ["person", "pet"],
            "birthday_formats": ["YYYY-MM-DD", "--MM-DD"],
            "item_birthday_automatically_maintains_annual_reminder": True,
            "birthday_reminder_automatically_maintains_linked_item": True,
            "yearless_birthday_stays_yearless_on_item": True,
            "instruction": (
                "Propose only the object explicitly requested. LifeLedger creates, updates, "
                "and links its birthday counterpart after confirmation."
            ),
        },
        "mutation_policy": {
            "tool_only_proposes": True,
            "every_write_requires_user_confirmation": True,
            "candidate_ids_are_untrusted_allowlisted_references": True,
        },
    }
