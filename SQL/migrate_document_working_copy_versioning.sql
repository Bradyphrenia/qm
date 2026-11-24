-- Add database guarantees required by explicit working-copy versioning.
-- Run as qm_owner (or another sufficiently privileged administrator) in database qm.

BEGIN;

DO $$
BEGIN
    IF current_database() <> 'qm' THEN
        RAISE EXCEPTION 'Dieses Skript muss in der Datenbank qm ausgeführt werden.';
    END IF;
    IF EXISTS (
        SELECT 1
        FROM qm.dokument
        WHERE vorgaenger_dokument_id IS NOT NULL
        GROUP BY vorgaenger_dokument_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Migration abgebrochen: Mindestens eine Dokumentversion besitzt mehrere direkte Nachfolger.';
    END IF;
END;
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dokument_ein_nachfolger
    ON qm.dokument(vorgaenger_dokument_id)
    WHERE vorgaenger_dokument_id IS NOT NULL;

CREATE OR REPLACE FUNCTION qm.fn_prevent_released_document_deletion()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IN ('freigegeben', 'archiviert')
       OR OLD.freigegeben_von IS NOT NULL OR OLD.freigegeben_am IS NOT NULL THEN
        RAISE EXCEPTION 'Released or archived documents cannot be deleted.';
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION qm.fn_protect_document_version()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status = 'archiviert' THEN
        RAISE EXCEPTION 'Archived document versions cannot be modified.';
    END IF;
    IF NEW.inhalt IS DISTINCT FROM OLD.inhalt
       OR NEW.dateiname IS DISTINCT FROM OLD.dateiname
       OR NEW.mime_type IS DISTINCT FROM OLD.mime_type
       OR NEW.dokumenttyp IS DISTINCT FROM OLD.dokumenttyp
       OR NEW.dokument_gruppe_id IS DISTINCT FROM OLD.dokument_gruppe_id
       OR NEW.vorgaenger_dokument_id IS DISTINCT FROM OLD.vorgaenger_dokument_id
       OR NEW.erstellt_von IS DISTINCT FROM OLD.erstellt_von
       OR NEW.erstellt_am IS DISTINCT FROM OLD.erstellt_am THEN
        RAISE EXCEPTION 'Document content and version identity cannot be modified; create a successor version.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dokument_protect_version ON qm.dokument;
CREATE TRIGGER trg_dokument_protect_version
BEFORE UPDATE ON qm.dokument
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_protect_document_version();

ALTER FUNCTION qm.fn_prevent_released_document_deletion() OWNER TO qm_owner;
ALTER FUNCTION qm.fn_protect_document_version() OWNER TO qm_owner;
REVOKE ALL PRIVILEGES ON FUNCTION qm.fn_protect_document_version() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION qm.fn_protect_document_version() TO qm_app;

COMMIT;
