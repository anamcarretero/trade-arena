BEGIN;

CREATE INDEX active_memberships_by_league
    ON league_memberships(league_id, joined_at)
    WHERE removed_at IS NULL;

CREATE INDEX pending_invitations_by_email
    ON league_invitations(lower(email), expires_at)
    WHERE status = 'pending';

INSERT INTO schema_migrations(version) VALUES ('003_league_reads');

COMMIT;
