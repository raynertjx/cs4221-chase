# chase/entailment.py
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

from .models import Schema, DependencySet, Dependency, FD, MVD, TableauCell, TableauRow


# Result Container

@dataclass
class ChaseEntailmentResult:
    target: Dependency
    entailed: bool
    steps: List[Tuple[str, List[Dict[str, str]]]]

    @property
    def success(self) -> bool:
        return self.entailed

    def __str__(self) -> str:
        tag = "IS" if self.entailed else "is NOT"
        return f"{self.target} {tag} entailed ({len(self.steps)} steps)"


# Helper
# Serialise a list of TableauRow into plain dicts for snapshots.

def _tableau_to_dicts(rows: List[TableauRow], attrs: List[str]) -> List[Dict[str, str]]:
    return [{a: r.cells[a].symbol for a in attrs} for r in rows]


# Chase Entailment Algorithm
class ChaseEntailment:
    def __init__(self, schema: Schema, deps: DependencySet, target: Union[FD, MVD]) -> None:
        self.schema = schema
        self.deps = deps
        self.target = target

    def run(self) -> ChaseEntailmentResult:
        names = self.schema.names
        lhs_names = {a.name for a in self.target.lhs}

        # 1. Initialize Tableau
        # Row 0: Initialized distinguised variables α for all attributes
        row0 = TableauRow({a: TableauCell("α", True) for a in names})
        row1 = TableauRow({})
        for a in names:
            if a in lhs_names:
                row1[a] = TableauCell("α", True)
            else:
                row1[a] = TableauCell(f"{a.lower()}₁", False)

        rows = [row0, row1]

        steps: List[Tuple[str, List[Dict[str, str]]]] = []
        steps.append((f"Initialize for {self.target}", _tableau_to_dicts(rows, names)))

        changed = True
        while changed:
            changed = False
            
            # FD rule: equate symbols
            for fd in self.deps.fds:
                fd_lhs = [a.name for a in fd.lhs]
                fd_rhs = [a.name for a in fd.rhs]
                
                # check every pair of rows in the table
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

            # MVD rule: generate new rows
            for mvd in self.deps.mvds:
                mvd_lhs = [a.name for a in mvd.lhs]
                mvd_rhs = [a.name for a in mvd.rhs]

                mvd_changed = True

                while mvd_changed:
                    mvd_changed = False
                
                    for i in range(len(rows)):
                        for j in range(i+1, len(rows)):
                            # if rows match on LHS, swap RHS values
                            if not all(rows[i][a].symbol == rows[j][a].symbol for a in mvd_lhs):
                                continue
                            
                            for src_rhs, src_rest in [(j, i), (i, j)]:
                                new_row_data = {}
                                for a in names:
                                    if a in mvd_rhs:
                                        new_row_data[a] = rows[src_rhs][a]
                                    else:
                                        new_row_data[a] = rows[src_rest][a]
                                
                                new_row = TableauRow(new_row_data)
                                
                                # add if this specific combination doesn't exist yet
                                if not any(all(new_row[a].symbol == existing[a].symbol for a in names) for existing in rows):
                                    rows.append(new_row)
                                    steps.append((f"Apply MVD {mvd}", _tableau_to_dicts(rows, names)))
                                    mvd_changed = True
                                    changed = True

                        if mvd_changed: break
                    if mvd_changed: break

        # check if any row consist entirely of distinguished variables
        entailed = self._check_entailment(rows, names)

        tag = "✓ Entailed" if entailed else "✗ Not entailed"
        steps.append((tag, _tableau_to_dicts(rows, names)))

        return ChaseEntailmentResult(target=self.target, entailed=entailed, steps=steps)
    
    def _check_entailment(self, rows: List[TableauRow], attrs: List[str]) -> bool:
        lhs = [a.name for a in self.target.lhs]
        rhs = [a.name for a in self.target.rhs]

        if isinstance(self.target, FD):
            # For FDs, rows agreeing on LHS must agree on RHS
            for r in range(len(rows)):
                for s in range(r + 1, len(rows)):
                    if all(rows[r][a].symbol == rows[s][a].symbol for a in lhs):
                        if not all(rows[r][a].symbol == rows[s][a].symbol for a in rhs):
                            return False
            return True
        
        elif isinstance(self.target, MVD):
            # For MVDs, for rows agreeing on LHS, we must be able to find a swapped row 
            rest = [a for a in attrs if a not in lhs and a not in rhs]
            for r in range(len(rows)):
                for s in range(len(rows)):
                    if r == s: continue
                    if all(rows[r][a].symbol == rows[s][a].symbol for a in lhs):
                        # We need to find a row t with t agrees with r on LHS and RHS, and with s on the rest
                        needed = {}
                        for a in lhs:
                            needed[a] = rows[r][a].symbol
                        for a in rhs:
                            needed[a] = rows[r][a].symbol
                        for a in rest:
                            needed[a] = rows[s][a].symbol

                        if not any(all(rows[t][a].symbol == needed[a] for a in attrs) for t in range(len(rows))):
                            return False
            return True
        
        return False
    

