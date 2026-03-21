"""
chase/models.py
───────────────
Core domain objects for the Chase algorithm toolkit.

Classes
-------
Attribute       – single named attribute
Schema          – ordered collection of attributes
FD              – functional dependency  X → Y
MVD             – multivalued dependency X ↠ Y
DependencySet   – container for mixed FD / MVD collections
TableInstance   – concrete rows over a schema (for validation)
TableauRow      – one row inside a Chase tableau
Tableau         – full Chase tableau with display helpers
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import (
    Dict,
    FrozenSet,
    Iterable,
    Iterator,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)


# ── Attribute ────────────────────────────────────────────────────────────────

@dataclass(frozen=True, order=True)
class Attribute:
    """Immutable, hashable wrapper around an attribute name."""

    name: str

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


# ── Schema ───────────────────────────────────────────────────────────────────

class Schema:
    """
    Ordered collection of unique attributes that defines a relation schema.

    Parameters
    ----------
    attrs : iterable of str or Attribute
    """

    def __init__(self, attrs: Iterable[Union[str, Attribute]]) -> None:
        seen: Set[str] = set()
        self._attrs: List[Attribute] = []
        for a in attrs:
            attr = Attribute(a) if isinstance(a, str) else a
            if attr.name not in seen:
                self._attrs.append(attr)
                seen.add(attr.name)
        self._set: FrozenSet[Attribute] = frozenset(self._attrs)

    # -- Container protocol ---------------------------------------------------

    def __contains__(self, item: Union[str, Attribute]) -> bool:
        if isinstance(item, str):
            item = Attribute(item)
        return item in self._set

    def __iter__(self) -> Iterator[Attribute]:
        return iter(self._attrs)

    def __len__(self) -> int:
        return len(self._attrs)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Schema):
            return self._set == other._set
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._set)

    # -- Helpers --------------------------------------------------------------

    @property
    def attribute_set(self) -> FrozenSet[Attribute]:
        return self._set

    @property
    def names(self) -> List[str]:
        return [a.name for a in self._attrs]

    def subset(self, names: Iterable[str]) -> Schema:
        return Schema([n for n in names if n in [a.name for a in self._attrs]])

    def __repr__(self) -> str:
        return f"Schema({', '.join(self.names)})"

    def __str__(self) -> str:
        return "{" + ", ".join(self.names) + "}"


# ── Dependency base class ────────────────────────────────────────────────────

class Dependency:
    """Abstract base for FD and MVD."""

    def __init__(
        self,
        lhs: Iterable[Union[str, Attribute]],
        rhs: Iterable[Union[str, Attribute]],
    ) -> None:
        self.lhs: FrozenSet[Attribute] = frozenset(
            Attribute(a) if isinstance(a, str) else a for a in lhs
        )
        self.rhs: FrozenSet[Attribute] = frozenset(
            Attribute(a) if isinstance(a, str) else a for a in rhs
        )

    @property
    def lhs_names(self) -> List[str]:
        return sorted(a.name for a in self.lhs)

    @property
    def rhs_names(self) -> List[str]:
        return sorted(a.name for a in self.rhs)

    @property
    def all_attributes(self) -> FrozenSet[Attribute]:
        return self.lhs | self.rhs

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return self.lhs == other.lhs and self.rhs == other.rhs  # type: ignore

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.lhs, self.rhs))


class FD(Dependency):
    """Functional dependency  X → Y."""

    @property
    def arrow(self) -> str:
        return "→"

    def __repr__(self) -> str:
        return f"FD({','.join(self.lhs_names)} → {','.join(self.rhs_names)})"

    def __str__(self) -> str:
        return f"{','.join(self.lhs_names)} → {','.join(self.rhs_names)}"


class MVD(Dependency):
    """Multivalued dependency  X ↠ Y."""

    @property
    def arrow(self) -> str:
        return "↠"

    def __repr__(self) -> str:
        return f"MVD({','.join(self.lhs_names)} ↠ {','.join(self.rhs_names)})"

    def __str__(self) -> str:
        return f"{','.join(self.lhs_names)} ↠ {','.join(self.rhs_names)}"


# ── DependencySet ────────────────────────────────────────────────────────────

class DependencySet:
    """
    An ordered, deduplicated collection of FDs and MVDs.

    Supports iteration, membership tests, and convenient factory methods.
    """

    def __init__(self, deps: Optional[Iterable[Dependency]] = None) -> None:
        self._deps: List[Dependency] = []
        self._set: Set[Dependency] = set()
        if deps:
            for d in deps:
                self.add(d)

    def add(self, dep: Dependency) -> None:
        if dep not in self._set:
            self._deps.append(dep)
            self._set.add(dep)

    @property
    def fds(self) -> List[FD]:
        return [d for d in self._deps if isinstance(d, FD)]

    @property
    def mvds(self) -> List[MVD]:
        return [d for d in self._deps if isinstance(d, MVD)]

    def __iter__(self) -> Iterator[Dependency]:
        return iter(self._deps)

    def __len__(self) -> int:
        return len(self._deps)

    def __contains__(self, dep: Dependency) -> bool:
        return dep in self._set

    def copy(self) -> DependencySet:
        return DependencySet(list(self._deps))

    def __repr__(self) -> str:
        return f"DependencySet({len(self._deps)} deps)"

    def __str__(self) -> str:
        return "\n".join(str(d) for d in self._deps)

    # -- Factory helpers (accept pratik2358 format) ---------------------------

    @classmethod
    def from_tuples(cls, tuples: List[Tuple[set, set]], mvd: bool = False) -> DependencySet:
        """
        Build from list of (lhs_set, rhs_set) tuples.
        Compatible with pratik2358/fucntional_dep format:
            [({'A'}, {'B', 'C'}), ({'B', 'C'}, {'A', 'D'})]
        """
        ds = cls()
        klass = MVD if mvd else FD
        for lhs, rhs in tuples:
            ds.add(klass(lhs, rhs))
        return ds

    @classmethod
    def from_strings(cls, lines: Iterable[str]) -> DependencySet:
        """
        Parse text lines like  'A,B -> C'  or  'A ->> B,C'.
        """
        ds = cls()
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if "->>" in line:
                parts = line.split("->>")
                lhs = [s.strip() for s in parts[0].split(",") if s.strip()]
                rhs = [s.strip() for s in parts[1].split(",") if s.strip()]
                ds.add(MVD(lhs, rhs))
            elif "->" in line:
                parts = line.split("->")
                lhs = [s.strip() for s in parts[0].split(",") if s.strip()]
                rhs = [s.strip() for s in parts[1].split(",") if s.strip()]
                ds.add(FD(lhs, rhs))
        return ds


# ── TableInstance ────────────────────────────────────────────────────────────

class TableInstance:
    """
    A concrete table: a list of rows (dicts mapping attribute name → value).

    Parameters
    ----------
    schema : Schema
    rows   : list of dicts  {attr_name: value}
    """

    def __init__(self, schema: Schema, rows: List[Dict[str, str]]) -> None:
        self.schema = schema
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Dict[str, str]]:
        return iter(self.rows)

    @classmethod
    def from_csv_text(cls, schema: Schema, text: str) -> TableInstance:
        """
        Parse rows from comma-separated text lines.
        Each line maps positionally to schema attributes.
        """
        rows: List[Dict[str, str]] = []
        names = schema.names
        for line in text.strip().splitlines():
            vals = [v.strip() for v in line.split(",")]
            row = {names[i]: vals[i] for i in range(min(len(names), len(vals)))}
            rows.append(row)
        return cls(schema, rows)

    @classmethod
    def from_dataframe(cls, df) -> TableInstance:
        """Build from a pandas DataFrame (for pratik2358 compatibility)."""
        schema = Schema(list(df.columns))
        rows = df.to_dict("records")
        return cls(schema, [{str(k): str(v) for k, v in r.items()} for r in rows])

    def __repr__(self) -> str:
        return f"TableInstance(cols={self.schema.names}, rows={len(self.rows)})"


# ── Tableau ──────────────────────────────────────────────────────────────────

@dataclass
class TableauCell:
    """
    A single cell in a Chase tableau.
    Distinguished (a-value) cells have  distinguished=True.
    """
    symbol: str
    distinguished: bool = False

    def __repr__(self) -> str:
        return self.symbol


class TableauRow:
    """One row of a Chase tableau."""

    def __init__(self, cells: Dict[str, TableauCell]) -> None:
        self.cells = cells

    def __getitem__(self, attr: str) -> TableauCell:
        return self.cells[attr]

    def __setitem__(self, attr: str, val: TableauCell) -> None:
        self.cells[attr] = val

    def is_all_distinguished(self, attrs: Iterable[str]) -> bool:
        return all(self.cells[a].distinguished for a in attrs)

    def copy(self) -> TableauRow:
        return TableauRow({k: TableauCell(v.symbol, v.distinguished) for k, v in self.cells.items()})

    def values_tuple(self, attrs: List[str]) -> Tuple[str, ...]:
        return tuple(self.cells[a].symbol for a in attrs)

    def __repr__(self) -> str:
        return " | ".join(f"{k}={v}" for k, v in self.cells.items())


class Tableau:
    """
    Full Chase tableau with snapshot capability for step-by-step replay.
    """

    def __init__(self, schema: Schema) -> None:
        self.schema = schema
        self.rows: List[TableauRow] = []
        self._snapshots: List[Tuple[str, List[TableauRow]]] = []

    def add_row(self, row: TableauRow) -> None:
        self.rows.append(row)

    def snapshot(self, description: str) -> None:
        """Save a frozen copy of the current tableau state with a label."""
        frozen = [r.copy() for r in self.rows]
        self._snapshots.append((description, frozen))

    @property
    def steps(self) -> List[Tuple[str, List[TableauRow]]]:
        return list(self._snapshots)

    def has_distinguished_row(self) -> bool:
        names = self.schema.names
        return any(r.is_all_distinguished(names) for r in self.rows)

    def __repr__(self) -> str:
        header = " | ".join(self.schema.names)
        lines = [header, "-" * len(header)]
        for r in self.rows:
            lines.append(" | ".join(str(r.cells[a]) for a in self.schema.names))
        return "\n".join(lines)
