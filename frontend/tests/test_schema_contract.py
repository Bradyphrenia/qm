from dataclasses import fields
from pathlib import Path
import re
from qm_app import models

SCHEMA = Path(__file__).resolve().parents[2] / 'SQL' / 'generate_schema.sql'


def test_status_values_match_schema():
    sql = SCHEMA.read_text()
    for name, constraint in [
        ('THEMA_STATUS', 'thema_status'), ('SITZUNG_STATUS', 'sitzung_status'),
        ('BESPRECHUNG_STATUS', 'besprechung_status'), ('MASSNAHME_STATUS', 'massnahme_status'),
        ('WIRKSAMKEIT_ERGEBNIS', 'massnahme_wirksamkeit'), ('DOKUMENT_STATUS', 'dokument_status'),
    ]:
        block = re.search(r'CONSTRAINT chk_' + constraint + r' CHECK \((.*?)\n    \)', sql, re.S)[1]
        assert getattr(models, name) == tuple(re.findall(r"'([^']+)'", block))


def test_models_cover_schema_fields():
    sql = SCHEMA.read_text()
    for table, cls in [('thema', models.Thema), ('sitzung', models.Sitzung),
                       ('sitzung_teilnehmer', models.SitzungTeilnehmer),
                       ('besprechung', models.Besprechung), ('massnahme', models.Massnahme),
                       ('dokument', models.Dokument), ('verlauf', models.Verlauf)]:
        block = re.search(r'CREATE TABLE IF NOT EXISTS qm\.' + table + r' \((.*?)\n\);', sql, re.S)[1]
        expected = set(re.findall(r'^    (\w+) (?:UUID|VARCHAR|TEXT|TIMESTAMPTZ|DATE|TIME|INTEGER|BIGINT|BIGSERIAL|BYTEA|BOOLEAN|JSONB)\b', block, re.M))
        if table == 'dokument':
            expected.remove('inhalt')  # metadata lists must not load binary content
        assert {f.name for f in fields(cls)} == expected


def test_document_version_guards_exist():
    sql = SCHEMA.read_text()
    assert 'CREATE UNIQUE INDEX IF NOT EXISTS uq_dokument_ein_nachfolger' in sql
    assert 'CREATE OR REPLACE FUNCTION qm.fn_protect_document_version()' in sql
    assert 'CREATE TRIGGER trg_dokument_protect_version' in sql
