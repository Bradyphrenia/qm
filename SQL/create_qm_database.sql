-- =============================================================================
-- Create the dedicated QM database, its non-login owner role and the shared
-- non-login application role used by all QM login users.
-- Run while connected to the postgres maintenance database as postgres.
-- CREATE DATABASE cannot run inside a transaction block.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qm_owner') THEN
        CREATE ROLE qm_owner
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qm_app') THEN
        CREATE ROLE qm_app
            NOLOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOREPLICATION
            NOBYPASSRLS;
    END IF;
END;
$$;

CREATE DATABASE qm
    WITH OWNER = qm_owner
    TEMPLATE = template0;

REVOKE ALL PRIVILEGES ON DATABASE qm FROM PUBLIC;
GRANT CONNECT ON DATABASE qm TO qm_app;

