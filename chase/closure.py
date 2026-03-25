# chase/closure.py
from dataclasses import dataclass
from typing import FrozenSet, List, Set, Union
from .models import Attribute, DependencySet, Schema, FD

@dataclass
class ClosureResult:
    """Result of an attribute-closure computation."""
    input_attrs: FrozenSet[Attribute]
    closure: FrozenSet[Attribute]
    is_superkey: bool

    @property
    def input_names(self) -> List[str]:
        return sorted(a.name for a in self.input_attrs)

    @property
    def closure_names(self) -> List[str]:
        return sorted(a.name for a in self.closure)

    def __str__(self) -> str:
        tag = " [superkey]" if self.is_superkey else ""
        return (
            f"{{{', '.join(self.input_names)}}}⁺ = "
            f"{{{', '.join(self.closure_names)}}}{tag}"
        )


class ClosureComputer:
    """
    Compute the attribute closure X⁺ under a set of FDs.
    """

    def __init__(self, schema: Schema, deps: DependencySet) -> None:
        self.schema = schema
        self.deps = deps

    def compute(
        self, attrs: Union[FrozenSet[Attribute], Set[str], List[str]]
    ) -> ClosureResult:
        """Return the closure of *attrs* under the stored FDs."""
        # Normalise input
        if isinstance(attrs, (list, set)) and attrs and isinstance(next(iter(attrs)), str):
            seed = frozenset(Attribute(a) for a in attrs)
        else:
            seed = frozenset(attrs)  # type: ignore

        closure = set(seed)
        changed = True
        while changed:
            changed = False
            for fd in self.deps.fds:
                if fd.lhs <= closure and not fd.rhs <= closure:
                    closure |= fd.rhs
                    changed = True

        frozen = frozenset(closure)
        return ClosureResult(
            input_attrs=seed,
            closure=frozen,
            is_superkey=(frozen >= self.schema.attribute_set),
        )

    @staticmethod
    def closure_of(attrs: FrozenSet[Attribute], fds: List[FD]) -> FrozenSet[Attribute]:
        """Stateless helper — no Schema needed."""
        closure = set(attrs)
        changed = True
        while changed:
            changed = False
            for fd in fds:
                if fd.lhs <= closure and not fd.rhs <= closure:
                    closure |= fd.rhs
                    changed = True
        return frozenset(closure)