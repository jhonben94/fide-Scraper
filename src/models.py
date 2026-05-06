"""Modelos de datos para jugadores FIDE."""

from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, Date, DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base para todos los modelos SQLAlchemy."""

    pass


class PlayerRatingHistory(Base):
    """Historial de ratings por periodo (para Progress)."""

    __tablename__ = "player_rating_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fideid: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rapid_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blitz_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("fideid", "period", name="uq_player_rating_history_fideid_period"),
        Index("ix_player_rating_history_fideid_period", "fideid", "period"),
        {"schema": "fide"},
    )


class HistoryImportCheckpoint(Base):
    """Periodo de historial ya importado (control / idempotencia)."""

    __tablename__ = "history_import_checkpoint"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    country_filter: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    period_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    rows_parsed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    rows_upserted: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "period",
            "country_filter",
            "period_scope",
            name="uq_fide_history_import_checkpoint",
        ),
        {"schema": "fide"},
    )


class Player(Base):
    """Modelo de jugador FIDE."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fideid: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    sex: Mapped[Optional[str]] = mapped_column(String(1), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    games: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rapid_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rapid_games: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blitz_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blitz_games: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    birthday: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    flag: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    flag_std: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    flag_rpd: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    flag_blz: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    foa_title: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    foa_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_players_country_rating", "country", "rating"),
        {"schema": "fide"},
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el jugador a diccionario para serialización."""
        return {
            "fideid": self.fideid,
            "name": self.name,
            "country": self.country,
            "sex": self.sex,
            "title": self.title,
            "rating": self.rating,
            "games": self.games,
            "rapid_rating": self.rapid_rating,
            "rapid_games": self.rapid_games,
            "blitz_rating": self.blitz_rating,
            "blitz_games": self.blitz_games,
            "birthday": self.birthday,
            "flag": self.flag,
            "flag_std": self.flag_std,
            "flag_rpd": self.flag_rpd,
            "flag_blz": self.flag_blz,
            "foa_title": self.foa_title,
            "foa_rating": self.foa_rating,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
