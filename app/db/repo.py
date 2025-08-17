from __future__ import annotations

from datetime import date, datetime, timezone
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
        now = datetime.now(timezone.utc)
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
            update(User).where(User.user_id == user_id).values(notifications=enabled, updated_at=datetime.now(timezone.utc))
        )

    async def set_admin_promoted(self, user_id: int, promoted: bool) -> None:
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(is_admin_promoted=promoted, updated_at=datetime.now(timezone.utc))
        )

    async def set_is_member(self, user_id: int, is_member: bool) -> None:
        await self.session.execute(
            update(User).where(User.user_id == user_id).values(is_member=is_member, updated_at=datetime.now(timezone.utc))
        )

    async def delete_user_data(self, user_id: int) -> None:
        """Удаляет все данные пользователя из БД"""
        # Удаляем метрики
        metrics = await self.session.get(Metrics, user_id)
        if metrics:
            await self.session.delete(metrics)
        
        # Удаляем пользователя
        user = await self.session.get(User, user_id)
        if user:
            await self.session.delete(user)
        
        # Удаляем записи аудита
        result = await self.session.execute(
            select(Audit).where(Audit.user_id == user_id)
        )
        audit_records = result.scalars().all()
        for audit_record in audit_records:
            await self.session.delete(audit_record)


class MetricsRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert_metrics(self, user_id: int, days: int, saved_money: float) -> Metrics:
        metrics = await self.session.get(Metrics, user_id)
        now = datetime.now(timezone.utc)
        if metrics is None:
            metrics = Metrics(user_id=user_id, days=days, saved_money=saved_money, relapses=0, updated_at=now)
            self.session.add(metrics)
        else:
            metrics.days = days
            metrics.saved_money = saved_money
            metrics.updated_at = now
        await self.session.flush()
        return metrics

    async def upsert_metrics_with_relapses(self, user_id: int, days: int, saved_money: float, relapses: int) -> Metrics:
        """Обновляет метрики с сохранением количества рецидивов"""
        metrics = await self.session.get(Metrics, user_id)
        now = datetime.now(timezone.utc)
        if metrics is None:
            metrics = Metrics(user_id=user_id, days=days, saved_money=saved_money, relapses=relapses, updated_at=now)
            logger.info(f"Created new metrics for user {user_id}")
            self.session.add(metrics)
        else:
            metrics.days = days
            metrics.saved_money = saved_money
            metrics.relapses = relapses
            metrics.updated_at = now
        await self.session.flush()
        return metrics

    async def add_relapse(self, user_id: int) -> Metrics:
        """Добавляет рецидив пользователю (без сброса счетчика дней)"""
        metrics = await self.session.get(Metrics, user_id)
        now = datetime.now(timezone.utc)
        if metrics is None:
            # Создаем новую запись если пользователя нет
            metrics = Metrics(user_id=user_id, days=0, saved_money=0, relapses=1, updated_at=now)
            self.session.add(metrics)
        else:
            metrics.relapses += 1
            metrics.updated_at = now
        
        await self.session.flush()
        return metrics

    async def get_top(self, limit: int = 10) -> Iterable[tuple[User, Metrics]]:
        # Получаем всех пользователей с метриками
        stmt: Select = (
            select(User, Metrics)
            .join(Metrics, Metrics.user_id == User.user_id)
            .where(User.is_member.is_(True))
        )
        result = await self.session.execute(stmt)
        users_with_metrics = list(result.all())
        
        # Сортируем по новому алгоритму рейтинга
        def calculate_score(metrics: Metrics) -> int:
            return metrics.days - (metrics.relapses * 3)
        
        def get_sort_key(item: tuple[User, Metrics]) -> tuple[int, int, int, str]:
            user, metrics = item
            score = calculate_score(metrics)
            # Сортируем по приоритетам:
            # 1. score (по убыванию)
            # 2. дни (по убыванию) 
            # 3. рецидивы (по возрастанию)
            # 4. имя (по алфавиту для стабильности)
            name = (user.full_name or user.username or str(user.user_id)).lower()
            return (-score, -metrics.days, metrics.relapses, name)
        
        # Сортируем и возвращаем топ
        sorted_users = sorted(users_with_metrics, key=get_sort_key)
        return sorted_users[:limit]

    async def get_all_metrics(self) -> list[Metrics]:
        rows = await self.session.execute(select(Metrics))
        return list(rows.scalars().all())


class TopPostRepo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_chat(self, chat_id: int, topic_id: int | None = None) -> Optional[TopPost]:
        # Ищем пост для конкретного чата и топика
        stmt = select(TopPost).where(
            TopPost.chat_id == chat_id,
            TopPost.topic_id == topic_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set(self, chat_id: int, message_id: int, topic_id: int | None = None) -> TopPost:
        item = await self.get_for_chat(chat_id, topic_id)
        now = datetime.now(timezone.utc)
        if item is None:
            item = TopPost(chat_id=chat_id, topic_id=topic_id, message_id=message_id, updated_at=now)
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
        entry = Audit(user_id=user_id, action=action, meta_json=meta_json, created_at=datetime.now(timezone.utc))
        self.session.add(entry)
        await self.session.flush()
        return entry
