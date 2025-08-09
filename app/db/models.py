from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    quit_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    pack_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    is_member: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_admin_promoted: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    notifications: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Metrics(Base):
    __tablename__ = "metrics"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id"), primary_key=True)
    days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    saved_money: Mapped[float] = mapped_column(Numeric(12, 2), default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class Audit(Base):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    meta_json: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow)


class TopPost(Base):
    __tablename__ = "top_posts"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=datetime.utcnow, onupdate=datetime.utcnow)
