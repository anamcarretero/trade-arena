BEGIN;

CREATE INDEX IF NOT EXISTS notifications_by_user_created
    ON notifications(user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS access_audit_by_actor_sequence
    ON access_audit(actor_id, sequence) WHERE actor_id IS NOT NULL;

INSERT INTO schema_migrations(version) VALUES ('009_notifications_privacy')
ON CONFLICT DO NOTHING;

COMMIT;
