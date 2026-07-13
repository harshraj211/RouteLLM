from typing import TypedDict, cast

from langgraph.graph import END, START, StateGraph

from routellm.schemas.models import ModelDescriptor
from routellm.schemas.routing import RouteRequest
from routellm.services.analyzer import RequestAnalysis, RequestAnalyzer
from routellm.services.policy import PolicyDecision, PolicyEngine
from routellm.services.scoring import CandidateScorer


class RoutingState(TypedDict, total=False):
    request: RouteRequest
    available_models: list[ModelDescriptor]
    analysis: RequestAnalysis
    policy: PolicyDecision
    ranked_candidates: list[ModelDescriptor]


class RoutingWorkflow:
    def __init__(
        self,
        analyzer: RequestAnalyzer,
        policy_engine: PolicyEngine,
        scorer: CandidateScorer,
    ) -> None:
        self.analyzer = analyzer
        self.policy_engine = policy_engine
        self.scorer = scorer
        self.graph = self._build_graph().compile()

    def _build_graph(self) -> StateGraph[RoutingState, None, RoutingState, RoutingState]:
        graph: StateGraph[RoutingState, None, RoutingState, RoutingState] = StateGraph(RoutingState)
        graph.add_node("analyze", self._analyze)
        graph.add_node("select_candidates", self._select_candidates)
        graph.add_node("rank_candidates", self._rank_candidates)
        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", "select_candidates")
        graph.add_edge("select_candidates", "rank_candidates")
        graph.add_edge("rank_candidates", END)
        return graph

    def run(self, request: RouteRequest, available_models: list[ModelDescriptor]) -> RoutingState:
        initial_state: RoutingState = {
            "request": request,
            "available_models": available_models,
        }
        return cast(RoutingState, self.graph.invoke(initial_state))

    def _analyze(self, state: RoutingState) -> RoutingState:
        request = state["request"]
        analysis = self.analyzer.analyze(request)
        return {"analysis": analysis}

    def _select_candidates(self, state: RoutingState) -> RoutingState:
        policy = self.policy_engine.select_candidates(
            state["request"],
            state["analysis"],
            state["available_models"],
        )
        return {"policy": policy}

    def _rank_candidates(self, state: RoutingState) -> RoutingState:
        analysis = state["analysis"]
        ranked = sorted(
            state["policy"].candidates,
            key=lambda model: self.scorer.score(model, analysis),
            reverse=True,
        )
        return {"ranked_candidates": ranked}
