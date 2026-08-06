BEGIN;

ALTER TABLE competitions
    ALTER COLUMN rules_snapshot DROP NOT NULL,
    ADD COLUMN IF NOT EXISTS started_at timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'competition_snapshot_lifecycle'
           AND conrelid = 'competitions'::regclass
    ) THEN
        ALTER TABLE competitions
            ADD CONSTRAINT competition_snapshot_lifecycle CHECK (
                (status = 'draft' AND rules_snapshot IS NULL AND started_at IS NULL)
                OR
                (status IN ('active', 'finished') AND rules_snapshot IS NOT NULL
                 AND started_at IS NOT NULL)
            );
    END IF;
END;
$$;

CREATE INDEX IF NOT EXISTS competitions_by_league
    ON competitions(league_id, starts_at, id);

CREATE OR REPLACE FUNCTION prevent_competition_snapshot_change()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.rules_snapshot IS NOT NULL
       AND NEW.rules_snapshot IS DISTINCT FROM OLD.rules_snapshot THEN
        RAISE EXCEPTION 'rules_snapshot es inmutable'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS immutable_competition_rules_snapshot ON competitions;
CREATE TRIGGER immutable_competition_rules_snapshot
BEFORE UPDATE ON competitions
FOR EACH ROW EXECUTE FUNCTION prevent_competition_snapshot_change();

INSERT INTO schema_migrations(version) VALUES ('004_competitions')
ON CONFLICT DO NOTHING;

COMMIT;
