"""Small terminal client for a running RouteLLM gateway."""

import argparse
import json
import sys
from getpass import getpass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_GATEWAY_URL = "http://localhost:8000/v1"


def _get_json(url: str) -> Any:
    try:
        with urlopen(url, timeout=10) as response:  # noqa: S310 - user-selected local gateway URL
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach RouteLLM at {url}: {exc}") from exc


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=360) as response:  # noqa: S310 - user-selected local gateway URL
            return json.load(response)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"RouteLLM request failed: {detail}") from exc
    except (URLError, TimeoutError) as exc:
        raise RuntimeError(f"Could not reach RouteLLM at {url}: {exc}") from exc


def _print_models(gateway_url: str) -> None:
    statuses = _get_json(f"{gateway_url.rstrip('/')}/runtime/ollama")
    for status in statuses:
        print(f"Ollama endpoint: {status['endpoint']}")
        if not status["reachable"]:
            print(f"  Unreachable: {status.get('detail', 'unknown error')}")
            continue
        print("  Installed models:")
        for model in status.get("installed_models", []):
            print(f"    - {model}")


def _ask(gateway_url: str, prompt: str, task_type: str, max_output_tokens: int) -> None:
    response = _post_json(
        f"{gateway_url.rstrip('/')}/route",
        {
            "tenant_id": "cli",
            "workflow_id": "terminal",
            "task_type": task_type,
            "messages": [{"role": "user", "content": prompt}],
            "max_budget_usd": 1,
            "latency_slo_ms": 300000,
            "max_output_tokens": max_output_tokens,
        },
    )
    decision = response["decision"]
    usage = response["usage"]
    print(f"Model: {decision['selected_model']} ({usage.get('provider_model', 'unknown')})")
    print(f"Time: {usage.get('latency_ms', 'unknown')} ms | Cost: ${usage['actual_cost_usd']}")
    print()
    print(response["output"]["text"])


def _setup() -> None:
    print("RouteLLM setup")
    print("Press Enter to accept defaults. API keys are never displayed.")
    use_ollama = input("Enable Ollama? [Y/n]: ").strip().lower() not in {"n", "no"}
    use_anthropic = input("Enable Anthropic/Claude API? [y/N]: ").strip().lower() in {"y", "yes"}
    use_openai = input("Enable OpenAI API? [y/N]: ").strip().lower() in {"y", "yes"}
    values = {
        "ROUTELLM_INFERENCE_MODE": "live",
        "ROUTELLM_ENABLE_CLOUD_MODELS": str(use_anthropic or use_openai).lower(),
    }
    if use_ollama:
        values["ROUTELLM_OLLAMA_FAST_MODEL"] = input(
            "Ollama fast model [qwen2.5:3b]: "
        ).strip() or "qwen2.5:3b"
        values["ROUTELLM_OLLAMA_CODER_MODEL"] = input(
            "Ollama coder model [qwen2.5-coder:7b]: "
        ).strip() or "qwen2.5-coder:7b"
    if use_anthropic:
        values["ANTHROPIC_API_KEY"] = getpass("Anthropic API key: ")
    if use_openai:
        values["OPENAI_API_KEY"] = getpass("OpenAI API key: ")
    env_path = Path(".env")
    existing = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    lines = existing.splitlines()
    for key, value in values.items():
        replacement = f"{key}={value}"
        for index, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[index] = replacement
                break
        else:
            lines.append(replacement)
    env_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Saved configuration to {env_path.resolve()}. Restart the gateway.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="routellm", description="Use a local RouteLLM gateway.")
    parser.add_argument(
        "prompt", nargs="*", help="Question to route. Use 'models' to list Ollama models."
    )
    parser.add_argument("--url", default=DEFAULT_GATEWAY_URL, help="RouteLLM gateway URL.")
    parser.add_argument("--task-type", default="qa", help="Task label sent to the router.")
    parser.add_argument(
        "--max-output-tokens", type=int, default=256, help="Maximum response tokens."
    )
    return parser


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1].lower() == "setup":
        _setup()
        return
    args = build_parser().parse_args()
    try:
        if args.prompt == ["models"]:
            _print_models(args.url)
        elif args.prompt:
            _ask(args.url, " ".join(args.prompt), args.task_type, args.max_output_tokens)
        else:
            build_parser().print_help()
            raise SystemExit(2)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
