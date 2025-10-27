from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from quizbot.db import Base


class Team(Base):
    """
    Представляет команду в рамках чата.

    :ivar id: Идентификатор команды.
    :ivar chat_id: Идентификатор чата Telegram.
    :ivar name: Название команды.
    :ivar members: Участники команды.
    """
    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("chat_id", "name", name="uq_team_chat_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(120))

    members: Mapped[list["TeamMember"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMember(Base):
    """
    Отражает участие пользователя в конкретной команде.

    :ivar id: Первичный ключ.
    :ivar chat_id: Идентификатор чата.
    :ivar team_id: Ссылка на команду.
    :ivar tg_user_id: Telegram ID участника.
    """
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("chat_id", "tg_user_id", name="uq_member_chat_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)

    team: Mapped[Team] = relationship(back_populates="members")


class Game(Base):
    """
    Модель игры, связывает чат и ведущего.

    :ivar id: Первичный ключ.
    :ivar chat_id: Идентификатор чата.
    :ivar owner_user_id: Telegram ID ведущего.
    :ivar status: Текущий статус игры.
    :ivar created_at: Дата создания.
    :ivar finished_at: Дата завершения.
    """
    __tablename__ = "games"
    __table_args__ = (UniqueConstraint("chat_id", name="uq_game_chat"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    owner_user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="idle")
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    finished_at: Mapped[Optional[datetime]] = mapped_column(default=None)


class Round(Base):
    """
    Описывает раунд внутри игры.

    :ivar id: Первичный ключ.
    :ivar game_id: Ссылка на игру.
    :ivar question: Текст вопроса.
    :ivar created_at: Время создания.
    """
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id", ondelete="CASCADE"))
    question: Mapped[Optional[str]] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
