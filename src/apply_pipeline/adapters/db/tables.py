from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class VacancyRow(Base):
    __tablename__ = "vacancies"

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    source: Mapped[str] = mapped_column(
        String(20),
    )

    external_id: Mapped[str] = mapped_column(
        String(64),
    )

    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    company: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    location: Mapped[str | None] = mapped_column(Text)
    salary_text: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    monthly_budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class CandidateProfileRow(Base):
    __tablename__ = "candidate_profiles"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "version",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )


class MatchRow(Base):
    __tablename__ = "matches"

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "vacancy_id",
        ),
        Index(
            "ix_matches_user_id_status",
            "user_id",
            "status",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    vacancy_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "vacancies.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    score_value: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    scored_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    unknown_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    profile_version: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    blocked_by: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    vacancy: Mapped["VacancyRow"] = relationship(
        lazy="raise",
    )

    history: Mapped[list["MatchStatusChangeRow"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by=lambda: (
            MatchStatusChangeRow.changed_at,
            MatchStatusChangeRow.id,
        ),
    )


class MatchStatusChangeRow(Base):
    __tablename__ = "match_status_changes"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    match_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "matches.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    from_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    to_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    match: Mapped["MatchRow"] = relationship(
        back_populates="history",
    )
