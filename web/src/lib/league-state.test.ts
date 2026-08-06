import {describe, expect, it} from "vitest";
import type {LeagueDetail} from "./api";
import {canCreateFreeLeague, canManageLeague, occupiedSeats} from "./league-state";

function league(overrides: Partial<LeagueDetail> = {}): LeagueDetail {
  return {
    id: "league-1", name: "Private", owner_id: "owner-1",
    created_at: "2026-08-06T10:00:00Z", active: true, plan: "free",
    actor_role: "owner", max_members: 2,
    members: [{user_id: "owner-1", display_name: "Owner", role: "owner", joined_at: "2026-08-06T10:00:00Z"}],
    invitations: [], ...overrides
  };
}

describe("league PWA state", () => {
  it("counts a pending invitation as the second Free seat", () => {
    const value = league({invitations: [{
      id: "invite-1", email: "member@example.com", role: "member",
      expires_at: "2026-08-13T10:00:00Z", status: "pending"
    }]});
    expect(occupiedSeats(value)).toBe(2);
  });

  it("shows management only to owner/admin and prevents a second owned league", () => {
    expect(canManageLeague(league())).toBe(true);
    expect(canManageLeague(league({actor_role: "member"}))).toBe(false);
    expect(canCreateFreeLeague([league()])).toBe(false);
    expect(canCreateFreeLeague([league({actor_role: "member"})])).toBe(true);
  });
});
