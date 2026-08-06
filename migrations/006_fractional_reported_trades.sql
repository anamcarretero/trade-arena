BEGIN;

ALTER TABLE orders
    ALTER COLUMN quantity TYPE numeric(28,8) USING quantity::numeric(28,8);
ALTER TABLE executions
    ALTER COLUMN quantity TYPE numeric(28,8) USING quantity::numeric(28,8);
ALTER TABLE portfolio_positions
    ALTER COLUMN quantity TYPE numeric(28,8) USING quantity::numeric(28,8);

ALTER TABLE executions
    ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'fixture',
    ADD COLUMN IF NOT EXISTS total_amount numeric(20,2),
    ADD COLUMN IF NOT EXISTS currency char(3) NOT NULL DEFAULT 'USD',
    ADD COLUMN IF NOT EXISTS fx_rate numeric(20,8) NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS correction_of text REFERENCES executions(id);

ALTER TABLE executions
    ADD CONSTRAINT executions_source_check CHECK (source IN ('fixture', 'reported')),
    ADD CONSTRAINT executions_currency_check CHECK (currency = 'USD'),
    ADD CONSTRAINT executions_fx_rate_check CHECK (fx_rate = 1),
    ADD CONSTRAINT executions_reported_total_check CHECK (
        (source = 'fixture' AND total_amount IS NULL)
        OR (source = 'reported' AND total_amount IS NOT NULL)
    );

CREATE UNIQUE INDEX IF NOT EXISTS one_correction_per_execution
    ON executions(correction_of) WHERE correction_of IS NOT NULL;

INSERT INTO schema_migrations(version) VALUES ('006_fractional_reported_trades')
ON CONFLICT DO NOTHING;

COMMIT;
