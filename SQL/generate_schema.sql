-- =============================================================================
-- Database Schema Definition for QM (Qualitaetsmanagement) Module
-- Target Database: PostgreSQL 10.10+ (Windows 64-Bit compatible)
-- Specification: Planung_QM_Modul.md
-- Note: Encapsulated strictly in schema "qm" without touching public/other schemas.
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS qm;

-- Enable pgcrypto extension inside schema qm if available/required for UUIDs and digest
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA qm;

-- Set search_path during execution (all objects are also explicitly schema-qualified)
SET search_path TO qm;

-- =============================================================================
-- Generic Trigger Functions
-- =============================================================================

-- Trigger function: Update timestamp and increment optimistic lock version
CREATE OR REPLACE FUNCTION qm.fn_set_timestamp_and_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.geaendert_am = CURRENT_TIMESTAMP;
    NEW.version = OLD.version + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger function: Calculate SHA-256 and size for binary document content
CREATE OR REPLACE FUNCTION qm.fn_dokument_metadata()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.inhalt IS NOT NULL THEN
        NEW.dateigroesse = octet_length(NEW.inhalt);
        NEW.pruefsumme_sha256 = qm.digest(NEW.inhalt, 'sha256');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger function: Prevent UPDATE or DELETE on immutable audit log
CREATE OR REPLACE FUNCTION qm.fn_prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log entries in qm.verlauf are immutable and cannot be modified or deleted.';
END;
$$ LANGUAGE plpgsql;

-- Trigger function: Prevent physical deletion of released or archived documents
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

-- Document bytes and version-chain identity are immutable after insertion.
-- Archived rows are completely immutable; a successor must be created instead.
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

-- =============================================================================
-- Core Entity Tables
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. qm.thema
-- Zentrale Entitaet fuer einen qualitaetsrelevanten Sachverhalt
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.thema (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    titel VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    kategorie VARCHAR(100) NOT NULL,
    prioritaet VARCHAR(50),
    status VARCHAR(50) NOT NULL DEFAULT 'offen',
    erfasst_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    abgeschlossen_am TIMESTAMPTZ,
    verantwortlich TEXT,
    epz_fall_id VARCHAR(100), -- Loose reference to external EPZ case (no cross-schema FK)
    vorgaenger_thema_id UUID REFERENCES qm.thema(id) ON DELETE RESTRICT,
    wiederaufnahme_am TIMESTAMPTZ,
    wiederaufnahme_durch VARCHAR(100),
    wiederaufnahme_grund TEXT,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    geaendert_von VARCHAR(100),
    geaendert_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT chk_thema_status CHECK (
        status IN ('offen', 'in_bearbeitung', 'geprueft', 'abgeschlossen', 'abgebrochen', 'wiederaufgenommen')
    ),
    CONSTRAINT chk_thema_abschluss_datum CHECK (
        (abgeschlossen_am IS NULL) OR (abgeschlossen_am >= erfasst_am)
    )
);

CREATE TRIGGER trg_thema_update
BEFORE UPDATE ON qm.thema
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_set_timestamp_and_version();

-- -----------------------------------------------------------------------------
-- 2. qm.sitzung
-- Bildet einen Besprechungstermin oder eine formale QM-Sitzung ab
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.sitzung (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    bezeichnung VARCHAR(255) NOT NULL,
    datum DATE NOT NULL,
    beginn TIME,
    ende TIME,
    sitzungsart VARCHAR(100),
    ort VARCHAR(255),
    leitung VARCHAR(100),
    protokollfuehrung VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'geplant',
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    geaendert_von VARCHAR(100),
    geaendert_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT chk_sitzung_status CHECK (
        status IN ('geplant', 'durchgefuehrt', 'freigegeben', 'abgesagt')
    ),
    CONSTRAINT chk_sitzung_zeiten CHECK (
        (ende IS NULL) OR (beginn IS NULL) OR (ende >= beginn)
    )
);

CREATE TRIGGER trg_sitzung_update
BEFORE UPDATE ON qm.sitzung
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_set_timestamp_and_version();

-- -----------------------------------------------------------------------------
-- 3. qm.sitzung_teilnehmer
-- Teilnehmende einer Sitzung mit Rolle und Anwesenheit
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.sitzung_teilnehmer (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    sitzung_id UUID NOT NULL REFERENCES qm.sitzung(id) ON DELETE CASCADE,
    person VARCHAR(100) NOT NULL,
    rolle VARCHAR(100),
    anwesend BOOLEAN NOT NULL DEFAULT true,
    vertretung_durch VARCHAR(100),
    bemerkung TEXT,
    CONSTRAINT uq_sitzung_person UNIQUE (sitzung_id, person)
);

-- -----------------------------------------------------------------------------
-- 4. qm.besprechung
-- Zuordnungstabelle zwischen qm.thema und qm.sitzung (m:n)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.besprechung (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    sitzung_id UUID NOT NULL REFERENCES qm.sitzung(id) ON DELETE CASCADE,
    thema_id UUID NOT NULL REFERENCES qm.thema(id) ON DELETE RESTRICT,
    top_nr VARCHAR(50),
    reihenfolge INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'vorgemerkt',
    ergebnis TEXT,
    beschluss TEXT,
    behandelt_am TIMESTAMPTZ,
    vertagung_nach_sitzung_id UUID REFERENCES qm.sitzung(id) ON DELETE SET NULL,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    geaendert_von VARCHAR(100),
    geaendert_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT uq_sitzung_thema UNIQUE (sitzung_id, thema_id),
    CONSTRAINT chk_besprechung_status CHECK (
        status IN ('vorgemerkt', 'in_beratung', 'beschlossen', 'vertagt', 'abgesetzt')
    )
);

CREATE TRIGGER trg_besprechung_update
BEFORE UPDATE ON qm.besprechung
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_set_timestamp_and_version();

-- -----------------------------------------------------------------------------
-- 5. qm.massnahme
-- Massnahmen zu einem QM-Thema und optional zu einer Besprechung
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.massnahme (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    thema_id UUID NOT NULL REFERENCES qm.thema(id) ON DELETE RESTRICT,
    besprechung_id UUID REFERENCES qm.besprechung(id) ON DELETE SET NULL,
    vorgaenger_massnahme_id UUID REFERENCES qm.massnahme(id) ON DELETE RESTRICT,
    titel VARCHAR(255) NOT NULL,
    beschreibung TEXT,
    ziel TEXT,
    verantwortlich VARCHAR(100) NOT NULL,
    faellig_am DATE,
    status VARCHAR(50) NOT NULL DEFAULT 'offen',
    abgeschlossen_am DATE,
    wirksamkeitspruefung_ergebnis VARCHAR(50),
    wirksamkeitspruefung_am DATE,
    wirksamkeitspruefung_durch VARCHAR(100),
    begruendung TEXT,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    geaendert_von VARCHAR(100),
    geaendert_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    version INTEGER NOT NULL DEFAULT 1,
    CONSTRAINT chk_massnahme_status CHECK (
        status IN (
            'offen',
            'in_bearbeitung',
            'umgesetzt',
            'wirksamkeit_zu_pruefen',
            'wirksam',
            'nicht_wirksam',
            'abgebrochen',
            'zurueckgestellt',
            'abgelehnt'
        )
    ),
    CONSTRAINT chk_massnahme_wirksamkeit CHECK (
        wirksamkeitspruefung_ergebnis IS NULL OR
        wirksamkeitspruefung_ergebnis IN ('wirksam', 'teilweise_wirksam', 'nicht_wirksam', 'nicht_pruefbar')
    )
);

CREATE TRIGGER trg_massnahme_update
BEFORE UPDATE ON qm.massnahme
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_set_timestamp_and_version();

-- -----------------------------------------------------------------------------
-- 6. qm.dokument
-- Zentrale Dokumentenablage mit Versionierung und SHA-256 Pruefsumme
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.dokument (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    dateiname VARCHAR(255) NOT NULL,
    mime_type VARCHAR(150) NOT NULL,
    dateigroesse BIGINT NOT NULL DEFAULT 0,
    inhalt BYTEA NOT NULL,
    pruefsumme_sha256 BYTEA,
    dokumenttyp VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'entwurf',
    version INTEGER NOT NULL DEFAULT 1,
    dokument_gruppe_id UUID,
    vorgaenger_dokument_id UUID REFERENCES qm.dokument(id) ON DELETE RESTRICT,
    freigegeben_von VARCHAR(100),
    freigegeben_am TIMESTAMPTZ,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_dokument_status CHECK (
        status IN ('entwurf', 'in_pruefung', 'freigegeben', 'obsolet', 'archiviert')
    ),
    CONSTRAINT chk_dokument_freigabe CHECK (
        (status <> 'freigegeben') OR (freigegeben_von IS NOT NULL AND freigegeben_am IS NOT NULL)
    )
);

CREATE TRIGGER trg_dokument_meta
BEFORE INSERT OR UPDATE ON qm.dokument
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_dokument_metadata();

CREATE TRIGGER trg_dokument_protect_version
BEFORE UPDATE ON qm.dokument
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_protect_document_version();

CREATE TRIGGER trg_dokument_prevent_del
BEFORE DELETE ON qm.dokument
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_prevent_released_document_deletion();

-- -----------------------------------------------------------------------------
-- 7. Dokument-Zuordnungstabellen (explizite Relationen statt polymorpher Zuordnung)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.thema_dokument (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    thema_id UUID NOT NULL REFERENCES qm.thema(id) ON DELETE CASCADE,
    dokument_id UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE,
    dokument_rolle VARCHAR(100),
    sichtbarkeit VARCHAR(50) DEFAULT 'intern',
    sortierung INTEGER DEFAULT 0,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_thema_dokument UNIQUE (thema_id, dokument_id)
);

CREATE TABLE IF NOT EXISTS qm.sitzung_dokument (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    sitzung_id UUID NOT NULL REFERENCES qm.sitzung(id) ON DELETE CASCADE,
    dokument_id UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE,
    dokument_rolle VARCHAR(100),
    sichtbarkeit VARCHAR(50) DEFAULT 'intern',
    sortierung INTEGER DEFAULT 0,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_sitzung_dokument UNIQUE (sitzung_id, dokument_id)
);

CREATE TABLE IF NOT EXISTS qm.besprechung_dokument (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    besprechung_id UUID NOT NULL REFERENCES qm.besprechung(id) ON DELETE CASCADE,
    dokument_id UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE,
    dokument_rolle VARCHAR(100),
    sichtbarkeit VARCHAR(50) DEFAULT 'intern',
    sortierung INTEGER DEFAULT 0,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_besprechung_dokument UNIQUE (besprechung_id, dokument_id)
);

CREATE TABLE IF NOT EXISTS qm.massnahme_dokument (
    id UUID PRIMARY KEY DEFAULT qm.gen_random_uuid(),
    massnahme_id UUID NOT NULL REFERENCES qm.massnahme(id) ON DELETE CASCADE,
    dokument_id UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE,
    dokument_rolle VARCHAR(100),
    sichtbarkeit VARCHAR(50) DEFAULT 'intern',
    sortierung INTEGER DEFAULT 0,
    erstellt_von VARCHAR(100) NOT NULL,
    erstellt_am TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_massnahme_dokument UNIQUE (massnahme_id, dokument_id)
);

-- -----------------------------------------------------------------------------
-- 8. qm.verlauf (Unveraenderliches Auditlog)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS qm.verlauf (
    id BIGSERIAL PRIMARY KEY,
    zeitpunkt TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    benutzer VARCHAR(100) NOT NULL,
    entitaet VARCHAR(100) NOT NULL,
    entitaet_id VARCHAR(100) NOT NULL,
    ereignis_art VARCHAR(100) NOT NULL,
    begruendung TEXT,
    alte_werte JSONB,
    neue_werte JSONB,
    transaktion_id BIGINT DEFAULT txid_current()
);

CREATE TRIGGER trg_verlauf_immutable
BEFORE UPDATE OR DELETE ON qm.verlauf
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_prevent_audit_modification();

-- -----------------------------------------------------------------------------
-- Generic Audit Trigger Function for Core Entities
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION qm.fn_audit_log_writer()
RETURNS TRIGGER AS $$
DECLARE
    v_user VARCHAR(100);
    v_entity_id VARCHAR(100);
    v_old_data JSONB := NULL;
    v_new_data JSONB := NULL;
    v_event VARCHAR(50);
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_event := 'INSERT';
        v_entity_id := NEW.id::TEXT;
        v_user := COALESCE(NEW.erstellt_von, current_user);
        v_new_data := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_event := 'UPDATE';
        v_entity_id := NEW.id::TEXT;
        v_user := COALESCE(NEW.geaendert_von, current_user);
        v_old_data := to_jsonb(OLD);
        v_new_data := to_jsonb(NEW);
    ELSIF TG_OP = 'DELETE' THEN
        v_event := 'DELETE';
        v_entity_id := OLD.id::TEXT;
        -- SECURITY DEFINER changes current_user to the function owner. Keep the
        -- authenticated application role in the audit record instead.
        v_user := session_user;
        v_old_data := to_jsonb(OLD);
    END IF;

    INSERT INTO qm.verlauf (
        zeitpunkt,
        benutzer,
        entitaet,
        entitaet_id,
        ereignis_art,
        begruendung,
        alte_werte,
        neue_werte,
        transaktion_id
    ) VALUES (
        CURRENT_TIMESTAMP,
        v_user,
        TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
        v_entity_id,
        v_event,
        NULL,
        v_old_data,
        v_new_data,
        txid_current()
    );

    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, qm;

-- Attach audit triggers to core tables
CREATE TRIGGER trg_thema_audit
AFTER INSERT OR UPDATE OR DELETE ON qm.thema
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_audit_log_writer();

CREATE TRIGGER trg_sitzung_audit
AFTER INSERT OR UPDATE OR DELETE ON qm.sitzung
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_audit_log_writer();

CREATE TRIGGER trg_besprechung_audit
AFTER INSERT OR UPDATE OR DELETE ON qm.besprechung
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_audit_log_writer();

CREATE TRIGGER trg_massnahme_audit
AFTER INSERT OR UPDATE OR DELETE ON qm.massnahme
FOR EACH ROW
EXECUTE PROCEDURE qm.fn_audit_log_writer();

-- =============================================================================
-- Indizes (PostgreSQL 10.10 compatible, standard B-tree / expression indices)
-- =============================================================================

-- qm.thema
CREATE INDEX IF NOT EXISTS idx_thema_status ON qm.thema(status);
CREATE INDEX IF NOT EXISTS idx_thema_kategorie ON qm.thema(kategorie);
CREATE INDEX IF NOT EXISTS idx_thema_epz_fall ON qm.thema(epz_fall_id) WHERE epz_fall_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_thema_erfasst_am ON qm.thema(erfasst_am);
CREATE INDEX IF NOT EXISTS idx_thema_vorgaenger ON qm.thema(vorgaenger_thema_id) WHERE vorgaenger_thema_id IS NOT NULL;

-- qm.sitzung
CREATE INDEX IF NOT EXISTS idx_sitzung_datum ON qm.sitzung(datum);
CREATE INDEX IF NOT EXISTS idx_sitzung_status ON qm.sitzung(status);

-- qm.sitzung_teilnehmer
CREATE INDEX IF NOT EXISTS idx_sitzung_teilnehmer_sitzung ON qm.sitzung_teilnehmer(sitzung_id);
CREATE INDEX IF NOT EXISTS idx_sitzung_teilnehmer_person ON qm.sitzung_teilnehmer(person);

-- qm.besprechung
CREATE INDEX IF NOT EXISTS idx_besprechung_sitzung ON qm.besprechung(sitzung_id);
CREATE INDEX IF NOT EXISTS idx_besprechung_thema ON qm.besprechung(thema_id);
CREATE INDEX IF NOT EXISTS idx_besprechung_status ON qm.besprechung(status);

-- qm.massnahme
CREATE INDEX IF NOT EXISTS idx_massnahme_thema ON qm.massnahme(thema_id);
CREATE INDEX IF NOT EXISTS idx_massnahme_besprechung ON qm.massnahme(besprechung_id) WHERE besprechung_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_massnahme_status ON qm.massnahme(status);
CREATE INDEX IF NOT EXISTS idx_massnahme_faellig_am ON qm.massnahme(faellig_am);
CREATE INDEX IF NOT EXISTS idx_massnahme_verantwortlich ON qm.massnahme(verantwortlich);
CREATE INDEX IF NOT EXISTS idx_massnahme_vorgaenger ON qm.massnahme(vorgaenger_massnahme_id) WHERE vorgaenger_massnahme_id IS NOT NULL;

-- qm.dokument
CREATE INDEX IF NOT EXISTS idx_dokument_status ON qm.dokument(status);
CREATE INDEX IF NOT EXISTS idx_dokument_gruppe ON qm.dokument(dokument_gruppe_id) WHERE dokument_gruppe_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dokument_vorgaenger ON qm.dokument(vorgaenger_dokument_id) WHERE vorgaenger_dokument_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_dokument_ein_nachfolger ON qm.dokument(vorgaenger_dokument_id) WHERE vorgaenger_dokument_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dokument_pruefsumme ON qm.dokument(pruefsumme_sha256);

-- Dokument-Zuordnungen
CREATE INDEX IF NOT EXISTS idx_thema_dok_thema ON qm.thema_dokument(thema_id);
CREATE INDEX IF NOT EXISTS idx_thema_dok_dok ON qm.thema_dokument(dokument_id);
CREATE INDEX IF NOT EXISTS idx_sitzung_dok_sitzung ON qm.sitzung_dokument(sitzung_id);
CREATE INDEX IF NOT EXISTS idx_sitzung_dok_dok ON qm.sitzung_dokument(dokument_id);
CREATE INDEX IF NOT EXISTS idx_besprechung_dok_bespr ON qm.besprechung_dokument(besprechung_id);
CREATE INDEX IF NOT EXISTS idx_besprechung_dok_dok ON qm.besprechung_dokument(dokument_id);
CREATE INDEX IF NOT EXISTS idx_massnahme_dok_massn ON qm.massnahme_dokument(massnahme_id);
CREATE INDEX IF NOT EXISTS idx_massnahme_dok_dok ON qm.massnahme_dokument(dokument_id);

-- qm.verlauf
CREATE INDEX IF NOT EXISTS idx_verlauf_entitaet ON qm.verlauf(entitaet, entitaet_id);
CREATE INDEX IF NOT EXISTS idx_verlauf_zeitpunkt ON qm.verlauf(zeitpunkt);
CREATE INDEX IF NOT EXISTS idx_verlauf_benutzer ON qm.verlauf(benutzer);
CREATE INDEX IF NOT EXISTS idx_verlauf_transaktion ON qm.verlauf(transaktion_id);

-- =============================================================================
-- Comments / Metadata Documentation
-- =============================================================================
COMMENT ON SCHEMA qm IS 'Qualitaetsmanagement (QM) Modul';
COMMENT ON TABLE qm.thema IS 'Zentrale Entitaet fuer qualitaetsrelevante Themen/Sachverhalte';
COMMENT ON TABLE qm.sitzung IS 'QM-Besprechungs- und Sitzungstermine';
COMMENT ON TABLE qm.sitzung_teilnehmer IS 'Teilnehmende und Anwesenheitsliste einer Sitzung';
COMMENT ON TABLE qm.besprechung IS 'm:n-Zuordnung zwischen Themen und Sitzungen';
COMMENT ON TABLE qm.massnahme IS 'Massnahmen zur Bearbeitung und Verbesserung von QM-Themen';
COMMENT ON TABLE qm.dokument IS 'Zentrale, versionierte binaere Dokumentenablage mit SHA-256 Pruefsumme';
COMMENT ON TABLE qm.thema_dokument IS 'Zuordnung von Dokumenten zu Themen';
COMMENT ON TABLE qm.sitzung_dokument IS 'Zuordnung von Dokumenten zu Sitzungen';
COMMENT ON TABLE qm.besprechung_dokument IS 'Zuordnung von Dokumenten zu Besprechungen';
COMMENT ON TABLE qm.massnahme_dokument IS 'Zuordnung von Dokumenten zu Massnahmen';
COMMENT ON TABLE qm.verlauf IS 'Revisionssicheres, unveraenderliches Auditlog fuer QM-Vorgaenge';
