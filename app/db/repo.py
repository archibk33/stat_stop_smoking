from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

from sqlalchemy import Select, desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Audit, Metrics, TopPost, User


class UserRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> Optional[User]:
        return await self.session.get(User, user_id)

    async def list_all_members(self) -> list[User]:
        stmt = select(User).where(User.is_member.is_(True))
        rows = await self.session.execute(stmt)
        return list(rows.scalars().all())

    async def list_with_notifications(self) -> list[User]:
        stmt = select(User).where(User.notifications.is_(True))
        rows = await self.session.execute(stmt)
        return list(rows.scalars().all())

    async def list_all(self) -> list[User]:
        rows = await self.session.execute(select(User))
        return list(rows.scalars().all())

    async def upsert_user(
        self,
        *,
        user_id: int,
        username: Optional[str],
        full_name: Optional[str],
        quit_date: Optional[date],
        pack_price: Optional[float],
        is_member: Optional[bool] = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        now = datetime.utcnow()
        if user is None:
            user = User(
                user_id=user_id,
                username=username,
                full_name=full_name,
                quit_date=quit_date,
                pack_price=pack_price,
                created_at=now,
                updated_at=now,
            )
            if is_member is not None:
                user.is_member = is_member
            self.session.add(user)
        else:
            if username is not None:
                user.username = username
            if full_name is not None:
                user.full_name = full_name
            user.quit_date = quit_date
            user.pack_price = pack_price
            if is_member is not None:
                user.is_member = is_member
            user.updated_at = now

        await self.session.flush()
        return user

    async def set_notifications(self, user_id: int, enabled: bool) -> None:
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(notifications=enabled, updated_at=datetime.utcnow())
        )

    async def set_admin_promoted(self, user_id: int, promoted: bool) -> None:
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(is_admin_promoted=promoted, updated_at=datetime.utcnow())
        )

    async def set_is_member(self, user_id: int, is_member: bool) -> None:
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(is_member=is_member, updated_at=datetime.utcnow())
        )


class MetricsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_metrics(self, user_id: int, days: int, saved_money: float) -> Metrics:
        metrics = await self.session.get(Metrics, user_id)
        now = datetime.utcnow()
        if metrics is None:
            metrics = Metrics(user_id=user_id, days=days, saved_money=saved_money, updated_at=now)
            self.session.add(metrics)
        else:
            metrics.days = days
            metrics.saved_money = saved_money
            metrics.updated_at = now
        await self.session.flush()
        return metrics

    async def get_top(self, limit: int = 10) -> Iterable[tuple[User, Metrics]]:
        stmt: Select = (
            select(User, Metrics)
            .join(Metrics, Metrics.user_id == User.user_id)
            .where(User.is_member.is_(True))
            .order_by(desc(Metrics.days), desc(Metrics.updated_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def get_all_metrics(self) -> list[Metrics]:
        rows = await self.session.execute(select(Metrics))
        return list(rows.scalars().all())


class TopPostRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_chat(self, chat_id: int) -> Optional[TopPost]:
        return await self.session.get(TopPost, chat_id)

    async def set(self, chat_id: int, message_id: int) -> TopPost:
        item = await self.get_for_chat(chat_id)
        now = datetime.utcnow()
        if item is None:
            item = TopPost(chat_id=chat_id, message_id=message_id, updated_at=now)
            self.session.add(item)
        else:
            item.message_id = message_id
            item.updated_at = now
        await self.session.flush()
        return item


class AuditRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, user_id: Optional[int], action: str, meta_json: Optional[str] = None) -> Audit:
        entry = Audit(user_id=user_id, action=action, meta_json=meta_json, created_at=datetime.utcnow())
        self.session.add(entry)
        await self.session.flush()
        return entry
