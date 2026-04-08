# web/app.py
# Flask web application for The Chase

import sys
import os
import json
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify

from chase import (
    Schema, FD, MVD, DependencySet, TableInstance,
    ClosureComputer, MinimalCoverComputer, CandidateKeyFinder, ProjectionComputer,
    ChaseLossless, ChaseTableValidator,
    FDDiscoverer, BenchmarkRunner,
    BCNFDecomposer, ThreeNFDecomposer,
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


def parse_target_dep(text: str):
    target_str = text.strip()
    if "->>" in target_str:
        parts = target_str.split("->>")
        lhs = [a.strip().upper() for a in parts[0].split(",") if a.strip()]
        rhs = [a.strip().upper() for a in parts[1].split(",") if a.strip()]
        return MVD(lhs, rhs)
    parts = target_str.split("->")
    lhs = [a.strip().upper() for a in parts[0].split(",") if a.strip()]
    rhs = [a.strip().upper() for a in parts[1].split(",") if a.strip()]
    return FD(lhs, rhs)


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

        target = parse_target_dep(data["target"])

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

@app.route("/api/decomposition", methods=["POST"])
def api_decomposition():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        schema = Schema(attrs)

        # Determine decomposition type
        decomp_type = data.get("type", "bcnf")
        if decomp_type == "bcnf":
            decomposer = BCNFDecomposer(schema, deps)
        elif decomp_type == "3nf":
            decomposer = ThreeNFDecomposer(schema, deps)
        else:
            raise ValueError("Invalid decomposition type")

        result = decomposer.decompose()
        return jsonify({
            "success": True,
            "fragments": result.fragment_names,
            "dependency_preserved": result.dependency_preserved if hasattr(result, 'dependency_preserved') else None,
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
        requested_num_attrs = max(4, int(data.get("num_attrs", len(attrs) or 12)))
        requested_max_fds = max(4, int(data.get("max_fds", 24)))
        requested_iterations = max(1, int(data.get("iterations", 10)))

        allowed_sizes = [4, 8, 12, 16, 20, 24]

        def clamp_allowed(value):
            return min(allowed_sizes, key=lambda candidate: abs(candidate - value))

        num_attrs = clamp_allowed(requested_num_attrs)
        max_fds = clamp_allowed(requested_max_fds)
        iterations = min(requested_iterations, 10)

        base_attrs = attrs or ["A", "B", "C", "D", "E", "F"]
        if len(base_attrs) >= num_attrs:
            bench_attrs = base_attrs[:num_attrs]
        else:
            bench_attrs = list(base_attrs)
            idx = 0
            while len(bench_attrs) < num_attrs:
                bench_attrs.append(f"A{idx}")
                idx += 1

        def build_sweep(max_value):
            return [value for value in allowed_sizes if value <= max_value]

        benchmark_seeds = [42, 43, 44, 45, 46]
        sizes = build_sweep(max_fds)
        runner = BenchmarkRunner(
            attr_names=bench_attrs,
            fd_sizes=sizes,
            iterations=iterations,
            seed=42,
            benchmark_seeds=benchmark_seeds,
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
                "num_rows": e.num_rows,
                "stats": {k: round(v, 3) for k, v in e.stats.items()},
            })

        attr_scaling = runner.run_attr_scaling(
            attr_sizes=build_sweep(num_attrs),
        )
        attr_entries = []
        for e in attr_scaling.entries:
            attr_entries.append({
                "label": e.label,
                "operation": e.operation,
                "num_fds": e.num_fds,
                "num_attrs": e.num_attrs,
                "num_rows": e.num_rows,
                "time_ms": round(e.time_ms, 3),
                "stats": {k: round(v, 3) for k, v in e.stats.items()},
            })

        ablation = runner.run_ablation()
        ablation_entries = []
        for e in ablation.entries:
            ablation_entries.append({
                "label": e.label,
                "operation": e.operation,
                "num_fds": e.num_fds,
                "num_attrs": e.num_attrs,
                "num_rows": e.num_rows,
                "time_ms": round(e.time_ms, 3),
                "stats": {k: round(v, 3) for k, v in e.stats.items()},
            })

        return jsonify({
            "success": True,
            "entries": entries,
            "attr_scaling": attr_entries,
            "ablation": ablation_entries,
            "effective": {
                "num_attrs": num_attrs,
                "max_fds": max_fds,
                "iterations": iterations,
                "num_workloads": len(benchmark_seeds),
            },
            "requested": {
                "num_attrs": requested_num_attrs,
                "max_fds": requested_max_fds,
                "iterations": requested_iterations,
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/benchmark_custom", methods=["POST"])
def api_benchmark_custom():
    try:
        data = request.json
        attrs = parse_attrs(data["attrs"])
        deps = parse_deps(data["fds"])
        target = parse_target_dep(data["target"])
        decomp_lists = parse_decomp(data["decomp"])
        iterations = max(1, int(data.get("iterations", 10)))

        schema = Schema(attrs)
        decomp = [Schema(d) for d in decomp_lists]

        def avg_time(fn, iters):
            start = time.perf_counter()
            for _ in range(iters):
                fn()
            return (time.perf_counter() - start) / iters * 1000

        entries = []

        entailment_ms = avg_time(lambda: ChaseEntailment(schema, deps, target).run(), iterations)
        entries.append({
            "label": "Custom input",
            "operation": "entailment",
            "num_fds": len(deps),
            "num_attrs": len(attrs),
            "num_rows": None,
            "time_ms": round(entailment_ms, 3),
            "stats": {},
        })

        lossless_iters = max(3, min(iterations, 10))
        total_steps = 0.0
        total_rows = 0.0
        start = time.perf_counter()
        for _ in range(lossless_iters):
            result = ChaseLossless(schema, deps, decomp).run()
            total_steps += len(result.steps)
            total_rows += len(result.steps[-1][1]) if result.steps else 0
        lossless_ms = (time.perf_counter() - start) / lossless_iters * 1000
        entries.append({
            "label": "Custom input",
            "operation": "lossless",
            "num_fds": len(deps),
            "num_attrs": len(attrs),
            "num_rows": None,
            "time_ms": round(lossless_ms, 3),
            "stats": {
                "avg_steps": round(total_steps / lossless_iters, 3),
                "avg_final_rows": round(total_rows / lossless_iters, 3),
            },
        })

        return jsonify({
            "success": True,
            "entries": entries,
            "target": str(target),
            "decomposition": decomp_lists,
            "iterations": iterations,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n  The Chase — CS4221 Database Tuning")
    print(f"  Running at http://localhost:{port}\n")
    app.run(debug=True, host="0.0.0.0", port=port)
