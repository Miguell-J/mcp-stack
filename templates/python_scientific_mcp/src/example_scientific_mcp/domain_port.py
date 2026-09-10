"""The library-facing boundary has no knowledge of MCP or stack infrastructure."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LibraryDescription:
    name: str
    version: str
    description: str


class DomainLibrary(Protocol):
    def describe(self) -> LibraryDescription: ...


class ExampleLibrary:
    """Runnable fixture. A real library is imported here, never into gateway code."""

    def describe(self) -> LibraryDescription:
        return LibraryDescription("example-library", "0.1.0", "Thin adapter fixture")
