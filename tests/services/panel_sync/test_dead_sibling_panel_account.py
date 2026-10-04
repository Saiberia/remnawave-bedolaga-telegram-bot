"""Продление живой подписки забирает аккаунт панели у мёртвой соседней строки (user 731, 2026-10-04).

У человека две строки с одним shortUuid: старая disabled (без тарифа) и бывшая живая,
которая держала аккаунт панели и истекла. Покупка оживила старую строку, а аккаунт числился
за истёкшей — запись отказывала, человек платил и оставался без доступа. Патч снимает
``remnawave_id`` с мёртвого соседа только при полном совпадении признаков; во всех
сомнительных случаях остаётся прежний громкий отказ.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.database.models import Subscription, SubscriptionStatus, User, UserStatus
from app.services.panel_sync import push_subscription
from app.services.panel_sync.identity import (
    PanelAccountOwnedByAnotherUser,
    find_foreign_panel_owner,
)
from tests.fixtures.sqlite_memory import memory_session


TABLES = [User.__table__, Subscription.__table__]
PANEL_ID = 491
SHORT = 'tUc58phNoCSrgcFJ'


def _now() -> datetime:
    return datetime.now(UTC)


def _user(user_id: int) -> User:
    return User(
        id=user_id,
        telegram_id=751689656 + user_id,
        first_name=f'U{user_id}',
        language='ru',
        status=UserStatus.ACTIVE.value,
        balance_kopeks=0,
    )


def _sub(
    sub_id: int,
    user_id: int,
    *,
    status: str,
    days: int,
    short: str | None = SHORT,
    **kw,
) -> Subscription:
    return Subscription(
        id=sub_id,
        user_id=user_id,
        remnawave_short_id=f'sid{sub_id}',
        remnawave_short_uuid=short,
        status=status,
        is_trial=False,
        start_date=_now() - timedelta(days=200),
        end_date=_now() + timedelta(days=days),
        traffic_limit_gb=0,
        device_limit=3,
        connected_squads=[],
        **kw,
    )


async def _seed(
    db,
    *,
    holder_status,
    holder_days,
    target_status,
    target_days,
    holder_short=SHORT,
    target_short=SHORT,
):
    """453 — старая строка, которую оживила покупка; 671 — бывшая живая, держит аккаунт 491."""
    user = _user(731)
    target = _sub(453, 731, status=target_status, days=target_days, short=target_short)
    holder = _sub(
        671,
        731,
        status=holder_status,
        days=holder_days,
        short=holder_short,
        remnawave_id=PANEL_ID,
    )
    db.add_all([user, target, holder])
    await db.commit()
    return user, target, holder


def _panel_account(expire_at: datetime):
    return SimpleNamespace(
        id=PANEL_ID,
        username='ronewss1',
        short_uuid=SHORT,
        email=None,
        telegram_id=751689656 + 731,
        expire_at=expire_at,
        subscription_url='https://p/s',
        happ_crypto_link=None,
    )


@pytest.mark.asyncio
async def test_dead_sibling_releases_account_to_live_renewal(monkeypatch) -> None:
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=SubscriptionStatus.EXPIRED.value,
            holder_days=-4,
            target_status=SubscriptionStatus.ACTIVE.value,
            target_days=30,
        )

        owner = await find_foreign_panel_owner(db, user, target, PANEL_ID, multi_tariff=True)
        await db.refresh(holder)

    assert owner is None
    assert holder.remnawave_id is None


@pytest.mark.asyncio
async def test_disabled_sibling_also_counts_as_dead(monkeypatch) -> None:
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=SubscriptionStatus.DISABLED.value,
            holder_days=30,
            target_status=SubscriptionStatus.ACTIVE.value,
            target_days=30,
        )

        owner = await find_foreign_panel_owner(db, user, target, PANEL_ID, multi_tariff=True)
        await db.refresh(holder)

    assert owner is None
    assert holder.remnawave_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        'holder_status',
        'holder_days',
        'target_status',
        'target_days',
        'holder_short',
        'target_short',
    ),
    [
        # сосед живой — аккаунт реально занят оплаченной подпиской
        ('active', 20, 'active', 30, SHORT, SHORT),
        ('trial', 2, 'active', 30, SHORT, SHORT),
        # продлеваемая сама не живая
        ('expired', -4, 'expired', -10, SHORT, SHORT),
        ('expired', -4, 'disabled', 30, SHORT, SHORT),
        ('expired', -4, 'active', -1, SHORT, SHORT),
        # не доказано, что это один и тот же аккаунт панели
        ('expired', -4, 'active', 30, 'otherShortUuid1', SHORT),
        ('expired', -4, 'active', 30, SHORT, None),
        ('expired', -4, 'active', 30, None, SHORT),
    ],
)
async def test_doubtful_cases_keep_the_loud_refusal(
    monkeypatch,
    holder_status,
    holder_days,
    target_status,
    target_days,
    holder_short,
    target_short,
) -> None:
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=holder_status,
            holder_days=holder_days,
            target_status=target_status,
            target_days=target_days,
            holder_short=holder_short,
            target_short=target_short,
        )

        owner = await find_foreign_panel_owner(db, user, target, PANEL_ID, multi_tariff=True)
        await db.refresh(holder)

    assert owner is not None and owner.subscription_id == 671
    assert holder.remnawave_id == PANEL_ID, 'аккаунт не должен сниматься при сомнении'


@pytest.mark.asyncio
async def test_other_person_never_loses_the_account(monkeypatch) -> None:
    """Тот же shortUuid у ДРУГОГО человека — это чужая оплата, а не наша мёртвая строка."""
    async with memory_session(monkeypatch, TABLES) as db:
        user = _user(1)
        target = _sub(11, 1, status=SubscriptionStatus.ACTIVE.value, days=30)
        stranger = _user(2)
        holder = _sub(
            12,
            2,
            status=SubscriptionStatus.EXPIRED.value,
            days=-4,
            remnawave_id=PANEL_ID,
        )
        db.add_all([user, stranger, target, holder])
        await db.commit()

        owner = await find_foreign_panel_owner(db, user, target, PANEL_ID, multi_tariff=True)
        await db.refresh(holder)

    assert owner is not None and owner.user_id == 2
    assert holder.remnawave_id == PANEL_ID


@pytest.mark.asyncio
async def test_single_tariff_behaviour_is_unchanged(monkeypatch) -> None:
    """В одиночном режиме соседа и так не считают чужим — патч туда не заходит."""
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=SubscriptionStatus.EXPIRED.value,
            holder_days=-4,
            target_status=SubscriptionStatus.ACTIVE.value,
            target_days=30,
        )

        owner = await find_foreign_panel_owner(db, user, target, PANEL_ID, multi_tariff=False)
        await db.refresh(holder)

    assert owner is None
    assert holder.remnawave_id == PANEL_ID


@pytest.mark.asyncio
async def test_renewal_of_user_731_reaches_the_panel_and_takes_the_account(
    monkeypatch,
) -> None:
    """Сквозной сценарий 04.10: раньше PanelAccountOwnedByAnotherUser, теперь PATCH в аккаунт 491."""
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=SubscriptionStatus.EXPIRED.value,
            holder_days=-4,
            target_status=SubscriptionStatus.ACTIVE.value,
            target_days=30,
        )
        account = _panel_account(_now() + timedelta(days=30))
        api = AsyncMock()
        api.get_user_by_id.return_value = None
        api.get_user_by_short_uuid.return_value = account
        api.find_users_by_telegram_id.return_value = []
        api.find_users_by_email.return_value = []
        api.update_user.return_value = account

        result = await push_subscription(api, user, target, db=db, multi_tariff=True, verify_recorded_id=False)
        await db.commit()
        await db.refresh(holder)
        await db.refresh(target)

    assert result.action == 'updated'
    assert api.update_user.await_args.kwargs['user_id'] == PANEL_ID
    api.create_user.assert_not_awaited()
    assert holder.remnawave_id is None


@pytest.mark.asyncio
async def test_live_sibling_still_blocks_the_write(monkeypatch) -> None:
    """Контрольный: при живом соседе запись по-прежнему отказывает и ничего не уходит в панель."""
    async with memory_session(monkeypatch, TABLES) as db:
        user, target, holder = await _seed(
            db,
            holder_status=SubscriptionStatus.ACTIVE.value,
            holder_days=20,
            target_status=SubscriptionStatus.ACTIVE.value,
            target_days=30,
        )
        account = _panel_account(_now() + timedelta(days=20))
        api = AsyncMock()
        api.get_user_by_id.return_value = None
        api.get_user_by_short_uuid.return_value = account
        api.find_users_by_telegram_id.return_value = []
        api.find_users_by_email.return_value = []

        with pytest.raises(PanelAccountOwnedByAnotherUser):
            await push_subscription(api, user, target, db=db, multi_tariff=True, verify_recorded_id=False)
        await db.refresh(holder)

    api.update_user.assert_not_awaited()
    api.create_user.assert_not_awaited()
    assert holder.remnawave_id == PANEL_ID
