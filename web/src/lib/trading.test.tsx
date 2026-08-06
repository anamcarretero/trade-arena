import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";

vi.mock("../app/[locale]/app/leagues/actions", () => ({
  submitOrder: async () => undefined,
  cancelOrder: async () => undefined,
  reportTrade: async () => undefined,
  correctReportedTrade: async () => undefined
}));
import {TradingPanel} from "../components/trading-panel";
import type {Portfolio, Ranking} from "./api";

const portfolio = {
  id: "p1", competition_id: "c1", user_id: "u1", currency: "USD",
  initial_cash: "3000.00", cash: "2797.01", joined_at: "2026-09-02T12:00:00Z",
  joined_late: true, equity: "3017.01", cumulative_return: "0.005670000000",
  positions: [{symbol: "AAPL", quantity: "2", price: "110.0000", market_value: "220.00"}],
  orders: [{
    id: "o1", symbol: "AAPL", side: "buy", quantity: "2", order_type: "market",
    allow_extended_hours: false, limit_price: null, status: "filled",
    rejection_reason: null, submitted_at: "2026-09-02T14:30:00Z"
  }],
  executions: [{
    id: "e1", order_id: "o1", symbol: "AAPL", side: "buy", quantity: "2",
    price: "101.0000", commission: "0.99", session: "regular",
    executed_at: "2026-09-02T14:31:00Z", source: "fixture",
    total_amount: null, currency: "USD", fx_rate: "1", correction_of: null
  }]
} satisfies Portfolio;

const ranking = {
  competition_id: "c1", as_of: "2026-09-02T20:00:00Z", digest: "a".repeat(64),
  rows: [{rank: 1, user_id: "u1", portfolio_id: "p1", display_name: "Ana",
    cumulative_return: "0.005670000000", joined_late: true}]
} satisfies Ranking;

describe("trading panel", () => {
  it.each([
    ["es", "Cartera y órdenes", "Incorporación tardía", "Enviar orden", "0,57"],
    ["en", "Portfolio and orders", "Late entry", "Submit order", "0.57"]
  ] as const)("renders backend financial state in %s", (locale, title, late, submit, percent) => {
    const html = renderToStaticMarkup(<TradingPanel locale={locale} leagueId="l1"
      competitionId="c1" portfolio={portfolio} ranking={ranking}/>);
    expect(html).toContain(title);
    expect(html).toContain(late);
    expect(html).toContain(submit);
    expect(html).toContain("2797.01 USD");
    expect(html).toContain(percent);
    expect(html).toContain(locale === "es" ? "Registrar operación ya realizada" : "Record a completed trade");
    expect(html).toContain(locale === "es" ? "Ejecutada por fixture" : "Executed by market fixture");
  });
});
