from __future__ import annotations

from synapse.communication.persona_pool import (
    load_communication_persona_prompt_from_file,
    load_personas_from_file,
    save_communication_persona_prompt_to_file,
    save_personas_to_file,
)
from synapse.protocol import Persona


def test_persona_pool_round_trips_communication_persona_prompt(tmp_path):
    personas_file = tmp_path / "personas.yaml"

    save_communication_persona_prompt_to_file(
        "You are calm.\nSpeak in Chinese.",
        path=personas_file,
    )

    assert load_communication_persona_prompt_from_file(personas_file) == (
        "You are calm.\nSpeak in Chinese."
    )
    assert load_personas_from_file(personas_file) == []


def test_save_personas_preserves_communication_persona_prompt(tmp_path):
    personas_file = tmp_path / "personas.yaml"
    save_communication_persona_prompt_to_file(
        "You are calm.\nSpeak in Chinese.",
        path=personas_file,
    )

    save_personas_to_file(
        [
            Persona(
                persona_id="persona-alex",
                name="Alex",
                avatar="A",
                base_prompt="Be direct.\nStay concise.",
            )
        ],
        path=personas_file,
    )

    assert load_communication_persona_prompt_from_file(personas_file) == (
        "You are calm.\nSpeak in Chinese."
    )
    personas = load_personas_from_file(personas_file)
    assert len(personas) == 1
    assert personas[0].name == "Alex"
    assert personas[0].base_prompt == "Be direct.\nStay concise."
