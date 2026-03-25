# web/app.py
# Flask web application for The Chase

import sys
import os
import json
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify

from chase import (
    Schema, FD, MVD, DependencySet, TableInstance,
    ClosureComputer, MinimalCoverComputer, CandidateKeyFinder, ProjectionComputer,
    ChaseLossless, ChaseTableValidator,
    FDDiscoverer, BenchmarkRunner,
)
from chase.entailment import ChaseEntailment

app = Flask(__name__, template_folder="templates", static_folder="static")


# global error handler

@app.errorhandler(Exception)
def handle_exception(e):
    """Catch any unhandled exception and return JSON instead of HTML."""
    return jsonify({"success": False, "error": f"{type(e).__name__}: {str(e)}"}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"success": False, "error": "Endpoint not found"}), 404


# helpers 

def parse_attrs(text: str) -> list[str]:
    return [a.strip().upper() for a in text.split(",") if a.strip()]


def parse_deps(text: str) -> DependencySet:
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    return DependencySet.from_strings(lines)


def parse_decomp(text: str) -> list[list[str]]:
    result = []
    for line in text.strip().splitlines():
        clean = line.replace("{", "").replace("}", "").strip()
        if clean:
            result.append([a.strip().upper() for a in clean.split(",") if a.strip()])
    return result


def parse_table(text: str, attr_names: list[str]) -> list[dict]:
    rows = []
    for line in text.strip().splitlines():
        vals = [v.strip() for v in line.split(",")]
        row = {attr_names[i]: vals[i] for i in range(min(len(attr_names), len(vals)))}
        rows.append(row)
    return rows


# routes 

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/closure", methods=["POST"])
def api_closure():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        target = parse_attrs(data["target"])
        schema = Schema(attrs)
        cc = ClosureComputer(schema, deps)
        result = cc.compute(target)
        return jsonify({
            "success": True,
            "input": result.input_names,
            "closure": result.closure_names,
            "is_superkey": result.is_superkey,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/entailment", methods=["POST"])
def api_entailment():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        schema = Schema(attrs)

        # Parse target — detect MVD (->>) vs FD (->)
        target_str = data["target"]
        if "->>" in target_str:
            parts = target_str.split("->>")
            lhs = [a.strip().upper() for a in parts[0].split(",") if a.strip()]
            rhs = [a.strip().upper() for a in parts[1].split(",") if a.strip()]
            target = MVD(lhs, rhs)
        else:
            parts = target_str.split("->")
            lhs = [a.strip().upper() for a in parts[0].split(",") if a.strip()]
            rhs = [a.strip().upper() for a in parts[1].split(",") if a.strip()]
            target = FD(lhs, rhs)

        result = ChaseEntailment(schema, deps, target).run()
        steps = [{"desc": desc, "tableau": tableau} for desc, tableau in result.steps]
        return jsonify({
            "success": True,
            "entailed": result.entailed,
            "steps": steps,
            "attrs": attrs,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/lossless", methods=["POST"])
def api_lossless():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        schema = Schema(attrs)
        decomp_lists = parse_decomp(data["decomp"])
        decomp = [Schema(d) for d in decomp_lists]

        result = ChaseLossless(schema, deps, decomp).run()
        steps = [{"desc": desc, "tableau": tableau} for desc, tableau in result.steps]
        return jsonify({
            "success": True,
            "lossless": result.lossless,
            "steps": steps,
            "attrs": attrs,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/mincover", methods=["POST"])
def api_mincover():
    try:
        data = request.json
        deps = parse_deps(data["fds"])
        result = MinimalCoverComputer(deps).compute()
        steps = []
        for desc, step_deps in result.steps:
            steps.append({
                "desc": desc,
                "fds": [str(fd) for fd in step_deps],
            })
        return jsonify({
            "success": True,
            "result": [str(fd) for fd in result.result],
            "steps": steps,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/keys", methods=["POST"])
def api_keys():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        schema = Schema(attrs)
        result = CandidateKeyFinder(schema, deps).compute()
        return jsonify({
            "success": True,
            "keys": result.key_names,
            "prime_attributes": sorted(a.name for a in result.prime_attributes),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/table_check", methods=["POST"])
def api_table_check():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        schema = Schema(attrs)
        rows = parse_table(data["table"], attrs)
        table = TableInstance(schema, rows)

        result = ChaseTableValidator(table, deps).run()
        validations = []
        for v in result.validations:
            validations.append({
                "dep": str(v.dependency),
                "satisfied": v.satisfied,
                "violations": [{"row1": r1, "row2": r2} for r1, r2 in v.violations],
            })
        return jsonify({
            "success": True,
            "all_satisfied": result.all_satisfied,
            "validations": validations,
            "table": rows,
            "attrs": attrs,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/discover", methods=["POST"])
def api_discover():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        schema = Schema(attrs)
        rows = parse_table(data["table"], attrs)
        table = TableInstance(schema, rows)

        result = FDDiscoverer(table).run()
        return jsonify({
            "success": True,
            "fds": [str(fd) for fd in result.discovered_fds],
            "count": len(result.discovered_fds),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/benchmark", methods=["POST"])
def api_benchmark():
    try:
        data = request.json
        attrs = parse_attrs(data.get("attrs", "A,B,C,D,E,F"))
        sizes = data.get("sizes", [5, 10, 20, 40])
        runner = BenchmarkRunner(
            attr_names=attrs,
            fd_sizes=sizes,
            iterations=20,
            seed=42,
        )
        result = runner.run_all()
        entries = []
        for e in result.entries:
            entries.append({
                "label": e.label,
                "operation": e.operation,
                "num_fds": e.num_fds,
                "num_attrs": e.num_attrs,
                "time_ms": round(e.time_ms, 3),
            })

        ablation = runner.run_ablation()
        ablation_entries = []
        for e in ablation.entries:
            ablation_entries.append({
                "label": e.label,
                "operation": e.operation,
                "num_fds": e.num_fds,
                "time_ms": round(e.time_ms, 3),
            })

        return jsonify({
            "success": True,
            "entries": entries,
            "ablation": ablation_entries,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n  The Chase — CS4221 Database Tuning")
    print(f"  Running at http://localhost:{port}\n")
    app.run(debug=True, host="0.0.0.0", port=port)