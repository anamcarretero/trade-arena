BEGIN;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS commission numeric(20,2),
    ADD CONSTRAINT orders_commission_non_negative
        CHECK (commission IS NULL OR commission >= 0);

INSERT INTO schema_migrations(version) VALUES ('007_user_commissions')
ON CONFLICT DO NOTHING;

COMMIT;
