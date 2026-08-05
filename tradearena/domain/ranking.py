"""Snapshots reproducibles de clasificación porcentual."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from .trading import PortfolioSnapshot


@dataclass(frozen=True)
class RankingRow:
    rank: int
    user_id: str
    portfolio_id: str
    cumulative_return: str
    joined_late: bool


@dataclass(frozen=True)
class RankingSnapshot:
    competition_id: str
    as_of: datetime
    rows: tuple[RankingRow, ...]
    digest: str


def build_ranking(
    competition_id: str,
    as_of: datetime,
    portfolios: list[tuple[str, PortfolioSnapshot, bool]],
) -> RankingSnapshot:
    ordered = sorted(portfolios, key=lambda item: (-item[1].cumulative_return, item[0]))
    rows = tuple(
        RankingRow(index, user_id, snapshot.portfolio_id,
                   str(snapshot.cumulative_return), joined_late)
        for index, (user_id, snapshot, joined_late) in enumerate(ordered, 1)
    )
    canonical = json.dumps(
        [row.__dict__ for row in rows], sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(
        f"{competition_id}|{as_of.isoformat()}|{canonical}".encode()
    ).hexdigest()
    return RankingSnapshot(competition_id, as_of, rows, digest)
