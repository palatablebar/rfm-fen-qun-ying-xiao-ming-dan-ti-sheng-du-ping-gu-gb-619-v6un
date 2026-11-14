-- 核心表结构参考（PostgreSQL 语法，运行时不执行；建表由 SQLAlchemy create_all 完成）

CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(160) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    display_name    VARCHAR(80)  NOT NULL,
    role            VARCHAR(20)  NOT NULL,
    org             VARCHAR(120),
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE members (
    id              SERIAL PRIMARY KEY,
    member_no       VARCHAR(24)  NOT NULL UNIQUE,
    name            VARCHAR(40)  NOT NULL,
    phone           VARCHAR(20)  NOT NULL,
    city            VARCHAR(24)  NOT NULL,
    tier            VARCHAR(12)  NOT NULL,
    joined_on       DATE         NOT NULL,
    last_order_at   TIMESTAMP,
    orders_window   INTEGER      NOT NULL DEFAULT 0,
    amount_window   DOUBLE PRECISION NOT NULL DEFAULT 0,
    purchase_rate   DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_ticket      DOUBLE PRECISION NOT NULL DEFAULT 0,
    r_days          INTEGER,
    r_score         INTEGER,
    f_score         INTEGER,
    m_score         INTEGER,
    composite_score DOUBLE PRECISION,
    segment_code    VARCHAR(20),
    scored_at       TIMESTAMP,
    created_at      TIMESTAMP    NOT NULL,
    updated_at      TIMESTAMP    NOT NULL
);
CREATE INDEX ix_members_segment_tier ON members (segment_code, tier);
CREATE INDEX ix_members_composite ON members (composite_score);

CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    order_no        VARCHAR(32)  NOT NULL UNIQUE,
    member_id       INTEGER      NOT NULL REFERENCES members(id) ON DELETE CASCADE,
    store_code      VARCHAR(16)  NOT NULL,
    channel         VARCHAR(16)  NOT NULL,
    amount          DOUBLE PRECISION NOT NULL DEFAULT 0,
    items           INTEGER      NOT NULL DEFAULT 1,
    coupon_used     BOOLEAN      NOT NULL DEFAULT FALSE,
    paid_at         TIMESTAMP    NOT NULL,
    created_at      TIMESTAMP    NOT NULL
);
CREATE INDEX ix_orders_member_paid ON orders (member_id, paid_at);

CREATE TABLE segments (
    id                  SERIAL PRIMARY KEY,
    code                VARCHAR(20) NOT NULL UNIQUE,
    name                VARCHAR(40) NOT NULL,
    rule_text           VARCHAR(120) NOT NULL,
    sort_order          INTEGER     NOT NULL DEFAULT 0,
    member_count        INTEGER     NOT NULL DEFAULT 0,
    share               DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_r_score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_f_score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_m_score         DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_r_days          DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_amount_window   DOUBLE PRECISION NOT NULL DEFAULT 0,
    purchase_rate       DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_ticket          DOUBLE PRECISION NOT NULL DEFAULT 0,
    lift                DOUBLE PRECISION NOT NULL DEFAULT 0,
    coupon_face         DOUBLE PRECISION NOT NULL DEFAULT 6,
    core_share          DOUBLE PRECISION NOT NULL DEFAULT 0.6,
    enabled             BOOLEAN     NOT NULL DEFAULT TRUE,
    as_of               TIMESTAMP,
    snapshot            JSON,
    seed_key            VARCHAR(120) UNIQUE,
    updated_at          TIMESTAMP   NOT NULL
);

CREATE TABLE campaigns (
    id                    SERIAL PRIMARY KEY,
    code                  VARCHAR(32) NOT NULL UNIQUE,
    name                  VARCHAR(80) NOT NULL,
    channel               VARCHAR(20) NOT NULL,
    budget                DOUBLE PRECISION NOT NULL DEFAULT 0,
    status                VARCHAR(16) NOT NULL DEFAULT 'draft',
    starts_on             DATE,
    ends_on               DATE,
    reach_cost            DOUBLE PRECISION NOT NULL DEFAULT 0.15,
    orders_per_converter  DOUBLE PRECISION NOT NULL DEFAULT 1.4,
    tail_factor           DOUBLE PRECISION NOT NULL DEFAULT 0.6,
    target_segments       JSON,
    note                  TEXT,
    operator_email        VARCHAR(160) NOT NULL,
    seed_key              VARCHAR(120) UNIQUE,
    created_at            TIMESTAMP NOT NULL,
    updated_at            TIMESTAMP NOT NULL
);

CREATE TABLE audiences (
    id              SERIAL PRIMARY KEY,
    audience_no     VARCHAR(32) NOT NULL UNIQUE,
    campaign_id     INTEGER     NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending',
    budget          DOUBLE PRECISION NOT NULL DEFAULT 0,
    member_count    INTEGER     NOT NULL DEFAULT 0,
    spend           DOUBLE PRECISION NOT NULL DEFAULT 0,
    inc_orders      INTEGER     NOT NULL DEFAULT 0,
    inc_gmv         DOUBLE PRECISION NOT NULL DEFAULT 0,
    roi             DOUBLE PRECISION NOT NULL DEFAULT 0,
    global_rate     DOUBLE PRECISION NOT NULL DEFAULT 0,
    allocation      JSON,
    note            TEXT,
    operator_email  VARCHAR(160) NOT NULL,
    confirmed_by    VARCHAR(160),
    confirmed_at    TIMESTAMP,
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
);

CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    actor_email     VARCHAR(160) NOT NULL,
    actor_role      VARCHAR(20)  NOT NULL,
    action          VARCHAR(64)  NOT NULL,
    entity          VARCHAR(40)  NOT NULL,
    entity_id       VARCHAR(64),
    detail          JSON,
    layer           VARCHAR(16)  NOT NULL DEFAULT 'domain',
    ip              VARCHAR(64),
    seed_key        VARCHAR(120) UNIQUE,
    created_at      TIMESTAMP    NOT NULL
);
