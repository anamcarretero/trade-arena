"""Proyección determinista y contrato saneado del dashboard de competición.

Este módulo no consulta el legado ni completa huecos de mercado. Las cantidades
monetarias se usan durante el cálculo y se descartan antes de construir la vista.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Iterable
from zoneinfo import ZoneInfo

from tradearena.domain.money import money, rate
from tradearena.domain.trading import Execution, OrderSide, Session

NY = ZoneInfo("America/New_York")
UTC = timezone.utc


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _easter(year: int) -> date:
    """Meeus/Jones/Butcher Gregorian Easter, used for Good Friday."""
    a, b = year % 19, year // 100
    c, d, e = year % 100, b // 4, b % 4
    f, g = (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def xnys_holidays(year: int) -> set[date]:
    days = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))
    return days


def _xnys_close(day: date) -> time:
    thanksgiving = _nth_weekday(day.year, 11, 3, 4)
    def previous_session(holiday: date) -> date:
        candidate = holiday - timedelta(days=1)
        while candidate.weekday() >= 5 or candidate in xnys_holidays(candidate.year):
            candidate -= timedelta(days=1)
        return candidate
    independence_eve = previous_session(_observed(date(day.year, 7, 4)))
    christmas_eve = previous_session(_observed(date(day.year, 12, 25)))
    # The recurring shortened sessions relevant to v1. Exceptional exchange
    # closures remain provider/calendar data for Fase 4.
    if day in {thanksgiving + timedelta(days=1), independence_eve, christmas_eve}:
        return time(13)
    return time(16)


def _xnys_open(_day: date) -> time:
    return time(9, 30)


def sessions_between(start: datetime, end: datetime, now: datetime) -> list[tuple[date, datetime, bool]]:
    """Return canonical XNYS closes and at most one provisional current point."""
    first = start.astimezone(NY).date()
    last = min(end, now).astimezone(NY).date()
    result: list[tuple[date, datetime, bool]] = []
    current = first
    while current <= last:
        if current.weekday() < 5 and current not in xnys_holidays(current.year):
            is_today = current == now.astimezone(NY).date()
            market_open = datetime.combine(current, _xnys_open(current), NY).astimezone(UTC)
            if is_today and now < market_open:
                current += timedelta(days=1)
                continue
            close = datetime.combine(current, _xnys_close(current), NY).astimezone(UTC)
            provisional = is_today and now < close
            point_at = min(close, now) if provisional else close
            if point_at >= start and point_at <= end:
                result.append((current, point_at, provisional))
        current += timedelta(days=1)
    return result


@dataclass(frozen=True)
class InternalPoint:
    day: date
    as_of: datetime
    provisional: bool
    equity: Decimal | None
    cumulative: Decimal | None
    daily: Decimal | None
    positions: tuple[tuple[str, Decimal], ...]
    cash: Decimal
    prices: tuple[tuple[str, Decimal], ...]
    missing: tuple[str, ...]


@dataclass(frozen=True)
class PortfolioProjection:
    portfolio_id: str
    trading_day: date
    as_of: datetime
    provisional: bool
    equity: Decimal
    cumulative_return: Decimal
    state: dict[str, object]
    digest: str


@dataclass(frozen=True)
class RankingProjection:
    competition_id: str
    trading_day: date
    as_of: datetime
    provisional: bool
    rows: tuple[dict[str, object], ...]
    digest: str


@dataclass(frozen=True)
class CompetitionBadge:
    competition_id: str
    user_id: str
    key: str
    achieved_on: date
    state: dict[str, object]


def project_account(account, competition, market, now: datetime) -> tuple[InternalPoint, ...]:
    calendar_data = competition.rules_snapshot["calendar"]
    starts_at = datetime.fromisoformat(str(calendar_data["starts_at"]))
    ends_at = datetime.fromisoformat(str(calendar_data["ends_at"]))
    initial = account.portfolio.initial_cash
    executions = sorted(account.portfolio.executions, key=lambda item: (item.executed_at, item.id))
    # Un proveedor remoto se consulta una vez por símbolo y ventana, no una vez
    # por jornada. La proyección sigue filtrando estrictamente por cada cierre.
    quote_start = datetime.combine(starts_at.astimezone(NY).date(), time.min, NY).astimezone(UTC)
    quote_end = min(ends_at, now)
    quote_cache = {
        symbol: tuple(sorted(market.quotes(symbol, quote_start, quote_end),
                             key=lambda item: item.observed_at))
        for symbol in sorted({item.symbol for item in executions})
    }
    points: list[InternalPoint] = []
    previous: Decimal | None = initial
    for day, as_of, provisional in sessions_between(starts_at, ends_at, now):
        if as_of < account.joined_at:
            continue
        applicable = [item for item in executions if item.executed_at <= as_of]
        cash, positions = _replay(initial, applicable)
        prices: dict[str, Decimal] = {}
        missing: list[str] = []
        day_start = datetime.combine(day, time.min, NY).astimezone(UTC)
        for symbol, quantity in sorted(positions.items()):
            if quantity == 0:
                continue
            quotes = [quote for quote in quote_cache.get(symbol, ())
                      if day_start <= quote.observed_at <= as_of]
            eligible = quotes if provisional else [q for q in quotes if q.session is Session.REGULAR]
            if not eligible:
                missing.append(symbol)
            else:
                prices[symbol] = eligible[-1].value
        equity = None if missing else money(cash + sum(
            (quantity * prices[symbol] for symbol, quantity in positions.items() if quantity),
            Decimal("0"),
        ))
        cumulative = rate(equity / initial - 1) if equity is not None else None
        daily = rate(equity / previous - 1) if equity is not None and previous is not None else None
        previous = equity
        points.append(InternalPoint(
            day, as_of, provisional, equity, cumulative, daily,
            tuple((key, value) for key, value in sorted(positions.items()) if value),
            cash, tuple(sorted(prices.items())), tuple(missing),
        ))
    return tuple(points)


def _replay(initial: Decimal, executions: Iterable[Execution]) -> tuple[Decimal, dict[str, Decimal]]:
    cash = initial
    positions: dict[str, Decimal] = {}
    for execution in executions:
        gross = execution.quantity * execution.price
        total = execution.total_amount
        if execution.side is OrderSide.BUY:
            cash -= total if total is not None else gross + execution.commission
            positions[execution.symbol] = positions.get(execution.symbol, Decimal("0")) + execution.quantity
        else:
            cash += total if total is not None else gross - execution.commission
            positions[execution.symbol] = positions.get(execution.symbol, Decimal("0")) - execution.quantity
    return money(cash), positions


def allocation(point: InternalPoint | None) -> list[dict[str, str]]:
    if point is None or point.equity is None or point.equity <= 0:
        return []
    prices = dict(point.prices)
    rows = [{"symbol": symbol, "weight": str(rate(quantity * prices[symbol] / point.equity))}
            for symbol, quantity in point.positions]
    rows.append({"symbol": "CASH", "weight": str(rate(point.cash / point.equity))})
    return sorted(rows, key=lambda item: item["symbol"])


def safe_trade(execution: Execution, display_name: str, user_id: str) -> dict[str, object]:
    return {
        "player_id": user_id,
        "display_name": display_name,
        "executed_at": execution.executed_at.isoformat(),
        "symbol": execution.symbol,
        "type": "correction" if execution.correction_of else execution.side.value,
        "source": execution.source.value,
    }


def assemble_dashboard(uow, competition, market, now: datetime) -> dict[str, object]:
    """Build the public, percentage-only representation from repository aggregates."""
    calendar_data = competition.rules_snapshot["calendar"]
    accounts = uow.trading.list_for_competition(competition.id)
    projected = {item.user_id: project_account(item, competition, market, now) for item in accounts}
    names: dict[str, str] = {}
    active: dict[str, bool] = {}
    for account in accounts:
        user = uow.users.get(account.user_id)
        profile = uow.profiles.get(account.user_id)
        deleted = user is None or user.deleted_at is not None
        names[account.user_id] = (
            "Participante eliminado" if deleted else
            (profile.display_name if profile else "Participante de TradeArena")
        )
        membership = uow.memberships.get(competition.league_id, account.user_id)
        active[account.user_id] = bool(membership and membership.removed_at is None and not deleted)

    latest = {user_id: next((p for p in reversed(points) if p.equity is not None), None)
              for user_id, points in projected.items()}
    live = sorted(
        (user_id for user_id in latest if active[user_id] and latest[user_id] is not None),
        key=lambda user_id: (-latest[user_id].cumulative, user_id),
    )
    ranks = {user_id: index for index, user_id in enumerate(live, 1)}
    _persist_projections(uow, competition, accounts, projected, active)
    players: list[dict[str, object]] = []
    all_badges: list[dict[str, object]] = []
    for account in sorted(accounts, key=lambda item: item.user_id):
        points = projected[account.user_id]
        valid = [item for item in points if item.equity is not None]
        current = valid[-1] if valid else None
        streak = _current_streak(valid)
        badges = _badges(account.user_id, valid, now)
        all_badges.extend(badges)
        players.append({
            "id": account.user_id,
            "display_name": names[account.user_id],
            "rank": ranks.get(account.user_id),
            "active": active[account.user_id],
            "joined_at": account.joined_at.isoformat(),
            "joined_late": account.joined_late,
            "as_of": current.as_of.isoformat() if current else None,
            "cumulative_return": str(current.cumulative) if current else None,
            "statistics": {
                "best_daily_return": str(max((p.daily for p in valid if p.daily is not None), default=Decimal("0"))),
                "worst_daily_return": str(min((p.daily for p in valid if p.daily is not None), default=Decimal("0"))),
                "current_streak": streak,
                "sessions": len(valid),
            },
            "series": [_public_point(item) for item in points],
            "allocation": allocation(current),
            "badges": badges,
        })

    days = sorted({point.day for points in projected.values() for point in points})
    daily_results = []
    daily_winners = []
    for day in days:
        results = []
        for player in players:
            point = next((p for p in projected[player["id"]] if p.day == day), None)
            if point is not None:
                results.append({
                    "player_id": player["id"], "display_name": player["display_name"],
                    "daily_return": str(point.daily) if point.daily is not None else None,
                    "cumulative_return": str(point.cumulative) if point.cumulative is not None else None,
                    "complete": point.equity is not None,
                })
        provisional = any(p.day == day and p.provisional for points in projected.values() for p in points)
        daily_results.append({"date": day.isoformat(), "provisional": provisional, "players": results})
        values = [(item["player_id"], Decimal(item["daily_return"])) for item in results
                  if item["daily_return"] is not None and active[item["player_id"]]]
        if values:
            best = max(value for _, value in values)
            daily_winners.append({"date": day.isoformat(), "player_ids": sorted(
                user_id for user_id, value in values if value == best
            ), "return": str(best), "provisional": provisional})

    months = sorted({point.day.strftime("%Y-%m") for points in projected.values() for point in points})
    monthly_blocks = [_month_block(month, players, projected, active) for month in months]
    current_month = now.astimezone(NY).strftime("%Y-%m")
    previous_month = (now.astimezone(NY).date().replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    current_block = next((item for item in monthly_blocks if item["month"] == current_month), _empty_month(current_month))
    previous_block = next((item for item in monthly_blocks if item["month"] == previous_month), _empty_month(previous_month))
    player_by_id = {item["id"]: item for item in players}
    for block in monthly_blocks:
        winner = block["winner"]
        if not winner:
            continue
        provisional = block["month"] == current_month
        if block["month"] > current_month:
            continue
        badge = {"player_id": winner["player_id"],
                 "key": f"month_champion_{block['month']}",
                 "achieved_on": f"{block['month']}-01", "provisional": provisional}
        all_badges.append(badge)
        player_by_id[winner["player_id"]]["badges"].append(badge)
    for player in players:
        positive_months = []
        for block in monthly_blocks:
            series = next((item for item in block["series"] if item["player_id"] == player["id"]), None)
            if series and series["points"] and Decimal(series["points"][-1]["return"]) > 0:
                positive_months.append(block["month"])
            else:
                positive_months = []
            for count in (2, 3):
                if len(positive_months) >= count:
                    badge = {"player_id": player["id"], "key": f"positive_months_{count}",
                             "achieved_on": f"{block['month']}-01", "provisional": False}
                    if not any(item["key"] == badge["key"] for item in player["badges"]):
                        player["badges"].append(badge)
                        all_badges.append(badge)
    for badge in all_badges:
        if not badge.get("provisional"):
            uow.trading.save_badge(CompetitionBadge(
                competition.id, str(badge["player_id"]), str(badge["key"]),
                date.fromisoformat(str(badge["achieved_on"])), {},
            ), now)
    historic = uow.trading.list_badges(competition.id)
    for stored in historic:
        if not any(item["player_id"] == stored.user_id and item["key"] == stored.key
                   for item in all_badges):
            badge = {"player_id": stored.user_id, "key": stored.key,
                     "achieved_on": stored.achieved_on.isoformat(), "provisional": False}
            all_badges.append(badge)
            if stored.user_id in player_by_id:
                player_by_id[stored.user_id]["badges"].append(badge)

    missing = sorted({(point.day.isoformat(), symbol) for points in projected.values()
                      for point in points for symbol in point.missing})
    has_provisional = any(point.provisional for points in projected.values() for point in points)
    data_status = "incomplete" if missing else "provisional" if has_provisional else "complete"
    if not accounts or not days:
        data_status = "empty"
    gap = Decimal("0")
    if live:
        gap = latest[live[0]].cumulative - latest[live[-1]].cumulative
    best_day = daily_winners[-1] if daily_winners else None
    trades = sorted(
        ((execution, account.user_id) for account in accounts
         for execution in account.portfolio.executions),
        key=lambda item: (item[0].executed_at, item[0].id), reverse=True,
    )[:8]
    league_allocation = _league_allocation(latest)
    insights = _insights(live, latest, players, gap, best_day, data_status)
    updated = max((point.as_of for points in projected.values() for point in points), default=None)
    return {
        "competition": {
            "id": competition.id, "league_id": competition.league_id,
            "name": competition.name, "status": competition.status.value,
            "starts_at": str(calendar_data["starts_at"]),
            "ends_at": str(calendar_data["ends_at"]),
            "market_calendar": str(calendar_data.get("market", "XNYS")),
            "updated_at": updated.isoformat() if updated else None,
        },
        "data_status": data_status,
        "players": sorted(players, key=lambda item: (item["rank"] is None, item["rank"] or 0, item["id"])),
        "summary": {
            "leader": ({"player_id": live[0], "display_name": names[live[0]],
                        "cumulative_return": str(latest[live[0]].cumulative)} if live else None),
            "best_day": best_day,
            "gap": str(rate(gap)),
        },
        "monthly": {"current": current_block, "previous": previous_block},
        "daily_winners": [item for item in daily_winners if item["date"][:7] == current_month],
        "daily_results": daily_results,
        "league_allocation": league_allocation,
        "recent_trades": [safe_trade(execution, names[user_id], user_id) for execution, user_id in trades],
        "badges": sorted(all_badges, key=lambda item: (item["player_id"], item["key"])),
        "insights": insights,
        "missing_data": [{"date": day, "symbol": symbol} for day, symbol in missing],
        "ticker_record": None,
    }


def _digest(payload: dict[str, object]) -> str:
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":")
    ).encode()).hexdigest()


def _persist_projections(uow, competition, accounts, projected, active) -> None:
    for account in accounts:
        for point in projected[account.user_id]:
            if point.equity is None or point.cumulative is None:
                continue
            state = {
                "version": "dashboard-v1", "cash": str(point.cash),
                "positions": {symbol: str(value) for symbol, value in point.positions},
                "prices": {symbol: str(value) for symbol, value in point.prices},
            }
            payload = {"portfolio_id": account.portfolio.id,
                       "trading_day": point.day.isoformat(),
                       "as_of": point.as_of.isoformat(), "provisional": point.provisional,
                       "equity": str(point.equity),
                       "cumulative_return": str(point.cumulative), "state": state}
            uow.trading.save_portfolio_projection(PortfolioProjection(
                account.portfolio.id, point.day, point.as_of, point.provisional,
                point.equity, point.cumulative, state, _digest(payload),
            ))
    days = sorted({point.day for points in projected.values() for point in points})
    for day in days:
        candidates = []
        day_points = []
        for account in accounts:
            point = next((item for item in projected[account.user_id] if item.day == day), None)
            if point is None:
                continue
            day_points.append(point)
            if active[account.user_id] and point.cumulative is not None:
                candidates.append((account.user_id, point.cumulative))
        if not day_points or not candidates:
            continue
        ordered = sorted(candidates, key=lambda item: (-item[1], item[0]))
        rows = tuple({"rank": rank, "user_id": user_id,
                      "cumulative_return": str(value)}
                     for rank, (user_id, value) in enumerate(ordered, 1))
        as_of = max(item.as_of for item in day_points)
        provisional = any(item.provisional for item in day_points)
        payload = {"competition_id": competition.id, "trading_day": day.isoformat(),
                   "as_of": as_of.isoformat(), "provisional": provisional,
                   "rows": rows, "version": "dashboard-v1"}
        uow.trading.save_ranking_projection(RankingProjection(
            competition.id, day, as_of, provisional, rows, _digest(payload),
        ))


def empty_dashboard(competition) -> dict[str, object]:
    return {
        "competition": {"id": competition.id, "league_id": competition.league_id,
                        "name": competition.name, "status": competition.status.value,
                        "starts_at": competition.starts_at.isoformat(),
                        "ends_at": competition.ends_at.isoformat(),
                        "market_calendar": "XNYS", "updated_at": None},
        "data_status": "empty", "players": [],
        "summary": {"leader": None, "best_day": None, "gap": "0"},
        "monthly": {"current": None, "previous": None}, "daily_winners": [],
        "daily_results": [], "league_allocation": [], "recent_trades": [],
        "badges": [], "insights": [], "missing_data": [], "ticker_record": None,
    }


def _public_point(point: InternalPoint) -> dict[str, object]:
    return {"date": point.day.isoformat(), "as_of": point.as_of.isoformat(),
            "provisional": point.provisional,
            "daily_return": str(point.daily) if point.daily is not None else None,
            "cumulative_return": str(point.cumulative) if point.cumulative is not None else None,
            "complete": point.equity is not None}


def _current_streak(points: list[InternalPoint]) -> int:
    streak = 0
    for point in reversed(points):
        value = point.daily
        if value is None or value == 0 or (streak and (value > 0) != (streak > 0)):
            break
        streak += 1 if value > 0 else -1
    return streak


def _badges(user_id: str, points: list[InternalPoint], now: datetime) -> list[dict[str, object]]:
    badges: list[dict[str, object]] = []
    maximum = max((point.cumulative for point in points if point.cumulative is not None), default=Decimal("0"))
    for threshold in (5, 10, 25):
        if maximum >= Decimal(threshold) / 100:
            achieved = next(point.day for point in points if point.cumulative is not None
                            and point.cumulative >= Decimal(threshold) / 100)
            badges.append({"player_id": user_id, "key": f"return_{threshold}",
                           "achieved_on": achieved.isoformat(), "provisional": False})
    positive = 0
    for point in points:
        positive = positive + 1 if point.daily is not None and point.daily > 0 else 0
        if positive >= 5:
            badges.append({"player_id": user_id, "key": "five_green_sessions",
                           "achieved_on": point.day.isoformat(), "provisional": False})
            break
    return badges


def _month_block(month: str, players, projected, active) -> dict[str, object]:
    series = []
    returns = []
    for player in players:
        points = [p for p in projected[player["id"]] if p.day.strftime("%Y-%m") == month and p.equity is not None]
        if not points:
            continue
        base = points[0].equity
        values = [{"date": p.day.isoformat(), "return": str(rate(p.equity / base - 1))} for p in points]
        value = Decimal(values[-1]["return"])
        series.append({"player_id": player["id"], "display_name": player["display_name"], "points": values})
        if active[player["id"]]:
            returns.append((player["id"], value))
    winner = None
    if returns:
        best = max(value for _, value in returns)
        winner_id = min(user_id for user_id, value in returns if value == best)
        winner = {"player_id": winner_id, "return": str(best)}
    return {"month": month, "winner": winner, "series": series}


def _empty_month(month: str) -> dict[str, object]:
    return {"month": month, "winner": None, "series": []}


def _league_allocation(latest) -> list[dict[str, str]]:
    total = Decimal("0")
    values: dict[str, Decimal] = {}
    for point in latest.values():
        if point is None or point.equity is None:
            continue
        total += point.equity
        values["CASH"] = values.get("CASH", Decimal("0")) + point.cash
        prices = dict(point.prices)
        for symbol, quantity in point.positions:
            values[symbol] = values.get(symbol, Decimal("0")) + quantity * prices[symbol]
    if total <= 0:
        return []
    return [{"symbol": symbol, "weight": str(rate(value / total))}
            for symbol, value in sorted(values.items())]


def _insights(live, latest, players, gap, best_day, status) -> list[dict[str, object]]:
    if status in {"empty", "incomplete"} or not live:
        return []
    result: list[dict[str, object]] = [{"kind": "leader", "player_id": live[0],
                                      "value": str(latest[live[0]].cumulative)}]
    if len(live) > 1:
        result.append({"kind": "close_competition" if gap <= Decimal("0.02") else "clear_leader",
                       "value": str(rate(gap))})
    if best_day:
        result.append({"kind": "best_day", "player_ids": best_day["player_ids"],
                       "value": best_day["return"]})
    streaked = sorted(((abs(p["statistics"]["current_streak"]), p["id"], p["statistics"]["current_streak"])
                       for p in players if p["statistics"]["current_streak"]), reverse=True)
    if streaked:
        _, user_id, streak = streaked[0]
        result.append({"kind": "green_streak" if streak > 0 else "red_streak",
                       "player_id": user_id, "sessions": abs(streak)})
    return result[:4]
