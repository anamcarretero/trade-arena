BEGIN;

ALTER TABLE portfolio_snapshots
    ADD COLUMN IF NOT EXISTS trading_day date,
    ADD COLUMN IF NOT EXISTS provisional boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS calculation_version text NOT NULL DEFAULT 'dashboard-v1';

ALTER TABLE ranking_snapshots
    ADD COLUMN IF NOT EXISTS trading_day date,
    ADD COLUMN IF NOT EXISTS provisional boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS calculation_version text NOT NULL DEFAULT 'dashboard-v1';

CREATE UNIQUE INDEX IF NOT EXISTS portfolio_snapshots_canonical_day
    ON portfolio_snapshots(portfolio_id, trading_day, provisional)
    WHERE trading_day IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ranking_snapshots_canonical_day
    ON ranking_snapshots(competition_id, trading_day, provisional)
    WHERE trading_day IS NOT NULL;
CREATE INDEX IF NOT EXISTS portfolio_snapshots_projection_history
    ON portfolio_snapshots(portfolio_id, trading_day, as_of);
CREATE INDEX IF NOT EXISTS ranking_snapshots_projection_history
    ON ranking_snapshots(competition_id, trading_day, as_of);

CREATE TABLE IF NOT EXISTS competition_badges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id uuid NOT NULL REFERENCES competitions(id),
    user_id uuid NOT NULL REFERENCES users(id),
    achievement_key text NOT NULL,
    achieved_on date NOT NULL,
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL,
    UNIQUE (competition_id, user_id, achievement_key)
);
CREATE INDEX IF NOT EXISTS competition_badges_history
    ON competition_badges(competition_id, achieved_on, user_id, achievement_key);

INSERT INTO schema_migrations(version) VALUES ('010_competition_dashboard')
ON CONFLICT DO NOTHING;

COMMIT;
