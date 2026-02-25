"""Modelos de datos para jugadores FIDE."""

from datetime import date, datetime

from sqlalchemy import Date, Index, Integer, String, UniqueConstraint
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
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rapid_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blitz_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("fideid", "period", name="uq_player_rating_history_fideid_period"),
        Index("ix_player_rating_history_fideid_period", "fideid", "period"),
    )


class Player(Base):
    """Modelo de jugador FIDE."""

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fideid: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    sex: Mapped[str | None] = mapped_column(String(1), nullable=True)
    title: Mapped[str | None] = mapped_column(String(10), nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rapid_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rapid_games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blitz_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    blitz_games: Mapped[int | None] = mapped_column(Integer, nullable=True)
    birthday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    flag: Mapped[str | None] = mapped_column(String(5), nullable=True)
    foa_title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    foa_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_players_country_rating", "country", "rating"),
    )

    def to_dict(self) -> dict:
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
            "foa_title": self.foa_title,
            "foa_rating": self.foa_rating,
        }
