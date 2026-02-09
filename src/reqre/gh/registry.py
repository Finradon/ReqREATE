"""Registry and definition models for Grasshopper evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

MISSING = object()


class MissingGhParameters(ValueError):
    """Raised when required Grasshopper inputs are missing."""

    def __init__(self, definition: str, missing: Iterable[str]) -> None:
        missing_list = sorted(set(missing))
        message = (
            f"Missing parameters for {definition}: "
            f"{', '.join(missing_list) if missing_list else 'unknown'}"
        )
        super().__init__(message)
        self.definition = definition
        self.missing = tuple(missing_list)


class UnknownGhDefinition(KeyError):
    """Raised when a Grasshopper definition is not registered."""

    def __init__(self, gh_file: str) -> None:
        super().__init__(f"No Grasshopper definition registered for {gh_file!r}.")
        self.gh_file = gh_file


def normalize_gh_path(path: str) -> str:
    """Normalize Grasshopper paths and map legacy gh/ to gh_samples/."""
    if not path:
        return path
    cleaned = path.replace("\\", "/").strip()
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if cleaned.startswith("gh/"):
        cleaned = "gh_samples/" + cleaned[len("gh/") :]
    return cleaned


@dataclass(frozen=True)
class GhInput:
    name: str
    aliases: tuple[str, ...] = ()
    default: Any = MISSING
    required: bool = True


ParamBuilder = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class GhDefinition:
    name: str
    gh_file: str
    inputs: tuple[GhInput, ...] = ()
    brep_output: str | None = None
    interface_outputs: tuple[str, ...] = ()
    extra_outputs: tuple[str, ...] = ()
    param_builder: ParamBuilder | None = None

    @property
    def normalized_gh_file(self) -> str:
        return normalize_gh_path(self.gh_file)


class GhRegistry:
    """Keeps track of available Grasshopper definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, GhDefinition] = {}

    def register(self, definition: GhDefinition) -> None:
        key = normalize_gh_path(definition.gh_file)
        self._definitions[key] = definition

    def get(self, gh_file: str) -> GhDefinition | None:
        return self._definitions.get(normalize_gh_path(gh_file))

    def require(self, gh_file: str) -> GhDefinition:
        definition = self.get(gh_file)
        if definition is None:
            raise UnknownGhDefinition(gh_file)
        return definition

    def all(self) -> list[GhDefinition]:
        return list(self._definitions.values())
