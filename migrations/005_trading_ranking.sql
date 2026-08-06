BEGIN;

ALTER TABLE competition_participants
    ADD COLUMN IF NOT EXISTS joined_late boolean NOT NULL DEFAULT false;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS rejection_reason text;

ALTER TABLE executions DROP CONSTRAINT IF EXISTS executions_order_id_fkey;
ALTER TABLE orders ALTER COLUMN id TYPE text USING id::text;
ALTER TABLE executions
    ALTER COLUMN id TYPE text USING id::text,
    ALTER COLUMN order_id TYPE text USING order_id::text;
ALTER TABLE executions
    ADD CONSTRAINT executions_order_id_fkey FOREIGN KEY (order_id) REFERENCES orders(id);

CREATE TABLE IF NOT EXISTS portfolio_positions (
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    symbol text NOT NULL,
    quantity bigint NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (portfolio_id, symbol)
);

CREATE INDEX IF NOT EXISTS participants_by_competition
    ON competition_participants(competition_id, joined_at, user_id);
CREATE INDEX IF NOT EXISTS orders_by_portfolio_history
    ON orders(portfolio_id, submitted_at, id);
CREATE INDEX IF NOT EXISTS executions_by_order_time
    ON executions(order_id, executed_at);

INSERT INTO schema_migrations(version) VALUES ('005_trading_ranking')
ON CONFLICT DO NOTHING;

COMMIT;
