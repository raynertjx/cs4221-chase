"""
chase/chase.py
──────────────
Chase algorithm implementations.

Classes
-------
ChaseEntailment     – 2-row Chase for FD entailment testing
ChaseLossless       – n-row Chase for lossless-join decomposition
ChaseTableValidator – validate FDs/MVDs against a concrete table instance

Each class follows the pattern:
    result = ChaseXxx(schema, deps, ...).run()
    result.success     → bool
    result.steps       → list of (description, tableau_snapshot)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    Attribute,
    Dependency,
    DependencySet,
    FD,
    MVD,
    Schema,
    TableauCell,
    TableauRow,
    Tableau,
    TableInstance,
)


# ── Result containers ────────────────────────────────────────────────────────

@dataclass
class ChaseEntailmentResult:
    target: FD
    entailed: bool
    steps: List[Tuple[str, List[Dict[str, str]]]]

    @property
    def success(self) -> bool:
        return self.entailed

    def __str__(self) -> str:
        tag = "IS" if self.entailed else "is NOT"
        return f"{self.target} {tag} entailed ({len(self.steps)} steps)"


@dataclass
class ChaseLosslessResult:
    decomposition: List[Schema]
    lossless: bool
    steps: List[Tuple[str, List[Dict[str, str]]]]

    @property
    def success(self) -> bool:
        return self.lossless

    def __str__(self) -> str:
        tag = "IS" if self.lossless else "is NOT"
        dec = ", ".join(str(s) for s in self.decomposition)
        return f"Decomposition [{dec}] {tag} lossless ({len(self.steps)} steps)"


@dataclass
class FDValidation:
    dependency: Dependency
    satisfied: bool
    violations: List[Tuple[int, int]]  # pairs of row indices

    def __str__(self) -> str:
        if self.satisfied:
            return f"  ✓ {self.dependency}"
        return f"  ✗ {self.dependency}  ({len(self.violations)} violations)"


@dataclass
class TableValidationResult:
    validations: List[FDValidation]

    @property
    def all_satisfied(self) -> bool:
        return all(v.satisfied for v in self.validations)

    def __str__(self) -> str:
        lines = ["Table Validation:"]
        for v in self.validations:
            lines.append(str(v))
        return "\n".join(lines)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _tableau_to_dicts(rows: List[TableauRow], attrs: List[str]) -> List[Dict[str, str]]:
    """Serialise a list of TableauRow into plain dicts for snapshots."""
    return [{a: r.cells[a].symbol for a in attrs} for r in rows]


# ── ChaseEntailment ──────────────────────────────────────────────────────────

class ChaseEntailment:
    """
    Chase test for FD entailment:  does  Σ ⊨ X → Y ?

    Builds a 2-row tableau where rows agree on X and differ elsewhere,
    then repeatedly applies FDs in Σ as equating rules.  If the rows
    end up agreeing on Y, the FD is entailed.

    Parameters
    ----------
    schema : Schema
    deps   : DependencySet   (only FDs used)
    target : FD              (the dependency to test)
    """

    def __init__(self, schema: Schema, deps: DependencySet, target: FD) -> None:
        self.schema = schema
        self.deps = deps
        self.target = target

    def run(self) -> ChaseEntailmentResult:
        names = self.schema.names
        lhs_names = {a.name for a in self.target.lhs}

        # Build initial 2-row tableau
        row0, row1 = TableauRow({}), TableauRow({})
        for a in names:
            row0[a] = TableauCell(f"a_{a}", distinguished=True)
            if a in lhs_names:
                row1[a] = TableauCell(f"a_{a}", distinguished=True)
            else:
                row1[a] = TableauCell(f"b_{a}", distinguished=False)

        rows = [row0, row1]
        steps: List[Tuple[str, List[Dict[str, str]]]] = []
        steps.append((
            f"Initialize for {self.target}",
            _tableau_to_dicts(rows, names),
        ))

        changed = True
        iterations = 0
        while changed and iterations < 100:
            changed = False
            iterations += 1
            for fd in self.deps.fds:
                fd_lhs = [a.name for a in fd.lhs]
                fd_rhs = [a.name for a in fd.rhs]

                # Check if rows agree on LHS
                if all(rows[0][a].symbol == rows[1][a].symbol for a in fd_lhs):
                    for a in fd_rhs:
                        if rows[0][a].symbol != rows[1][a].symbol:
                            # Equate: prefer distinguished
                            if rows[0][a].distinguished:
                                rows[1][a] = TableauCell(rows[0][a].symbol, True)
                            elif rows[1][a].distinguished:
                                rows[0][a] = TableauCell(rows[1][a].symbol, True)
                            else:
                                rows[1][a] = TableauCell(rows[0][a].symbol, rows[0][a].distinguished)
                            changed = True
                    if changed:
                        steps.append((
                            f"Apply {fd}",
                            _tableau_to_dicts(rows, names),
                        ))
                        break  # restart scan

        rhs_names = {a.name for a in self.target.rhs}
        entailed = all(rows[0][a].symbol == rows[1][a].symbol for a in rhs_names)
        tag = "✓ Entailed" if entailed else "✗ Not entailed"
        steps.append((tag, _tableau_to_dicts(rows, names)))

        return ChaseEntailmentResult(
            target=self.target,
            entailed=entailed,
            steps=steps,
        )


# ── ChaseLossless ────────────────────────────────────────────────────────────

class ChaseLossless:
    """
    Chase test for lossless-join decomposition.

    Builds an n-row tableau (one row per relation in the decomposition),
    then applies FD equating rules and MVD row-generation rules.
    If any row becomes all-distinguished, the decomposition is lossless.

    Parameters
    ----------
    schema        : Schema
    deps          : DependencySet  (FDs and MVDs)
    decomposition : list of Schema (the relations in the decomposition)
    """

    def __init__(
        self,
        schema: Schema,
        deps: DependencySet,
        decomposition: List[Schema],
    ) -> None:
        self.schema = schema
        self.deps = deps
        self.decomposition = decomposition

    def run(self) -> ChaseLosslessResult:
        names = self.schema.names

        # Build initial tableau
        rows: List[TableauRow] = []
        for i, rel in enumerate(self.decomposition):
            rel_names = set(rel.names)
            row = TableauRow({})
            for a in names:
                if a in rel_names:
                    row[a] = TableauCell(f"a_{a}", distinguished=True)
                else:
                    row[a] = TableauCell(f"b_{i}{a}", distinguished=False)
            rows.append(row)

        steps: List[Tuple[str, List[Dict[str, str]]]] = []
        dec_str = ", ".join(str(s) for s in self.decomposition)
        steps.append((f"Initialize for [{dec_str}]", _tableau_to_dicts(rows, names)))

        changed = True
        iterations = 0
        while changed and iterations < 200:
            changed = False
            iterations += 1

            # ── FD equating rules ──
            for fd in self.deps.fds:
                fd_lhs = [a.name for a in fd.lhs]
                fd_rhs = [a.name for a in fd.rhs]

                groups: Dict[Tuple[str, ...], List[int]] = {}
                for idx, r in enumerate(rows):
                    key = tuple(r[a].symbol for a in fd_lhs)
                    groups.setdefault(key, []).append(idx)

                fd_changed = False
                for key, idxs in groups.items():
                    if len(idxs) < 2:
                        continue
                    for a in fd_rhs:
                        vals = [rows[i][a] for i in idxs]
                        best = next((v for v in vals if v.distinguished), vals[0])
                        for i in idxs:
                            if rows[i][a].symbol != best.symbol:
                                rows[i][a] = TableauCell(best.symbol, best.distinguished)
                                changed = True
                                fd_changed = True

                if fd_changed:
                    steps.append((f"Apply {fd}", _tableau_to_dicts(rows, names)))

            # ── MVD row-generation rules ──
            for mvd in self.deps.mvds:
                mvd_lhs = [a.name for a in mvd.lhs]
                mvd_rhs = [a.name for a in mvd.rhs]
                rest = [a for a in names if a not in mvd_lhs and a not in mvd_rhs]

                groups: Dict[Tuple[str, ...], List[int]] = {}
                for idx, r in enumerate(rows):
                    key = tuple(r[a].symbol for a in mvd_lhs)
                    groups.setdefault(key, []).append(idx)

                new_rows: List[TableauRow] = []
                for key, idxs in groups.items():
                    if len(idxs) < 2:
                        continue
                    for x in range(len(idxs)):
                        for y in range(x + 1, len(idxs)):
                            for src_rhs, src_rest in [(x, y), (y, x)]:
                                nr = TableauRow({})
                                for a in mvd_lhs:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rhs]][a].symbol,
                                        rows[idxs[src_rhs]][a].distinguished,
                                    )
                                for a in mvd_rhs:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rhs]][a].symbol,
                                        rows[idxs[src_rhs]][a].distinguished,
                                    )
                                for a in rest:
                                    nr[a] = TableauCell(
                                        rows[idxs[src_rest]][a].symbol,
                                        rows[idxs[src_rest]][a].distinguished,
                                    )
                                # Check duplicate
                                sig = tuple(nr[a].symbol for a in names)
                                if not any(
                                    tuple(r[a].symbol for a in names) == sig
                                    for r in rows + new_rows
                                ):
                                    new_rows.append(nr)

                if new_rows:
                    rows.extend(new_rows)
                    changed = True
                    steps.append((
                        f"Apply {mvd} (+{len(new_rows)} rows)",
                        _tableau_to_dicts(rows, names),
                    ))

            # Early exit
            if any(
                all(r[a].distinguished for a in names) for r in rows
            ):
                break

        lossless = any(all(r[a].distinguished for a in names) for r in rows)
        tag = "✓ Lossless" if lossless else "✗ Not lossless"
        steps.append((tag, _tableau_to_dicts(rows, names)))

        return ChaseLosslessResult(
            decomposition=self.decomposition,
            lossless=lossless,
            steps=steps,
        )


# ── ChaseTableValidator ─────────────────────────────────────────────────────

class ChaseTableValidator:
    """
    Validate FDs and MVDs against a concrete table instance.

    For each dependency, every pair of rows is checked:
      FD  X→Y : rows agreeing on X must agree on Y
      MVD X↠Y : if rows agree on X, a "swapped" row must exist

    Parameters
    ----------
    table : TableInstance
    deps  : DependencySet
    """

    def __init__(self, table: TableInstance, deps: DependencySet) -> None:
        self.table = table
        self.deps = deps

    def run(self) -> TableValidationResult:
        validations: List[FDValidation] = []
        all_names = self.table.schema.names
        rows = self.table.rows

        for dep in self.deps:
            violations: List[Tuple[int, int]] = []

            if isinstance(dep, FD):
                lhs = [a.name for a in dep.lhs]
                rhs = [a.name for a in dep.rhs]
                for i in range(len(rows)):
                    for j in range(i + 1, len(rows)):
                        if all(rows[i][a] == rows[j][a] for a in lhs):
                            if not all(rows[i][a] == rows[j][a] for a in rhs):
                                violations.append((i, j))

            elif isinstance(dep, MVD):
                lhs = [a.name for a in dep.lhs]
                rhs = [a.name for a in dep.rhs]
                rest = [a for a in all_names if a not in lhs and a not in rhs]
                for i in range(len(rows)):
                    for j in range(i + 1, len(rows)):
                        if all(rows[i][a] == rows[j][a] for a in lhs):
                            needed = {}
                            for a in lhs:
                                needed[a] = rows[i][a]
                            for a in rhs:
                                needed[a] = rows[i][a]
                            for a in rest:
                                needed[a] = rows[j][a]
                            if not any(
                                all(r[a] == needed[a] for a in all_names)
                                for r in rows
                            ):
                                violations.append((i, j))

            validations.append(FDValidation(
                dependency=dep,
                satisfied=len(violations) == 0,
                violations=violations,
            ))

        return TableValidationResult(validations=validations)
