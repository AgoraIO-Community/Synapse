from __future__ import annotations

from newbro.communication.persona_pool import (
    load_personas_from_file,
    save_personas_to_file,
)
from newbro.protocol import Persona


def test_save_personas_writes_only_worker_personas(tmp_path):
    personas_file = tmp_path / "personas.yaml"

    save_personas_to_file(
        [
            Persona(
                persona_id="persona-alex",
                name="Alex",
                avatar="A",
                base_prompt="Be direct.\nStay concise.",
                executor_node_id="node-1",
            )
        ],
        path=personas_file,
    )

    assert "communication_persona_prompt" not in personas_file.read_text(encoding="utf-8")
    personas = load_personas_from_file(personas_file)
    assert len(personas) == 1
    assert personas[0].persona_id == "persona-alex"
    assert personas[0].name == "Alex"
    assert personas[0].base_prompt == "Be direct.\nStay concise."
    assert personas[0].executor_node_id == "node-1"
    assert personas[0].bro_detail_session_id


def test_load_legacy_persona_without_bro_detail_session_id_uses_stable_generation(tmp_path):
    personas_file = tmp_path / "personas.yaml"
    personas_file.write_text(
        "\n".join(
            [
                'communication_persona_prompt: ""',
                "personas:",
                '  - name: "Alex"',
                '    persona_id: "persona-alex"',
                '    avatar: "A"',
                '    base_prompt: "Be direct."',
                '    executor_node_id: "node-1"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    first = load_personas_from_file(personas_file)
    second = load_personas_from_file(personas_file)

    assert first[0].bro_detail_session_id == "bro-detail-persona-alex"
    assert second[0].bro_detail_session_id == first[0].bro_detail_session_id
