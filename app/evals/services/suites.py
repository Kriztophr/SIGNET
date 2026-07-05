import uuid

from sqlalchemy.orm import Session

from app.evals.models.entities import EvalCase, EvalSuite, EvalSuiteType, EvalTargetType
from app.platform.errors import DomainValidationError


class EvalSuiteService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_suite(
        self,
        tenant_id: uuid.UUID,
        created_by: uuid.UUID,
        *,
        name: str,
        target_type: EvalTargetType,
        config: dict,
        cases: list[dict],
        project_id: uuid.UUID | None = None,
    ) -> EvalSuite:
        min_reviewers = config.get("min_reviewers", 1)
        if not isinstance(min_reviewers, int) or min_reviewers < 1:
            raise DomainValidationError("config.min_reviewers must be an integer >= 1")

        suite = EvalSuite(
            tenant_id=tenant_id,
            project_id=project_id,
            name=name,
            target_type=target_type,
            suite_type=EvalSuiteType.rubric_scored,
            config_json={**config, "min_reviewers": min_reviewers},
            created_by=created_by,
        )
        self._session.add(suite)
        self._session.flush()

        for index, case in enumerate(cases):
            order_index = case.get("order_index")
            self._session.add(
                EvalCase(
                    eval_suite_id=suite.id,
                    name=case["name"],
                    prompt_or_instruction=case["prompt_or_instruction"],
                    expected_shape_json=case.get("expected_shape"),
                    weight=case.get("weight", 1.0),
                    order_index=order_index if order_index is not None else index,
                )
            )
        self._session.flush()
        return suite
