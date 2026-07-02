from sqlalchemy.orm import Session

from routellm.db.models import RoutingDecisionRecord
from routellm.schemas.routing import RouteRequest, RouteResponse


class RoutingDecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: RouteRequest, response: RouteResponse) -> RoutingDecisionRecord:
        record = RoutingDecisionRecord(
            request_id=response.request_id,
            tenant_id=request.tenant_id,
            workflow_id=request.workflow_id,
            task_type=request.task_type,
            selected_model=response.decision.selected_model,
            reason_codes=",".join(response.decision.reason_codes),
            estimated_input_tokens=response.decision.estimated_input_tokens,
            estimated_output_tokens=response.decision.estimated_output_tokens,
            estimated_cost_usd=response.decision.estimated_cost_usd,
            actual_cost_usd=response.usage.actual_cost_usd,
            estimated_latency_ms=response.decision.estimated_latency_ms,
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list_recent(self, limit: int = 50) -> list[RoutingDecisionRecord]:
        return (
            self.session.query(RoutingDecisionRecord)
            .order_by(RoutingDecisionRecord.id.desc())
            .limit(limit)
            .all()
        )

    def get_by_id(self, decision_id: int) -> RoutingDecisionRecord | None:
        return (
            self.session.query(RoutingDecisionRecord)
            .filter(RoutingDecisionRecord.id == decision_id)
            .one_or_none()
        )
