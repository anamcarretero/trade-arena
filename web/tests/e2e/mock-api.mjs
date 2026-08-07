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
const deletedSessions = new Set();
const notifications = new Map([
  ["owner-e2e", [{
    id: "notification-owner", kind: "competition.started",
    payload: {message: "Temporada preparada"},
    created_at: "2026-08-06T12:00:00Z", read_at: null
  }]],
  ["member-e2e", [{
    id: "notification-member", kind: "invitation.accepted",
    payload: {message: "Invitation accepted"},
    created_at: "2026-08-05T12:00:00Z", read_at: null
  }]]
]);

function json(response, status, body) {
  response.writeHead(status, {"Content-Type": "application/json"});
  response.end(JSON.stringify(body));
}

function empty(response, status) {
  response.writeHead(status);
  response.end();
}

async function body(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {};
}

createServer(async (request, response) => {
  const path = new URL(request.url, "http://127.0.0.1:18080").pathname;
  if (path === "/health/live") return json(response, 200, {status: "ok"});
  const token = request.headers.authorization?.replace("Bearer ", "");
  const actorId = token === "e2e-session" ? "owner-e2e"
    : token === "e2e-session-member" ? "member-e2e" : null;
  if (!actorId || deletedSessions.has(token)) {
    return json(response, 403, {error: "forbidden"});
  }
  if (request.method === "GET" && path === "/api/v1/me") {
    return json(response, 200, {
      schema_version: "1",
      user: {
        id: actorId,
        email: actorId === "owner-e2e" ? "owner@example.com" : "member@example.com",
        created_at: "2026-08-01T12:00:00Z"
      },
      profile: {
        display_name: actorId === "owner-e2e" ? "Owner E2E" : "Member E2E",
        locale: "es", birth_date: "1990-01-01"
      },
      memberships: [{league_id: "league-e2e", user_id: actorId}],
      invitations: [], notifications: notifications.get(actorId), audit: [],
      financial_history: [{
        competition: {id: "competition-export"},
        portfolio: {id: `portfolio-${actorId}`, user_id: actorId, ledger: []}
      }]
    });
  }
  if (request.method === "DELETE" && path === "/api/v1/me") {
    const input = await body(request);
    if (input.confirm_account_deletion !== true) {
      return json(response, 400, {error: "invalid_input"});
    }
    deletedSessions.add(token);
    return empty(response, 204);
  }
  if (request.method === "GET" && path === "/api/v1/notifications") {
    return json(response, 200, notifications.get(actorId));
  }
  const notificationRead = path.match(/^\/api\/v1\/notifications\/([^/]+)\/read$/);
  if (request.method === "POST" && notificationRead) {
    const item = notifications.get(actorId).find(row => row.id === notificationRead[1]);
    if (!item) return json(response, 404, {error: "not_found"});
    item.read_at ??= "2026-08-06T13:00:00Z";
    return json(response, 200, item);
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
      submitted_at: "2026-09-02T14:30:00Z", commission: input.commission
    };
    portfolio.orders.push(order);
    portfolio.executions.push({
      id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol,
      side: order.side, quantity: order.quantity, price: "100.0000",
      commission: input.commission?.replace(",", ".") ?? "1.15", session: "regular",
      executed_at: "2026-09-02T14:31:00Z", source: "fixture",
      total_amount: null, currency: "USD", fx_rate: "1", correction_of: null
    });
    portfolio.cash = "2799.25";
    portfolio.equity = "2999.25";
    portfolio.cumulative_return = "-0.000250000000";
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
      rejection_reason: null, submitted_at: input.date,
      commission: input.commission?.replace(",", ".") ?? "1.15"
    };
    portfolio.orders.push(order);
    portfolio.executions.push({
      id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol,
      side: order.side, quantity: order.quantity,
      price: input.price_per_share.replace(",", "."),
      commission: input.commission?.replace(",", ".") ?? "1.15",
      session: "regular", executed_at: input.date,
      source: "reported", total_amount: input.total_amount,
      currency: "USD", fx_rate: "1", correction_of: null
    });
    portfolio.cash = "1942.00";
    portfolio.equity = "3042.00";
    portfolio.cumulative_return = "0.014000000000";
    portfolio.positions = [{
      symbol: order.symbol, quantity: "3",
      price: "366.6667", market_value: "1100.00"
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
  const dashboardRoute = path.match(/^\/api\/v1\/leagues\/league-e2e\/competitions\/([^/]+)\/dashboard$/);
  if (request.method === "GET" && dashboardRoute) {
    const competition = competitions.find(item => item.id === dashboardRoute[1]);
    if (!competition) return json(response, 404, {error: "not_found"});
    if (competition.status === "draft") return json(response, 200, {
      competition: {id: competition.id, league_id: league.id, name: competition.name, status: "draft", starts_at: competition.starts_at, ends_at: competition.ends_at, market_calendar: "XNYS", updated_at: null},
      data_status: "empty", players: [], summary: {leader: null, best_day: null, gap: "0"},
      monthly: {current: null, previous: null}, daily_winners: [], daily_results: [],
      league_allocation: [], recent_trades: [], badges: [], insights: [], missing_data: [], ticker_record: null
    });
    const portfolio = portfolios.get(competition.id);
    const ownerReturn = portfolio?.cumulative_return ?? "0";
    const point = (playerReturn) => ({date: "2026-09-03", as_of: "2026-09-03T20:00:00Z", provisional: false, daily_return: playerReturn, cumulative_return: playerReturn, complete: true});
    const allocation = [{symbol: "CASH", weight: "0.65"}, {symbol: "AAPL", weight: "0.35"}];
    const players = [
      {id: "member-e2e", display_name: "Member E2E", rank: ownerReturn.startsWith("-") ? 1 : 2, active: true, joined_at: "2026-09-02T12:00:00Z", joined_late: true, as_of: "2026-09-03T20:00:00Z", cumulative_return: "0.010000000000", statistics: {best_daily_return: "0.01", worst_daily_return: "0.01", current_streak: 1, sessions: 1}, series: [point("0.01")], allocation, badges: []},
      {id: "owner-e2e", display_name: "Owner E2E", rank: ownerReturn.startsWith("-") ? 2 : 1, active: true, joined_at: "2026-09-01T00:00:00Z", joined_late: false, as_of: "2026-09-03T20:00:00Z", cumulative_return: ownerReturn, statistics: {best_daily_return: ownerReturn, worst_daily_return: ownerReturn, current_streak: Number(ownerReturn) >= 0 ? 1 : -1, sessions: 1}, series: [point(ownerReturn)], allocation, badges: []}
    ].sort((a, b) => a.rank - b.rank);
    const leader = players[0];
    const recentTrades = (portfolio?.executions ?? []).slice(-8).reverse().map(execution => ({
      player_id: "owner-e2e", display_name: "Owner E2E", executed_at: execution.executed_at,
      symbol: execution.symbol, type: execution.correction_of ? "correction" : execution.side,
      source: execution.source
    }));
    return json(response, 200, {
      competition: {id: competition.id, league_id: league.id, name: competition.name, status: "active", starts_at: competition.starts_at, ends_at: competition.ends_at, market_calendar: "XNYS", updated_at: "2026-09-03T20:00:00Z"},
      data_status: "complete", players,
      summary: {leader: {player_id: leader.id, display_name: leader.display_name, cumulative_return: leader.cumulative_return}, best_day: {date: "2026-09-03", player_ids: [leader.id], return: leader.cumulative_return, provisional: false}, gap: String(Math.abs(Number(players[0].cumulative_return) - Number(players[1].cumulative_return)))},
      monthly: {current: {month: "2026-09", winner: {player_id: leader.id, return: leader.cumulative_return}, series: players.map(player => ({player_id: player.id, display_name: player.display_name, points: [{date: "2026-09-03", return: player.cumulative_return}]}))}, previous: {month: "2026-08", winner: null, series: []}},
      daily_winners: [{date: "2026-09-03", player_ids: [leader.id], return: leader.cumulative_return, provisional: false}],
      daily_results: [{date: "2026-09-03", provisional: false, players: players.map(player => ({player_id: player.id, display_name: player.display_name, daily_return: player.cumulative_return, cumulative_return: player.cumulative_return, complete: true}))}],
      league_allocation: allocation, recent_trades: recentTrades,
      badges: [], insights: [{kind: "leader", player_id: leader.id, value: leader.cumulative_return}],
      missing_data: [], ticker_record: null
    });
  }
  return json(response, 404, {error: "not_found"});
}).listen(18080, "127.0.0.1");
