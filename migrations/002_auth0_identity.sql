BEGIN;

ALTER TABLE identities
    DROP CONSTRAINT identities_provider_check;

ALTER TABLE identities
    ADD CONSTRAINT identities_provider_check
    CHECK (provider IN ('email', 'google', 'apple', 'auth0'));

INSERT INTO schema_migrations(version) VALUES ('002_auth0_identity');

COMMIT;
