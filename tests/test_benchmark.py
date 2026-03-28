from chase.benchmark import BenchmarkRunner


def test_run_all_includes_core_operations():
    runner = BenchmarkRunner(["A", "B", "C", "D"], fd_sizes=[3, 5], iterations=5, seed=42)

    result = runner.run_all()

    ops = {entry.operation for entry in result.entries}
    assert {"closure", "min_cover", "entailment", "cand_keys"} <= ops


def test_run_row_scaling_includes_table_operations():
    runner = BenchmarkRunner(["A", "B", "C", "D"], fd_sizes=[4], iterations=5, seed=42)

    result = runner.run_row_scaling(row_sizes=[10, 20], fd_count=4)

    ops = [entry.operation for entry in result.entries]
    assert ops.count("discover") == 2
    assert ops.count("table_check") == 2
    assert all(entry.num_rows in {10, 20} for entry in result.entries)


def test_run_attr_scaling_includes_width_sensitive_operations():
    runner = BenchmarkRunner(["A", "B", "C", "D", "E", "F", "G", "H"], iterations=5, seed=42)

    result = runner.run_attr_scaling(attr_sizes=[4, 6])

    ops = [entry.operation for entry in result.entries]
    assert ops.count("closure_attr") == 2
    assert ops.count("cand_keys_attr") == 2


def test_run_ablation_reports_chase_stats():
    runner = BenchmarkRunner(["A", "B", "C", "D", "E"], fd_sizes=[4], iterations=5, seed=42)

    result = runner.run_ablation()

    assert result.entries
    for entry in result.entries:
        assert "avg_steps" in entry.stats
        assert "avg_final_rows" in entry.stats
