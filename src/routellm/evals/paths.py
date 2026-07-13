from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BENCHMARK_DATASET = PROJECT_ROOT / "evals" / "datasets" / "benchmark_requests.json"
