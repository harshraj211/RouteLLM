"""The RouteLLM stdio MCP server for agent-native task routing."""

from typing import Literal

from mcp.server.fastmcp import FastMCP

from routellm.agent_native.policy import AgentHost, AgentNativeRouter

HostName = Literal["codex", "claude_cowork", "antigravity", "generic_mcp"]

mcp = FastMCP(
    "RouteLLM",
    instructions=(
        "Use route_task before substantial work when task complexity, verification, or tool "
        "choice is unclear. RouteLLM returns local policy guidance; it does not control the "
        "host application's model."
    ),
)
router = AgentNativeRouter()


@mcp.tool()
def route_task(
    prompt: str,
    host: HostName = "codex",
    requires_external_research: bool = False,
    high_risk: bool = False,
) -> dict[str, object]:
    """Return local execution guidance without calling any paid model API.

    The active host agent remains responsible for executing the task. Use `high_risk` for
    security-sensitive, production-impacting, legal, financial, or irreversible work.
    """

    recommendation = router.recommend(
        prompt,
        host=host,
        requires_external_research=requires_external_research,
        high_risk=high_risk,
    )
    return recommendation.to_dict()


@mcp.tool()
def host_capabilities(host: HostName = "codex") -> dict[str, object]:
    """Describe the integration boundary shared by supported MCP agent hosts."""

    _validate_host(host)
    return {
        "host": host,
        "transport": "stdio_mcp",
        "requires_provider_api_key": False,
        "execution_target": "current_agent",
        "model_control": "host_managed",
        "supports_forced_runtime_model_switching": False,
        "detail": (
            "RouteLLM can guide an MCP-capable host, but the host owns its model selection "
            "and any subscription entitlement."
        ),
    }


def _validate_host(host: str) -> AgentHost:
    allowed_hosts: set[str] = {"codex", "claude_cowork", "antigravity", "generic_mcp"}
    if host not in allowed_hosts:
        raise ValueError(f"Unsupported host: {host}")
    return host  # type: ignore[return-value]


def main() -> None:
    """Run the server over standard input/output for an MCP host."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
