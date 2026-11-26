from typing import Any

from .admin import AdminClient
from .fix import Applied, Plan, apply_plan, publish

CLONE_NAME = "flagpact-rehearsal"


class Clone:
    def __init__(self, source: AdminClient, scoped: AdminClient, key: str) -> None:
        self.source = source
        self.scoped = scoped
        self.key = key
        self.applied: Applied | None = None

    @classmethod
    def create(cls, source: AdminClient) -> "Clone":
        key = source.clone_environment(CLONE_NAME)
        try:
            scoped = source.scoped(key, source.create_server_key(key, CLONE_NAME))
        except Exception:
            source.delete_environment(key)
            raise
        return cls(source, scoped, key)

    def apply(self, plan: Plan) -> None:
        self.applied = apply_plan(self.scoped, plan)

    def publish(self, value: dict[str, Any]) -> None:
        if self.applied is not None:
            publish(self.scoped, self.applied, value)

    def probe(self, flag: str, version: str | None) -> dict[str, Any]:
        return self.scoped.probe(flag, version)

    def cleanup(self) -> None:
        try:
            self.source.delete_environment(self.key)
        finally:
            if self.applied is not None and self.applied.created_segment:
                self.source.delete_segment(self.applied.segment_id)
