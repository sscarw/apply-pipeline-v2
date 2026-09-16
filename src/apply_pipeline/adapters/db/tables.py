from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
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

    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
    )

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

    history: Mapped[list["StatusChangeRow"]] = relationship(
        back_populates="vacancy",
        cascade="all, delete-orphan",
        order_by=lambda: (
            StatusChangeRow.changed_at,
            StatusChangeRow.id,
        ),
    )


class StatusChangeRow(Base):
    __tablename__ = "vacancy_status_changes"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
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

    from_status: Mapped[str] = mapped_column(
        String(32),
    )

    to_status: Mapped[str] = mapped_column(
        String(32),
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(Text)

    vacancy: Mapped["VacancyRow"] = relationship(
        back_populates="history",
    )
