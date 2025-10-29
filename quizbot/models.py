from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quizbot.db import Base


class Team(Base):
    """
    Представляет команду участника.

    :ivar id: Идентификатор команды.
    :ivar name: Уникальное название команды.
    :ivar members: Список участников.
    """

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("name", name="uq_team_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)

    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    game_participants: Mapped[list["GameParticipant"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class Player(Base):
    """
    Описывает пользователя, общающегося с ботом.

    :ivar id: Первичный ключ.
    :ivar tg_user_id: Уникальный Telegram ID.
    :ivar username: Telegram username (если есть).
    :ivar full_name: Отображаемое имя пользователя.
    """

    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("tg_user_id", name="uq_player_tg_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64), default=None)
    full_name: Mapped[Optional[str]] = mapped_column(String(128), default=None)

    memberships: Mapped[list["TeamMember"]] = relationship(
        back_populates="player", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    """
    Отражает участие игрока в конкретной команде.

    :ivar id: Первичный ключ.
    :ivar team_id: Ссылка на команду.
    :ivar player_id: Ссылка на игрока.
    """

    __tablename__ = "team_members"
    __table_args__ = (
        UniqueConstraint("player_id", name="uq_member_player"),
        UniqueConstraint("team_id", "player_id", name="uq_team_player"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"))

    team: Mapped[Team] = relationship(back_populates="members")
    player: Mapped[Player] = relationship(back_populates="memberships")


class Game(Base):
    """
    Модель игры, которую ведёт администратор.

    :ivar id: Первичный ключ.
    :ivar owner_user_id: Telegram ID ведущего (админа).
    :ivar status: Состояние игры.
    :ivar created_at: Время создания.
    :ivar finished_at: Время завершения.
    """

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    finished_at: Mapped[Optional[datetime]] = mapped_column(default=None)

    participants: Mapped[list["GameParticipant"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GameParticipant(Base):
    """
    Связка игра-команда с текущим счётом.

    :ivar id: Первичный ключ.
    :ivar game_id: Идентификатор игры.
    :ivar team_id: Идентификатор команды.
    :ivar score: Накопленный счёт.
    """

    __tablename__ = "game_participants"
    __table_args__ = (UniqueConstraint("game_id", "team_id", name="uq_game_team"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(default=0)

    game: Mapped[Game] = relationship(back_populates="participants")
    team: Mapped[Team] = relationship(back_populates="game_participants")
