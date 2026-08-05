BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'deleted')),
    created_at timestamptz NOT NULL,
    deleted_at timestamptz,
    UNIQUE (email)
);
CREATE UNIQUE INDEX users_email_case_insensitive ON users(lower(email));
CREATE TABLE identities (
    provider text NOT NULL CHECK (provider IN ('email', 'google', 'apple')),
    subject text NOT NULL,
    user_id uuid NOT NULL REFERENCES users(id),
    email_verified boolean NOT NULL,
    PRIMARY KEY (provider, subject)
);
CREATE TABLE profiles (
    user_id uuid PRIMARY KEY REFERENCES users(id),
    display_name text NOT NULL,
    locale text NOT NULL CHECK (locale IN ('es', 'en')),
    birth_date date NOT NULL,
    accepted_terms_at timestamptz NOT NULL
);
CREATE TABLE sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    token_hash bytea NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz
);
CREATE TABLE access_audit (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL,
    actor_id uuid REFERENCES users(id),
    action text NOT NULL,
    resource_type text NOT NULL,
    resource_id text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE leagues (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES users(id),
    name text NOT NULL,
    plan text NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'friends', 'club')),
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL
);
CREATE UNIQUE INDEX one_active_free_league_per_owner
    ON leagues(owner_id) WHERE active AND plan = 'free';
CREATE TABLE league_memberships (
    league_id uuid NOT NULL REFERENCES leagues(id),
    user_id uuid NOT NULL REFERENCES users(id),
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
    joined_at timestamptz NOT NULL,
    removed_at timestamptz,
    PRIMARY KEY (league_id, user_id)
);
CREATE TABLE league_invitations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES leagues(id),
    email text NOT NULL,
    role text NOT NULL CHECK (role IN ('admin', 'member')),
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    accepted_by uuid REFERENCES users(id)
);
CREATE INDEX pending_invitations_by_league
    ON league_invitations(league_id, expires_at) WHERE status = 'pending';

CREATE TABLE competitions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    league_id uuid NOT NULL REFERENCES leagues(id),
    name text NOT NULL,
    starts_at timestamptz NOT NULL,
    ends_at timestamptz NOT NULL,
    status text NOT NULL CHECK (status IN ('draft', 'active', 'finished')),
    rules_snapshot jsonb NOT NULL,
    CHECK (ends_at > starts_at)
);
CREATE TABLE competition_participants (
    competition_id uuid NOT NULL REFERENCES competitions(id),
    user_id uuid NOT NULL REFERENCES users(id),
    joined_at timestamptz NOT NULL,
    removed_at timestamptz,
    PRIMARY KEY (competition_id, user_id)
);
CREATE TABLE portfolios (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id uuid NOT NULL REFERENCES competitions(id),
    user_id uuid NOT NULL REFERENCES users(id),
    currency char(3) NOT NULL CHECK (currency = 'USD'),
    initial_cash numeric(20,2) NOT NULL CHECK (initial_cash > 0),
    UNIQUE (competition_id, user_id)
);
CREATE TABLE cash_accounts (
    portfolio_id uuid PRIMARY KEY REFERENCES portfolios(id),
    balance numeric(20,2) NOT NULL
);
CREATE TABLE instruments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol text NOT NULL UNIQUE,
    kind text NOT NULL CHECK (kind IN ('stock', 'etf')),
    currency char(3) NOT NULL CHECK (currency = 'USD'),
    active boolean NOT NULL DEFAULT true
);
CREATE TABLE orders (
    id uuid PRIMARY KEY,
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    instrument_id uuid NOT NULL REFERENCES instruments(id),
    side text NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type text NOT NULL CHECK (order_type IN ('market', 'limit')),
    quantity bigint NOT NULL CHECK (quantity > 0),
    limit_price numeric(20,4),
    allow_extended_hours boolean NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'filled', 'rejected', 'cancelled')),
    submitted_at timestamptz NOT NULL,
    CHECK ((order_type = 'limit') = (limit_price IS NOT NULL))
);
CREATE TABLE executions (
    id uuid PRIMARY KEY,
    order_id uuid NOT NULL UNIQUE REFERENCES orders(id),
    quantity bigint NOT NULL CHECK (quantity > 0),
    price numeric(20,4) NOT NULL CHECK (price > 0),
    commission numeric(20,2) NOT NULL CHECK (commission >= 0),
    session text NOT NULL CHECK (session IN ('regular', 'extended')),
    executed_at timestamptz NOT NULL
);
CREATE TABLE ledger_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    sequence bigint NOT NULL,
    kind text NOT NULL,
    reference text NOT NULL,
    occurred_at timestamptz NOT NULL,
    UNIQUE (portfolio_id, sequence),
    UNIQUE (portfolio_id, kind, reference)
);
CREATE TABLE ledger_postings (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entry_id uuid NOT NULL REFERENCES ledger_entries(id),
    account text NOT NULL,
    amount numeric(24,4) NOT NULL
);

CREATE TABLE market_prices (
    instrument_id uuid NOT NULL REFERENCES instruments(id),
    observed_at timestamptz NOT NULL,
    price numeric(20,4) NOT NULL CHECK (price > 0),
    session text NOT NULL CHECK (session IN ('regular', 'extended')),
    provider text NOT NULL,
    delayed_until timestamptz NOT NULL,
    PRIMARY KEY (instrument_id, observed_at, provider)
);
CREATE TABLE market_calendar (
    market text NOT NULL,
    trading_day date NOT NULL,
    regular_open timestamptz,
    regular_close timestamptz,
    extended_open timestamptz,
    extended_close timestamptz,
    status text NOT NULL CHECK (status IN ('open', 'closed', 'suspended')),
    PRIMARY KEY (market, trading_day)
);
CREATE TABLE corporate_actions (
    id text PRIMARY KEY,
    instrument_id uuid NOT NULL REFERENCES instruments(id),
    kind text NOT NULL CHECK (kind IN ('dividend', 'split')),
    effective_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    provider text NOT NULL
);
CREATE TABLE portfolio_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    portfolio_id uuid NOT NULL REFERENCES portfolios(id),
    as_of timestamptz NOT NULL,
    equity numeric(20,2) NOT NULL,
    cumulative_return numeric(24,12) NOT NULL,
    state jsonb NOT NULL,
    digest char(64) NOT NULL,
    UNIQUE (portfolio_id, as_of),
    UNIQUE (portfolio_id, digest)
);
CREATE TABLE ranking_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id uuid NOT NULL REFERENCES competitions(id),
    as_of timestamptz NOT NULL,
    rows jsonb NOT NULL,
    digest char(64) NOT NULL,
    UNIQUE (competition_id, as_of),
    UNIQUE (competition_id, digest)
);

CREATE TABLE subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES users(id),
    provider text NOT NULL,
    provider_subscription_id text NOT NULL UNIQUE,
    status text NOT NULL,
    current_period_end timestamptz
);
CREATE TABLE entitlements (
    owner_id uuid NOT NULL REFERENCES users(id),
    entitlement text NOT NULL,
    value jsonb NOT NULL,
    valid_until timestamptz,
    PRIMARY KEY (owner_id, entitlement)
);
CREATE TABLE billing_events (
    provider text NOT NULL,
    provider_event_id text NOT NULL,
    received_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (provider, provider_event_id)
);
CREATE TABLE notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES users(id),
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    read_at timestamptz
);

INSERT INTO schema_migrations(version) VALUES ('001_initial');
COMMIT;
