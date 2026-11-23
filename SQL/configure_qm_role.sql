-- =============================================================================
-- Least-privilege roles for the QM desktop application
-- Target database: qm
-- Target schema:   qm
--
-- Run this script while connected to database qm as postgres or another
-- sufficiently privileged administrator. Review the final verification output.
-- The script deliberately does not change PUBLIC privileges on other databases
-- or on schema public because that could affect unrelated applications.
-- =============================================================================

BEGIN;

DO $$
BEGIN
    IF current_database() <> 'qm' THEN
        RAISE EXCEPTION 'Dieses Skript muss in der Datenbank qm ausgeführt werden.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qm') THEN
        RAISE EXCEPTION 'Die Rolle qm existiert nicht.';
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

-- Remove the critical inheritance path to the postgres superuser.
REVOKE postgres FROM qm;

-- Keep qm as a login role without administrative cluster privileges.
ALTER ROLE qm
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    INHERIT
    LOGIN;

-- qm_app is a shared privilege bundle. It can never be used to log in.
ALTER ROLE qm_app
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS
    NOLOGIN;

GRANT qm_app TO qm;

-- Login roles connect through qm_app; they receive no direct database rights.
REVOKE ALL PRIVILEGES ON DATABASE qm FROM qm;
REVOKE ALL PRIVILEGES ON DATABASE qm FROM qm_app;
GRANT CONNECT ON DATABASE qm TO qm_app;

-- Unqualified application names resolve only inside qm and pg_catalog.
ALTER ROLE qm IN DATABASE qm SET search_path = qm, pg_catalog;

-- Keep ownership separate from the login role.
ALTER SCHEMA qm OWNER TO qm_owner;
ALTER TABLE qm.thema OWNER TO qm_owner;
ALTER TABLE qm.sitzung OWNER TO qm_owner;
ALTER TABLE qm.sitzung_teilnehmer OWNER TO qm_owner;
ALTER TABLE qm.besprechung OWNER TO qm_owner;
ALTER TABLE qm.massnahme OWNER TO qm_owner;
ALTER TABLE qm.dokument OWNER TO qm_owner;
ALTER TABLE qm.thema_dokument OWNER TO qm_owner;
ALTER TABLE qm.sitzung_dokument OWNER TO qm_owner;
ALTER TABLE qm.besprechung_dokument OWNER TO qm_owner;
ALTER TABLE qm.massnahme_dokument OWNER TO qm_owner;
ALTER TABLE qm.verlauf OWNER TO qm_owner;
ALTER SEQUENCE qm.verlauf_id_seq OWNER TO qm_owner;
ALTER FUNCTION qm.fn_set_timestamp_and_version() OWNER TO qm_owner;
ALTER FUNCTION qm.fn_dokument_metadata() OWNER TO qm_owner;
ALTER FUNCTION qm.fn_prevent_audit_modification() OWNER TO qm_owner;
ALTER FUNCTION qm.fn_prevent_released_document_deletion() OWNER TO qm_owner;

-- No role receives access to the QM schema through PUBLIC.
REVOKE ALL PRIVILEGES ON SCHEMA qm FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA qm FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA qm FROM PUBLIC;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA qm FROM PUBLIC;

-- Login roles have no direct object privileges. The shared qm_app role carries
-- exactly the privileges needed by the application.
REVOKE ALL PRIVILEGES ON SCHEMA qm FROM qm;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA qm FROM qm;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA qm FROM qm;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA qm FROM qm;
REVOKE ALL PRIVILEGES ON SCHEMA qm FROM qm_app;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA qm FROM qm_app;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA qm FROM qm_app;
REVOKE ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA qm FROM qm_app;

GRANT USAGE ON SCHEMA qm TO qm_app;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    qm.thema,
    qm.sitzung,
    qm.sitzung_teilnehmer,
    qm.besprechung,
    qm.massnahme,
    qm.dokument,
    qm.thema_dokument,
    qm.sitzung_dokument,
    qm.besprechung_dokument,
    qm.massnahme_dokument
TO qm_app;

-- The application may read the audit history but may not forge, update, or
-- delete audit rows directly.
GRANT SELECT ON TABLE qm.verlauf TO qm_app;

-- Includes pgcrypto functions installed in qm and the trigger functions used
-- by table defaults and triggers.
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA qm TO qm_app;

-- The audit trigger writes with its owner's rights. A fixed search_path blocks
-- object-shadowing attacks in SECURITY DEFINER execution.
ALTER FUNCTION qm.fn_audit_log_writer() OWNER TO qm_owner;
ALTER FUNCTION qm.fn_audit_log_writer() SECURITY DEFINER;
ALTER FUNCTION qm.fn_audit_log_writer() SET search_path = pg_catalog, qm;
REVOKE ALL PRIVILEGES ON FUNCTION qm.fn_audit_log_writer() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qm.fn_audit_log_writer() TO qm_app;

COMMIT;

-- =============================================================================
-- Verification. Expected highlights:
--   qm is a member of qm_app, but not of postgres
--   qm_app cannot log in and has no administrative privileges
--   qm_connect = true, database_create = false
--   qm_usage = true, qm_create = false
--   no INSERT/UPDATE/DELETE on qm.verlauf
-- =============================================================================

SELECT
    r.rolname,
    r.rolsuper,
    r.rolcreaterole,
    r.rolcreatedb,
    r.rolcanlogin,
    r.rolreplication,
    r.rolbypassrls,
    has_database_privilege('qm', 'qm', 'CONNECT') AS qm_connect,
    has_database_privilege('qm', 'qm', 'CREATE') AS database_create,
    has_schema_privilege('qm', 'qm', 'USAGE') AS qm_usage,
    has_schema_privilege('qm', 'qm', 'CREATE') AS qm_create,
    has_schema_privilege('qm', 'public', 'USAGE') AS public_usage,
    has_schema_privilege('qm', 'public', 'CREATE') AS public_create
FROM pg_roles AS r
WHERE r.rolname = 'qm';

SELECT parent.rolname AS member_of
FROM pg_auth_members AS membership
JOIN pg_roles AS child ON child.oid = membership.member
JOIN pg_roles AS parent ON parent.oid = membership.roleid
WHERE child.rolname = 'qm';

SELECT
    rolname,
    rolcanlogin,
    rolsuper,
    rolcreaterole,
    rolcreatedb,
    rolreplication,
    rolbypassrls
FROM pg_roles
WHERE rolname = 'qm_app';

SELECT
    table_name,
    has_table_privilege('qm', format('%I.%I', table_schema, table_name), 'SELECT') AS can_select,
    has_table_privilege('qm', format('%I.%I', table_schema, table_name), 'INSERT') AS can_insert,
    has_table_privilege('qm', format('%I.%I', table_schema, table_name), 'UPDATE') AS can_update,
    has_table_privilege('qm', format('%I.%I', table_schema, table_name), 'DELETE') AS can_delete
FROM information_schema.tables
WHERE table_schema = 'qm'
ORDER BY table_name;

-- PostgreSQL has no per-role DENY. If the following query returns databases
-- other than qm, that access is normally inherited from PUBLIC. Restricting it
-- requires a coordinated change to PUBLIC CONNECT grants or pg_hba.conf.
SELECT datname
FROM pg_database
WHERE datallowconn
  AND datname <> 'qm'
  AND has_database_privilege('qm', datname, 'CONNECT')
ORDER BY datname;

-- To add another login later, create it without administrative privileges,
-- grant qm_app to it, and set its database-local search_path. Set the password
-- interactively in Navicat so it is not stored in SQL history:
--
--   CREATE ROLE neuer_nutzer LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
--       NOREPLICATION NOBYPASSRLS INHERIT;
--   GRANT qm_app TO neuer_nutzer;
--   ALTER ROLE neuer_nutzer IN DATABASE qm SET search_path = qm, pg_catalog;

