import type {LeagueDetail} from "./api";

export function occupiedSeats(league: LeagueDetail) {
  return league.members.length + league.invitations.length;
}

export function canManageLeague(league: LeagueDetail) {
  return league.actor_role === "owner" || league.actor_role === "admin";
}

export function canCreateFreeLeague(leagues: LeagueDetail[]) {
  return !leagues.some(league =>
    league.actor_role === "owner" && league.active && league.plan === "free"
  );
}
