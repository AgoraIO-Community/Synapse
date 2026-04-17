"""Task-level persona pool.

Each task gets a unique persona assigned at creation time.
Personas are recycled when tasks reach terminal states.
"""

from __future__ import annotations

from dataclasses import dataclass

# Pre-defined persona pool. Avatar is an emoji for now;
# the frontend can map these to pixel-art sprites.
_PERSONAS = [
    ("Mochi", "🐕", "An energetic shiba inu"),
    ("Pixel", "🐱", "A curious calico cat"),
    ("Biscuit", "🐶", "A loyal golden retriever"),
    ("Nori", "🐾", "A clever black cat"),
    ("Tofu", "🐰", "A speedy white rabbit"),
    ("Mango", "🦊", "A crafty little fox"),
    ("Pudding", "🐻", "A steady brown bear"),
    ("Sesame", "🐧", "A focused penguin"),
    ("Waffle", "🐹", "A cheerful hamster"),
    ("Dumpling", "🐼", "A calm panda"),
]


@dataclass(slots=True, frozen=True)
class TaskPersona:
    name: str
    avatar: str
    tagline: str


PERSONA_POOL: list[TaskPersona] = [
    TaskPersona(name=n, avatar=a, tagline=t) for n, a, t in _PERSONAS
]


class PersonaAssigner:
    """Assigns personas to tasks from a fixed pool, recycling on terminal tasks."""

    def __init__(self, pool: list[TaskPersona] | None = None) -> None:
        self._pool = list(pool or PERSONA_POOL)
        self._assigned: dict[str, TaskPersona] = {}  # task_id -> persona

    def assign(self, task_id: str) -> TaskPersona:
        """Assign a persona to a task. Returns existing if already assigned."""
        if task_id in self._assigned:
            return self._assigned[task_id]
        used = set(id(p) for p in self._assigned.values())
        for persona in self._pool:
            if id(persona) not in used:
                self._assigned[task_id] = persona
                return persona
        # Pool exhausted — wrap around with index.
        idx = len(self._assigned) % len(self._pool)
        persona = self._pool[idx]
        self._assigned[task_id] = persona
        return persona

    def get(self, task_id: str) -> TaskPersona | None:
        return self._assigned.get(task_id)

    def release(self, task_id: str) -> None:
        """Release a persona back to the pool (task completed/cancelled/failed)."""
        self._assigned.pop(task_id, None)

    def to_metadata(self, persona: TaskPersona) -> dict[str, str]:
        return {"persona_name": persona.name, "persona_avatar": persona.avatar, "persona_tagline": persona.tagline}
