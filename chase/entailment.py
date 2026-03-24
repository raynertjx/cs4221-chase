# chase/entailment.py
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models import Schema, DependencySet, FD, TableauCell, TableauRow


# ── Result Container ─────────────────────────────────────────────────────────

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


# ── Helper ───────────────────────────────────────────────────────────────────

def _tableau_to_dicts(rows: List[TableauRow], attrs: List[str]) -> List[Dict[str, str]]:
    """Serialise a list of TableauRow into plain dicts for snapshots."""
    return [{a: r.cells[a].symbol for a in attrs} for r in rows]


# ── ChaseEntailment ──────────────────────────────────────────────────────────
class ChaseEntailment:
    """
    Chase test for Dependency entailment (FDs and MVDs).
    """

    def __init__(self, schema: Schema, deps: DependencySet, target: FD) -> None:
        self.schema = schema
        self.deps = deps
        self.target = target

    def run(self) -> ChaseEntailmentResult:
        names = self.schema.names
        lhs_names = {a.name for a in self.target.lhs}

        # 1. Initialize Tableau
        row0 = TableauRow({a: TableauCell(f"a_{a}", True) for a in names})
        row1 = TableauRow({})
        for a in names:
            if a in lhs_names:
                row1[a] = TableauCell(f"a_{a}", True)
            else:
                row1[a] = TableauCell(f"b_{a}", False)

        rows = [row0, row1]
        steps: List[Tuple[str, List[Dict[str, str]]]] = []
        steps.append((f"Initialize for {self.target}", _tableau_to_dicts(rows, names)))

        changed = True
        while changed:
            changed = False
            
            # --- FD Rule: Equate Symbols ---
            for fd in self.deps.fds:
                fd_lhs = [a.name for a in fd.lhs]
                fd_rhs = [a.name for a in fd.rhs]
                
                # Check every pair of rows in the growing tableau
                for i in range(len(rows)):
                    for j in range(i + 1, len(rows)):
                        if all(rows[i][a].symbol == rows[j][a].symbol for a in fd_lhs):
                            for a in fd_rhs:
                                if rows[i][a].symbol != rows[j][a].symbol:
                                    # Equate values, preferring distinguished (a_x) symbols
                                    new_val = rows[i][a] if rows[i][a].distinguished else rows[j][a]
                                    rows[i][a] = new_val
                                    rows[j][a] = new_val
                                    changed = True
                            if changed:
                                steps.append((f"Apply FD {fd}", _tableau_to_dicts(rows, names)))
                                break
                    if changed: break
                if changed: break

            if changed: continue # Prioritise FD applications

            # --- MVD Rule: Generate New Rows ---
            for mvd in self.deps.mvds:
                mvd_lhs = [a.name for a in mvd.lhs]
                mvd_rhs = [a.name for a in mvd.rhs]
                
                for i in range(len(rows)):
                    for j in range(len(rows)):
                        if i == j: continue
                        
                        # If rows match on LHS, we can swap RHS values
                        if all(rows[i][a].symbol == rows[j][a].symbol for a in mvd_lhs):
                            # Create a new row: take Y from row i, and everything else from row j
                            new_row_data = {}
                            for a in names:
                                if a in mvd_rhs:
                                    new_row_data[a] = rows[i][a]
                                else:
                                    new_row_data[a] = rows[j][a]
                            
                            new_row = TableauRow(new_row_data)
                            
                            # Add if this specific combination doesn't exist yet
                            if not any(all(new_row[a].symbol == existing[a].symbol for a in names) for existing in rows):
                                rows.append(new_row)
                                steps.append((f"Apply MVD {mvd}", _tableau_to_dicts(rows, names)))
                                changed = True
                                break
                    if changed: break
                if changed: break

        # 2. Final check: Does any row consist entirely of distinguished symbols for the target RHS?
        rhs_names = {a.name for a in self.target.rhs}
        entailed = any(all(r[a].distinguished for a in rhs_names) for r in rows[1:])
        
        tag = "✓ Entailed" if entailed else "✗ Not entailed"
        steps.append((tag, _tableau_to_dicts(rows, names)))

        return ChaseEntailmentResult(target=self.target, entailed=entailed, steps=steps)