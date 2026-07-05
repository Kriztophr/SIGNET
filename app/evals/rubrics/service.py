import uuid

from sqlalchemy.orm import Session

from app.evals.models.entities import Rubric, RubricVersion
from app.evals.repositories.evals import EvalsRepository
from app.platform.errors import DomainValidationError
from app.platform.time.clock import utc_now


class RubricService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = EvalsRepository(session)

    def create_rubric(
        self,
        tenant_id: uuid.UUID,
        *,
        name: str,
        description: str = "",
        project_id: uuid.UUID | None = None,
    ) -> Rubric:
        rubric = Rubric(
            tenant_id=tenant_id, project_id=project_id, name=name, description=description
        )
        self._session.add(rubric)
        self._session.flush()
        return rubric

    def create_version(
        self,
        tenant_id: uuid.UUID,
        rubric_id: uuid.UUID,
        *,
        criteria: list[dict],
        score_scale: dict,
        pass_threshold: dict,
    ) -> RubricVersion:
        rubric = self._repo.get_rubric(tenant_id, rubric_id)
        validate_rubric_config(criteria, score_scale, pass_threshold)
        version = RubricVersion(
            rubric_id=rubric.id,
            version_number=self._repo.next_rubric_version_number(rubric.id),
            criteria_json=criteria,
            score_scale_json=score_scale,
            pass_threshold_json=pass_threshold,
            published_at=utc_now(),
        )
        self._session.add(version)
        self._session.flush()
        return version


def validate_rubric_config(criteria: list[dict], score_scale: dict, pass_threshold: dict) -> None:
    """A misconfigured rubric is rejected at creation, never at scoring time."""
    if not criteria:
        raise DomainValidationError("rubric version must define at least one criterion")
    keys = []
    for criterion in criteria:
        key = criterion.get("key")
        weight = criterion.get("weight", 1)
        if not key:
            raise DomainValidationError("every rubric criterion needs a non-empty 'key'")
        if not isinstance(weight, int | float) or weight <= 0:
            raise DomainValidationError(f"criterion {key!r} weight must be a positive number")
        keys.append(key)
    if len(keys) != len(set(keys)):
        raise DomainValidationError("rubric criterion keys must be unique")

    scale_min, scale_max = score_scale.get("min"), score_scale.get("max")
    if not isinstance(scale_min, int | float) or not isinstance(scale_max, int | float):
        raise DomainValidationError("score_scale requires numeric 'min' and 'max'")
    if scale_min >= scale_max:
        raise DomainValidationError("score_scale min must be below max")

    min_total = pass_threshold.get("min_total")
    if not isinstance(min_total, int | float):
        raise DomainValidationError("pass_threshold requires a numeric 'min_total'")
    max_attainable = sum(c.get("weight", 1) for c in criteria) * scale_max
    if min_total > max_attainable:
        raise DomainValidationError(
            f"pass_threshold min_total {min_total} exceeds the maximum attainable "
            f"weighted total {max_attainable}"
        )


def validate_and_score(version: RubricVersion, score_json: dict) -> tuple[float, bool]:
    """Validates a reviewer's criterion scores against the rubric version and
    returns (weighted_total, pass_fail)."""
    criteria = {c["key"]: c for c in version.criteria_json}
    submitted = set(score_json)
    expected = set(criteria)
    if submitted != expected:
        missing = sorted(expected - submitted)
        extra = sorted(submitted - expected)
        parts = []
        if missing:
            parts.append(f"missing criteria: {', '.join(missing)}")
        if extra:
            parts.append(f"unknown criteria: {', '.join(extra)}")
        raise DomainValidationError("; ".join(parts))

    scale_min = version.score_scale_json["min"]
    scale_max = version.score_scale_json["max"]
    total = 0.0
    for key, value in score_json.items():
        if not isinstance(value, int | float) or not (scale_min <= value <= scale_max):
            raise DomainValidationError(
                f"score for {key!r} must be a number within [{scale_min}, {scale_max}]"
            )
        total += value * criteria[key].get("weight", 1)

    return total, total >= version.pass_threshold_json["min_total"]
