import {createServer} from "node:http";

const league = {
  id: "league-e2e", name: "Liga E2E", owner_id: "owner-e2e",
  created_at: "2026-08-01T12:00:00Z", active: true, plan: "free",
  actor_role: "owner", max_members: 2,
  members: [{
    user_id: "owner-e2e", display_name: "Owner E2E", role: "owner",
    joined_at: "2026-08-01T12:00:00Z"
  }], invitations: []
};
const competitions = [];

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
    return json(response, 200, competition);
  }
  return json(response, 404, {error: "not_found"});
}).listen(18080, "127.0.0.1");
