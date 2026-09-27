from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apply_pipeline.adapters.db.mappers import verdict_to_decision_row
from apply_pipeline.adapters.db.tables import (
    JudgeDecisionRow,
    MatchRow,
    VacancyRow,
)
from apply_pipeline.domain.errors import NotFoundError
from apply_pipeline.domain.judge import JudgeFailure, JudgeVerdict
from apply_pipeline.domain.match import Match
from apply_pipeline.domain.models import split_vacancy_key


class SqlAlchemyJudgeDecisionLog:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _match_id(
        self,
        match: Match,
    ) -> int | None:
        source, external_id = split_vacancy_key(match.vacancy_key)

        statement = (
            select(MatchRow.id)
            .join(
                VacancyRow,
                MatchRow.vacancy_id == VacancyRow.id,
            )
            .where(
                MatchRow.user_id == match.user_id,
                VacancyRow.source == source.value,
                VacancyRow.external_id == external_id,
            )
        )

        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def record(
        self,
        match: Match,
        verdict: JudgeVerdict,
        *,
        profile_version: int,
        vacancy_hash: str,
        decided_at: datetime,
    ) -> None:
        match_id = await self._match_id(match)

        if match_id is None:
            raise NotFoundError(
                "match",
                f"{match.user_id} / {match.vacancy_key}",
            )

        row = verdict_to_decision_row(
            verdict,
            match_id=match_id,
            profile_version=profile_version,
            vacancy_hash=vacancy_hash,
            decided_at=decided_at,
        )

        self._session.add(row)

    async def was_attempted(
        self,
        match: Match,
        *,
        profile_version: int,
        prompt_version: str,
        vacancy_hash: str,
    ) -> bool:
        match_id = await self._match_id(match)

        if match_id is None:
            return False

        statement = select(
            exists().where(
                JudgeDecisionRow.match_id == match_id,
                JudgeDecisionRow.profile_version == profile_version,
                JudgeDecisionRow.prompt_version == prompt_version,
                JudgeDecisionRow.vacancy_hash == vacancy_hash,
                JudgeDecisionRow.failure.is_distinct_from(JudgeFailure.UNAVAILABLE.value),
            )
        )

        result = await self._session.execute(statement)

        return bool(result.scalar())

    async def spent_since(
        self,
        user_id: UUID,
        *,
        since: datetime,
    ) -> Decimal:
        statement = (
            select(
                func.coalesce(
                    func.sum(JudgeDecisionRow.cost_usd),
                    0,
                )
            )
            .join(
                MatchRow,
                JudgeDecisionRow.match_id == MatchRow.id,
            )
            .where(
                MatchRow.user_id == user_id,
                JudgeDecisionRow.decided_at >= since,
            )
        )

        result = await self._session.execute(statement)

        spent = result.scalar()

        if spent is None:
            return Decimal("0")

        return spent
