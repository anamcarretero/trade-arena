import {createServer} from "node:http";

const identities = {
  "e2e-session": {id: "owner-e2e", email: "owner@example.com", name: "Owner E2E"},
  "e2e-session-member": {id: "member-e2e", email: "member@example.com", name: "Member E2E"},
  "e2e-session-outsider": {id: "outsider-e2e", email: "outsider@example.com", name: "Outsider E2E"}
};

let state;

function resetState({seed = false} = {}) {
  state = {
    league: null,
    competitions: [],
    portfolios: new Map(),
    deletedSessions: new Set(),
    dashboardMode: "complete",
    dashboardDelay: 0,
    notifications: new Map(Object.values(identities).map(identity => [identity.id, [{
      id: `notification-${identity.id}`, kind: "competition.started",
      payload: {message: identity.id === "owner-e2e" ? "Temporada preparada" : "Invitation accepted"},
      created_at: "2026-08-06T12:00:00Z", read_at: null
    }]]))
  };
  if (seed) seedCompetition();
}

function seedCompetition() {
  state.league = baseLeague();
  state.league.members.push(member("member-e2e", "member"));
  const competition = {
    id: "competition-1", league_id: "league-e2e", name: "Otoño E2E",
    starts_at: "2026-09-01T00:00:00Z", ends_at: "2026-09-30T23:59:59Z",
    status: "active", started_at: "2026-08-06T12:00:00Z", rules_snapshot: rules()
  };
  state.competitions.push(competition);
  for (const actorId of ["owner-e2e", "member-e2e"]) {
    state.portfolios.set(portfolioKey(competition.id, actorId), emptyPortfolio(competition, actorId));
  }
}

function baseLeague() {
  return {
    id: "league-e2e", name: "Liga E2E", owner_id: "owner-e2e",
    created_at: "2026-08-01T12:00:00Z", active: true, plan: "free",
    max_members: 2, members: [member("owner-e2e", "owner")], invitations: []
  };
}

function member(userId, role) {
  return {
    user_id: userId, display_name: identities[Object.keys(identities).find(key => identities[key].id === userId)]?.name,
    role, joined_at: role === "owner" ? "2026-08-01T12:00:00Z" : "2026-08-02T12:00:00Z"
  };
}

function rules() {
  return {
    version: "1",
    calendar: {market: "XNYS", timezone: "America/New_York", starts_at: "2026-09-01T00:00:00Z", ends_at: "2026-09-30T23:59:59Z"},
    rules: {currency: "USD", initial_capital: "3000.00"}
  };
}

function emptyPortfolio(competition, actorId) {
  return {
    id: `portfolio-${actorId}`, competition_id: competition.id, user_id: actorId,
    currency: "USD", initial_cash: "3000.00", cash: "3000.00",
    joined_at: competition.starts_at, joined_late: false, positions: [], orders: [],
    executions: [], equity: "3000.00", cumulative_return: "0.000000000000"
  };
}

function portfolioKey(competitionId, actorId) { return `${competitionId}:${actorId}`; }
function sleep(milliseconds) { return new Promise(resolve => setTimeout(resolve, milliseconds)); }

function json(response, status, payload) {
  response.writeHead(status, {"Content-Type": "application/json"});
  response.end(JSON.stringify(payload));
}

function empty(response, status) { response.writeHead(status); response.end(); }

async function requestBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : {};
}

function actorLeague(actorId) {
  if (!state.league?.members.some(item => item.user_id === actorId)) return null;
  return {...state.league, actor_role: actorId === "owner-e2e" ? "owner" : "member"};
}

function ownInvitations(actor) {
  if (!state.league) return [];
  return state.league.invitations.filter(item => item.email === actor.email).map(item => ({
    id: item.id, league_name: state.league.name, expires_at: item.expires_at
  }));
}

resetState();

createServer(async (request, response) => {
  const url = new URL(request.url, "http://127.0.0.1:18080");
  const path = url.pathname;
  if (path === "/health/live") return json(response, 200, {status: "ok"});
  if (request.method === "POST" && path === "/__e2e/reset") {
    const input = await requestBody(request);
    resetState({seed: input.seed === true});
    return empty(response, 204);
  }
  if (request.method === "POST" && path === "/__e2e/dashboard") {
    const input = await requestBody(request);
    state.dashboardMode = input.mode ?? "complete";
    state.dashboardDelay = input.delay ?? 0;
    return empty(response, 204);
  }

  const token = request.headers.authorization?.replace("Bearer ", "");
  const actor = identities[token];
  if (!actor || state.deletedSessions.has(token)) return json(response, 403, {error: "forbidden"});

  if (request.method === "GET" && path === "/api/v1/me") {
    return json(response, 200, {
      schema_version: "1",
      user: {id: actor.id, email: actor.email, created_at: "2026-08-01T12:00:00Z"},
      profile: {display_name: actor.name, locale: actor.id === "member-e2e" ? "en" : "es", birth_date: "1990-01-01"},
      memberships: actorLeague(actor.id) ? [{league_id: "league-e2e", user_id: actor.id}] : [],
      invitations: ownInvitations(actor), notifications: state.notifications.get(actor.id), audit: [],
      financial_history: [...state.portfolios.values()].filter(item => item.user_id === actor.id).map(portfolio => ({
        competition: {id: portfolio.competition_id}, portfolio: {...portfolio, ledger: []}
      }))
    });
  }
  if (request.method === "DELETE" && path === "/api/v1/me") {
    const input = await requestBody(request);
    if (input.confirm_account_deletion !== true) return json(response, 400, {error: "invalid_input"});
    state.deletedSessions.add(token);
    return empty(response, 204);
  }
  if (request.method === "GET" && path === "/api/v1/notifications") return json(response, 200, state.notifications.get(actor.id));
  const notificationRead = path.match(/^\/api\/v1\/notifications\/([^/]+)\/read$/);
  if (request.method === "POST" && notificationRead) {
    const item = state.notifications.get(actor.id).find(row => row.id === notificationRead[1]);
    if (!item) return json(response, 404, {error: "not_found"});
    item.read_at ??= "2026-08-06T13:00:00Z";
    return json(response, 200, item);
  }

  if (path === "/api/v1/leagues") {
    if (request.method === "GET") return json(response, 200, actorLeague(actor.id) ? [actorLeague(actor.id)] : []);
    if (request.method === "POST") {
      if (actor.id !== "owner-e2e" || state.league) return json(response, 409, {error: "conflict"});
      const input = await requestBody(request);
      state.league = {...baseLeague(), name: input.name};
      return json(response, 201, actorLeague(actor.id));
    }
  }
  if (request.method === "GET" && path === "/api/v1/invitations") return json(response, 200, ownInvitations(actor));
  const acceptInvitation = path.match(/^\/api\/v1\/invitations\/([^/]+)$/);
  if (request.method === "POST" && acceptInvitation) {
    const invitation = state.league?.invitations.find(item => item.id === acceptInvitation[1] && item.email === actor.email);
    if (!invitation) return json(response, 404, {error: "not_found"});
    state.league.invitations = state.league.invitations.filter(item => item.id !== invitation.id);
    state.league.members.push(member(actor.id, "member"));
    return json(response, 200, {league_id: state.league.id, user_id: actor.id});
  }

  const leagueRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)$/);
  if (request.method === "GET" && leagueRoute) {
    const visible = leagueRoute[1] === state.league?.id ? actorLeague(actor.id) : null;
    return visible ? json(response, 200, visible) : json(response, 404, {error: "not_found"});
  }
  const invitationRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/invitations$/);
  if (request.method === "POST" && invitationRoute) {
    if (actor.id !== "owner-e2e" || invitationRoute[1] !== state.league?.id) return json(response, 404, {error: "not_found"});
    const input = await requestBody(request);
    const invitation = {id: "invitation-e2e", email: input.email.toLowerCase(), expires_at: "2026-08-14T12:00:00Z", status: "pending"};
    state.league.invitations.push(invitation);
    return json(response, 201, invitation);
  }

  const competitionsRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions$/);
  if (competitionsRoute) {
    if (!actorLeague(actor.id) || competitionsRoute[1] !== state.league.id) return json(response, 404, {error: "not_found"});
    if (request.method === "GET") return json(response, 200, state.competitions);
    if (request.method === "POST") {
      if (actor.id !== "owner-e2e") return json(response, 404, {error: "not_found"});
      const input = await requestBody(request);
      const competition = {id: `competition-${state.competitions.length + 1}`, league_id: state.league.id, name: input.name, starts_at: input.starts_at, ends_at: input.ends_at, status: "draft", rules_snapshot: null, started_at: null};
      state.competitions.push(competition);
      return json(response, 201, competition);
    }
  }
  const startRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/start$/);
  if (request.method === "POST" && startRoute) {
    if (actor.id !== "owner-e2e" || startRoute[1] !== state.league?.id) return json(response, 404, {error: "not_found"});
    const competition = state.competitions.find(item => item.id === startRoute[2]);
    if (!competition) return json(response, 404, {error: "not_found"});
    competition.status = "active"; competition.started_at = "2026-08-06T12:00:00Z";
    competition.rules_snapshot = rules();
    for (const item of state.league.members) state.portfolios.set(portfolioKey(competition.id, item.user_id), emptyPortfolio(competition, item.user_id));
    return json(response, 200, competition);
  }

  const portfolioRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/portfolio$/);
  if (request.method === "GET" && portfolioRoute) {
    if (!actorLeague(actor.id) || portfolioRoute[1] !== state.league.id) return json(response, 404, {error: "not_found"});
    const portfolio = state.portfolios.get(portfolioKey(portfolioRoute[2], actor.id));
    return portfolio ? json(response, 200, portfolio) : json(response, 404, {error: "not_found"});
  }
  const orderRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/orders$/);
  if (request.method === "POST" && orderRoute) {
    const portfolio = state.portfolios.get(portfolioKey(orderRoute[2], actor.id));
    if (!portfolio || orderRoute[1] !== state.league?.id) return json(response, 404, {error: "not_found"});
    const input = await requestBody(request);
    const order = {id: input.client_order_id, symbol: input.symbol, side: input.side, quantity: input.quantity, order_type: input.order_type, allow_extended_hours: input.allow_extended_hours, limit_price: input.limit_price, status: "filled", rejection_reason: null, submitted_at: "2026-09-02T14:30:00Z", commission: input.commission};
    portfolio.orders.push(order);
    portfolio.executions.push({id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol, side: order.side, quantity: order.quantity, price: "100.0000", commission: input.commission?.replace(",", ".") ?? "1.15", session: "regular", executed_at: "2026-09-02T14:31:00Z", source: "fixture", total_amount: null, currency: "USD", fx_rate: "1", correction_of: null});
    portfolio.cash = "2799.25"; portfolio.equity = "2999.25"; portfolio.cumulative_return = "-0.000250000000";
    portfolio.positions = [{symbol: order.symbol, quantity: order.quantity, price: "100.0000", market_value: "200.00"}];
    return json(response, 201, portfolio);
  }
  const reportedRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/reported-trades$/);
  if (request.method === "POST" && reportedRoute) {
    const portfolio = state.portfolios.get(portfolioKey(reportedRoute[2], actor.id));
    if (!portfolio || reportedRoute[1] !== state.league?.id) return json(response, 404, {error: "not_found"});
    const input = await requestBody(request);
    const order = {id: `reported-${input.client_trade_id}`, symbol: input.ticker, side: input.type, quantity: input.quantity, order_type: "market", allow_extended_hours: false, limit_price: null, status: "filled", rejection_reason: null, submitted_at: input.date, commission: input.commission?.replace(",", ".") ?? "1.15"};
    portfolio.orders.push(order);
    portfolio.executions.push({id: `execution-${order.id}`, order_id: order.id, symbol: order.symbol, side: order.side, quantity: order.quantity, price: input.price_per_share.replace(",", "."), commission: order.commission, session: "regular", executed_at: input.date, source: "reported", total_amount: input.total_amount, currency: "USD", fx_rate: "1", correction_of: null});
    portfolio.cash = "2143.15"; portfolio.equity = "3043.15"; portfolio.cumulative_return = "0.014383333333";
    portfolio.positions = [{symbol: order.symbol, quantity: order.quantity, price: input.price_per_share.replace(",", "."), market_value: "900.00"}];
    return json(response, 201, portfolio);
  }
  const cancelRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/orders\/([^/]+)$/);
  if (request.method === "DELETE" && cancelRoute) {
    const portfolio = state.portfolios.get(portfolioKey(cancelRoute[2], actor.id));
    const order = portfolio?.orders.find(item => item.id === cancelRoute[3]);
    if (!order || cancelRoute[1] !== state.league?.id) return json(response, 404, {error: "not_found"});
    if (order.status !== "pending") return json(response, 409, {error: "conflict"});
    order.status = "cancelled";
    return json(response, 200, portfolio);
  }
  const rankingRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/ranking$/);
  if (request.method === "GET" && rankingRoute) {
    if (!actorLeague(actor.id) || rankingRoute[1] !== state.league.id) return json(response, 404, {error: "not_found"});
    const rows = state.league.members.map(item => {
      const portfolio = state.portfolios.get(portfolioKey(rankingRoute[2], item.user_id));
      return {user_id: item.user_id, portfolio_id: portfolio?.id, display_name: item.display_name, cumulative_return: portfolio?.cumulative_return ?? "0", joined_late: false};
    }).sort((a, b) => Number(b.cumulative_return) - Number(a.cumulative_return)).map((row, index) => ({...row, rank: index + 1}));
    return json(response, 200, {competition_id: rankingRoute[2], as_of: "2026-09-03T20:00:00Z", digest: "a".repeat(64), rows});
  }
  const dashboardRoute = path.match(/^\/api\/v1\/leagues\/([^/]+)\/competitions\/([^/]+)\/dashboard$/);
  if (request.method === "GET" && dashboardRoute) {
    if (!actorLeague(actor.id) || dashboardRoute[1] !== state.league.id) return json(response, 404, {error: "not_found"});
    if (state.dashboardDelay) await sleep(state.dashboardDelay);
    if (state.dashboardMode === "error") return json(response, 500, {error: "fixture_failure"});
    const competition = state.competitions.find(item => item.id === dashboardRoute[2]);
    if (!competition) return json(response, 404, {error: "not_found"});
    return json(response, 200, dashboard(competition));
  }
  return json(response, 404, {error: "not_found"});
}).listen(18080, "127.0.0.1");

function dashboard(competition) {
  if (competition.status === "draft") return {competition, data_status: "empty", players: [], summary: {leader: null, best_day: null, gap: "0"}, monthly: {current: null, previous: null}, daily_winners: [], daily_results: [], league_allocation: [], recent_trades: [], badges: [], insights: [], missing_data: [], ticker_record: null};
  const rows = state.league.members.map(item => {
    const portfolio = state.portfolios.get(portfolioKey(competition.id, item.user_id));
    return {id: item.user_id, display_name: item.display_name, active: true, joined_at: portfolio.joined_at, joined_late: false, as_of: "2026-09-03T20:00:00Z", cumulative_return: portfolio.cumulative_return, statistics: {best_daily_return: portfolio.cumulative_return, worst_daily_return: portfolio.cumulative_return, current_streak: Number(portfolio.cumulative_return) >= 0 ? 1 : -1, sessions: 1}, allocation: portfolio.positions.length ? [{symbol: "CASH", weight: "0.70"}, {symbol: portfolio.positions[0].symbol, weight: "0.30"}] : [{symbol: "CASH", weight: "1"}], badges: []};
  }).sort((a, b) => Number(b.cumulative_return) - Number(a.cumulative_return)).map((row, index) => ({...row, rank: index + 1, series: [{date: "2026-09-03", as_of: "2026-09-03T20:00:00Z", provisional: false, daily_return: row.cumulative_return, cumulative_return: row.cumulative_return, complete: state.dashboardMode !== "incomplete"}]}));
  const leader = rows[0];
  const trades = [...state.portfolios.values()].filter(item => item.competition_id === competition.id).flatMap(portfolio => portfolio.executions.map(execution => ({player_id: portfolio.user_id, display_name: identities[Object.keys(identities).find(key => identities[key].id === portfolio.user_id)].name, executed_at: execution.executed_at, symbol: execution.symbol, type: execution.correction_of ? "correction" : execution.side, source: execution.source}))).slice(-8).reverse();
  const incomplete = state.dashboardMode === "incomplete";
  return {
    competition: {id: competition.id, league_id: state.league.id, name: competition.name, status: competition.status, starts_at: competition.starts_at, ends_at: competition.ends_at, market_calendar: "XNYS", updated_at: "2026-09-03T20:00:00Z"},
    data_status: incomplete ? "incomplete" : "complete", players: rows,
    summary: {leader: {player_id: leader.id, display_name: leader.display_name, cumulative_return: leader.cumulative_return}, best_day: {date: "2026-09-03", player_ids: [leader.id], return: leader.cumulative_return, provisional: false}, gap: String(Math.abs(Number(rows[0].cumulative_return) - Number(rows.at(-1).cumulative_return)))},
    monthly: {current: {month: "2026-09", winner: {player_id: leader.id, return: leader.cumulative_return}, series: rows.map(row => ({player_id: row.id, display_name: row.display_name, points: [{date: "2026-09-03", return: row.cumulative_return}]}))}, previous: null},
    daily_winners: [{date: "2026-09-03", player_ids: [leader.id], return: leader.cumulative_return, provisional: false}],
    daily_results: [{date: "2026-09-03", provisional: false, players: rows.map(row => ({player_id: row.id, display_name: row.display_name, daily_return: incomplete ? null : row.cumulative_return, cumulative_return: row.cumulative_return, complete: !incomplete}))}],
    league_allocation: [{symbol: "CASH", weight: "0.85"}, {symbol: "AAPL", weight: "0.15"}], recent_trades: trades,
    badges: [], insights: [{kind: "leader", player_id: leader.id, value: leader.cumulative_return}],
    missing_data: incomplete ? [{date: "2026-09-03", symbol: "AAPL"}] : [], ticker_record: null
  };
}
