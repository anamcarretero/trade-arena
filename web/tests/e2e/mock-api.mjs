import {createServer} from "node:http";

const league = {
  id: "league-e2e", name: "Liga E2E", owner_id: "owner-e2e",
  created_at: "2026-08-01T12:00:00Z", active: true, plan: "free",
  actor_role: "owner", max_members: 2,
  members: [{
    user_id: "owner-e2e", display_name: "Owner E2E", role: "owner",
    joined_at: "2026-08-01T12:00:00Z"
  }, {
    user_id: "member-e2e", display_name: "Member E2E", role: "member",
    joined_at: "2026-08-02T12:00:00Z"
  }], invitations: []
};
const competitions = [];
const portfolios = new Map();

function json(response, status, body) {
  response.writeHead(status, {"Content-Type": "application/json"});
  response.end(JSON.stringify(body));
}

async function body(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {};
}

createServer(async (request, response) => {
  const path = new URL(request.url, "http://127.0.0.1:18080").pathname;
  if (path === "/health/live") return json(response, 200, {status: "ok"});
  if (request.headers.authorization !== "Bearer e2e-session") {
    return json(response, 403, {error: "forbidden"});
  }
  if (request.method === "GET" && path === "/api/v1/me") {
    return json(response, 200, {
      user: {id: "owner-e2e", email: "owner@example.com"},
      profile: {display_name: "Owner E2E", locale: "es", birth_date: "1990-01-01"}
    });
  }
  if (request.method === "GET" && path === `/api/v1/leagues/${league.id}`) {
    return json(response, 200, league);
  }
  if (path === `/api/v1/leagues/${league.id}/competitions`) {
    if (request.method === "GET") return json(response, 200, competitions);
    if (request.method === "POST") {
      const input = await body(request);
      const competition = {
        id: `competition-${competitions.length + 1}`, league_id: league.id,
        name: input.name, starts_at: input.starts_at, ends_at: input.ends_at,
        status: "draft", rules_snapshot: null, started_at: null
      };
      competitions.push(competition);
      return json(response, 201, competition);
    }
  }
  const start = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/start$/);
  if (request.method === "POST" && start) {
    const competition = competitions.find(item => item.id === start[1]);
    if (!competition) return json(response, 404, {error: "not_found"});
    competition.status = "active";
    competition.started_at = "2026-08-06T12:00:00Z";
    competition.rules_snapshot = {
      version: "1",
      calendar: {
        market: "XNYS", timezone: "America/New_York",
        starts_at: competition.starts_at, ends_at: competition.ends_at
      },
      rules: {currency: "USD", initial_capital: "3000.00"}
    };
    portfolios.set(competition.id, {
      id: `portfolio-${competition.id}`, competition_id: competition.id,
      user_id: "owner-e2e", currency: "USD", initial_cash: "3000.00",
      cash: "3000.00", joined_at: competition.started_at, joined_late: false,
      positions: [], orders: [], executions: [], equity: "3000.00",
      cumulative_return: "0.000000000000"
    });
    return json(response, 200, competition);
  }
  const portfolioRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/portfolio$/);
  if (request.method === "GET" && portfolioRoute) {
    const portfolio = portfolios.get(portfolioRoute[1]);
    return portfolio ? json(response, 200, portfolio) : json(response, 404, {error: "not_found"});
  }
  const ordersRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/orders$/);
  if (request.method === "POST" && ordersRoute) {
    const portfolio = portfolios.get(ordersRoute[1]);
    if (!portfolio) return json(response, 404, {error: "not_found"});
    const input = await body(request);
    const order = {
      id: input.client_order_id, symbol: input.symbol, side: input.side,
      quantity: input.quantity, order_type: input.order_type,
      allow_extended_hours: input.allow_extended_hours,
      limit_price: input.limit_price, status: "filled", rejection_reason: null,
      submitted_at: "2026-09-02T14:30:00Z"
    };
    portfolio.orders.push(order);
    portfolio.executions.push({
      id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol,
      side: order.side, quantity: order.quantity, price: "100.0000",
      commission: "0.99", session: "regular",
      executed_at: "2026-09-02T14:31:00Z", source: "fixture",
      total_amount: null, currency: "USD", fx_rate: "1", correction_of: null
    });
    portfolio.cash = "2799.01";
    portfolio.equity = "2999.01";
    portfolio.cumulative_return = "-0.000330000000";
    portfolio.positions = [{
      symbol: order.symbol, quantity: order.quantity,
      price: "100.0000", market_value: "200.00"
    }];
    return json(response, 201, portfolio);
  }
  const reportedRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/reported-trades$/);
  if (request.method === "POST" && reportedRoute) {
    const portfolio = portfolios.get(reportedRoute[1]);
    if (!portfolio) return json(response, 404, {error: "not_found"});
    const input = await body(request);
    const order = {
      id: `reported-${input.client_trade_id}`, symbol: input.ticker,
      side: input.type, quantity: input.quantity, order_type: "market",
      allow_extended_hours: false, limit_price: null, status: "filled",
      rejection_reason: null, submitted_at: input.date
    };
    portfolio.orders.push(order);
    portfolio.executions.push({
      id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol,
      side: order.side, quantity: order.quantity, price: "50.0000",
      commission: "0.99", session: "regular", executed_at: input.date,
      source: "reported", total_amount: input.total_amount,
      currency: "USD", fx_rate: "1", correction_of: null
    });
    portfolio.cash = "2773.02";
    portfolio.equity = "3023.02";
    portfolio.cumulative_return = "0.007673333333";
    portfolio.positions = [{
      symbol: order.symbol, quantity: "2.5",
      price: "100.0000", market_value: "250.00"
    }];
    return json(response, 201, portfolio);
  }
  const cancelRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/orders\/([^/]+)$/);
  if (request.method === "DELETE" && cancelRoute) {
    const portfolio = portfolios.get(cancelRoute[1]);
    const order = portfolio?.orders.find(item => item.id === cancelRoute[2]);
    if (!order) return json(response, 404, {error: "not_found"});
    if (order.status !== "pending") return json(response, 409, {error: "conflict"});
    order.status = "cancelled";
    return json(response, 200, portfolio);
  }
  const rankingRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/ranking$/);
  if (request.method === "GET" && rankingRoute) {
    const portfolio = portfolios.get(rankingRoute[1]);
    if (!portfolio) return json(response, 404, {error: "not_found"});
    const ownerReturn = portfolio.cumulative_return;
    const ownerRank = ownerReturn.startsWith("-") ? 2 : 1;
    return json(response, 200, {
      competition_id: rankingRoute[1], as_of: "2026-09-02T20:00:00Z",
      digest: "a".repeat(64), rows: [
        {rank: ownerRank === 1 ? 2 : 1, user_id: "member-e2e", portfolio_id: "portfolio-member", display_name: "Member E2E", cumulative_return: "0.000000000000", joined_late: true},
        {rank: ownerRank, user_id: "owner-e2e", portfolio_id: portfolio.id, display_name: "Owner E2E", cumulative_return: ownerReturn, joined_late: false}
      ].sort((a, b) => a.rank - b.rank)
    });
  }
  return json(response, 404, {error: "not_found"});
}).listen(18080, "127.0.0.1");
