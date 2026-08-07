import io
import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tradearena.adapters.market_data import (
    FixtureMarketDataAdapter,
    YahooFinanceMarketDataAdapter,
    build_market_data_adapter,
)
from tradearena.domain.trading import Session


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def test_yahoo_adapter_translates_daily_closes_to_market_port_quotes():
    requested = []
    payload = {
        "chart": {
            "error": None,
            "result": [{
                "timestamp": [1783517400, 1783603800],
                "indicators": {"quote": [{"close": [134.25, None]}]},
            }],
        },
    }

    def opener(request, timeout):
        requested.append((request.full_url, timeout))
        return Response(json.dumps(payload).encode())

    adapter = YahooFinanceMarketDataAdapter(opener=opener, timeout=3)
    start = datetime(2026, 7, 8, tzinfo=timezone.utc)
    end = datetime(2026, 7, 10, tzinfo=timezone.utc)

    quotes = adapter.quotes("mu", start, end)
    again = adapter.quotes("MU", start, end)

    assert quotes == again
    assert len(requested) == 1
    assert "%2F" not in requested[0][0]
    assert quotes[0].symbol == "MU"
    assert quotes[0].value == Decimal("134.250000")
    assert quotes[0].session is Session.REGULAR
    assert quotes[0].observed_at.tzinfo is timezone.utc


def test_market_adapter_factory_keeps_provider_choice_at_composition_root():
    assert isinstance(build_market_data_adapter("fixture"), FixtureMarketDataAdapter)
    assert isinstance(build_market_data_adapter("YAHOO"), YahooFinanceMarketDataAdapter)
    with pytest.raises(ValueError, match="MARKET_DATA_PROVIDER"):
        build_market_data_adapter("unknown")


def test_yahoo_failure_becomes_missing_quotes_instead_of_partial_results():
    def unavailable(request, timeout):
        raise OSError("offline")

    adapter = YahooFinanceMarketDataAdapter(opener=unavailable)
    start = datetime(2026, 7, 8, tzinfo=timezone.utc)
    end = datetime(2026, 7, 10, tzinfo=timezone.utc)

    assert adapter.quotes("MU", start, end) == ()
