# Projektdokumentation: PostgreSQL-Datenbank und Schema `qm`

Diese Dokumentation beschreibt die eigenständige PostgreSQL-Datenbank `qm` und
das darin gekapselte Schema `qm` für das Qualitätsmanagement-Modul. Grundlage
sind `Planung_QM_Modul.md`, `SQL/generate_schema.sql`,
`SQL/create_qm_database.sql` und `SQL/configure_qm_role.sql`.

---

## 1. Gesamtarchitektur und Design-Prinzipien

- **Schema-Kapselung**: Alle Tabellen, Funktionen, Trigger, Indizes und Erweiterungen (`pgcrypto`) sind vollständig im Schema `qm` gekapselt. Es existieren keine harten Abhängigkeiten oder Fremdschlüssel zum Schema `public` oder anderen Schemata.
- **Eigene Datenbank**: Das QM-Modul läuft in der eigenständigen Datenbank `qm`.
  Das frühere Schema `epz.qm` bleibt vorerst nur als Rückfallmöglichkeit bestehen.
- **Getrennte Rollen**: `qm_owner` besitzt die Datenbankobjekte, `qm_app` bündelt
  die Anwendungsrechte ohne eigene Anmeldung und der Login `qm` erbt diese Rechte
  als Mitglied von `qm_app`.
- **Kompatibilität**: Vollständig kompatibel mit PostgreSQL 10.10+ (Windows 64-Bit).
- **Primärschlüssel**: Durchgängig UUIDs (erzeugt via `qm.gen_random_uuid()`), ausgenommen das Auditlog `qm.verlauf` (`BIGSERIAL`).
- **Auditierung & Revisionssicherheit**: Zentrale, unveränderliche Audit-Tabelle `qm.verlauf` mit JSONB-Snapshot-Erfassung bei `INSERT`, `UPDATE` und `DELETE`.
- **Optimistische Sperrung**: Spalte `version INTEGER` in allen operativen Haupttabellen mit automatischer Inkrementierung per Trigger.
- **Dokumentenverwaltung**: Binäre Speicherung via `BYTEA`, serverseitige Integritätsprüfung (SHA-256) und explizite m:n-Relationstabellen.

---

## 2. Übersicht des Beziehungsgefüges (Entity-Relationship)

```text
                  +--------------------------------+
                  |            qm.sitzung          |
                  +---------------+----------------+
                                  | 1
                  +---------------+----------------+
                  |                                | n
                  v n                              v
     +-----------------------+           +-----------------------+
     |     qm.besprechung    |           | qm.sitzung_teilnehmer |
     +-----------+-----------+           +-----------------------+
               n | (m:n)
                 v 1
+----------------+---------------+       +------------------------------------+
|            qm.thema            |<------+ vorgaenger_thema_id (Selbstbezug)  |
+----------------+---------------+       +------------------------------------+
  | 1            | 1 (epz_fall_id: lose Kopplung)
  |              +-----------------------------------+
  v n                                                |
+----------------+---------------+                   |
|          qm.massnahme          |                   |
+----------------+---------------+                   |
  |              | vorgaenger_massnahme_id (Selbstbezug)
  | 0..1         +-----------------------------------+
  v (aus Besprechung entstanden)
qm.besprechung

Dokument-Zuordnungen (m:n über Zwischentabellen auf qm.dokument):
- qm.thema_dokument       : qm.thema       <-> qm.dokument
- qm.sitzung_dokument     : qm.sitzung     <-> qm.dokument
- qm.besprechung_dokument : qm.besprechung <-> qm.dokument
- qm.massnahme_dokument   : qm.massnahme   <-> qm.dokument

Auditierung:
- Alle Änderungen an thema, sitzung, besprechung, massnahme -> qm.verlauf
```

---

## 3. Tabellenspezifikationen im Detail

---

### 3.1 Tabelle `qm.thema`
Zentrale Entität zur Erfassung qualitätsrelevanter Sachverhalte (Komplikationen, Audits, CIRS-Fälle, Prozessabweichungen).

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `titel` | `VARCHAR(255)` | `NOT NULL` | - | Kurztitel / Bezeichnung des Sachverhalts |
| `beschreibung` | `TEXT` | `NULL` | - | Ausführliche Problem- bzw. Sachverhaltsbeschreibung |
| `kategorie` | `VARCHAR(100)` | `NOT NULL` | - | Fachliche Einordnung (z. B. `Komplikation`, `Audit`, `Hygiene`, `Prozess`) |
| `prioritaet` | `VARCHAR(50)` | `NULL` | - | Dringlichkeits- oder Risikostufe (z. B. `niedrig`, `mittel`, `hoch`, `kritisch`) |
| `status` | `VARCHAR(50)` | `NOT NULL` | `'offen'` | Bearbeitungsstatus (`offen`, `in_bearbeitung`, `geprueft`, `abgeschlossen`, `abgebrochen`, `wiederaufgenommen`) |
| `erfasst_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Initialer Erfassungszeitpunkt |
| `abgeschlossen_am` | `TIMESTAMPTZ` | `NULL` | - | Zeitpunkt des formalen Abschlusses |
| `verantwortlich` | `TEXT` | `NULL` | - | Zuständige Person oder Organisationseinheit |
| `epz_fall_id` | `VARCHAR(100)` | `NULL` | - | Externe Fall-ID zur optionalen Verknüpfung mit dem EPZ-Modell (lose Referenz ohne DB-Fremdschlüssel) |
| `vorgaenger_thema_id` | `UUID` | `NULL` | - | **FK** auf `qm.thema(id)`: Verweis auf das Vorgängerthema bei Wiederaufnahme oder Fortführung |
| `wiederaufnahme_am` | `TIMESTAMPTZ` | `NULL` | - | Zeitstempel, an dem das Thema erneut geöffnet wurde |
| `wiederaufnahme_durch`| `VARCHAR(100)` | `NULL` | - | Benutzerkennung der wiederaufnehmenden Person |
| `wiederaufnahme_grund`| `TEXT` | `NULL` | - | Fachliche Begründung für die Wiederaufnahme |
| `erstellt_von` | `VARCHAR(100)` | `NOT NULL` | - | Benutzername des Erstellers |
| `erstellt_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Technischer Erstellungszeitstempel |
| `geaendert_von` | `VARCHAR(100)` | `NULL` | - | Benutzername des letzten Bearbeiters |
| `geaendert_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Zeitstempel der letzten Änderung |
| `version` | `INTEGER` | `NOT NULL` | `1` | Revisionszähler für optimistische Sperre (wird via Trigger hochgezählt) |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `FOREIGN KEY (vorgaenger_thema_id) REFERENCES qm.thema(id) ON DELETE RESTRICT`
- `CHECK chk_thema_status`: Erlaubte Werte: `'offen'`, `'in_bearbeitung'`, `'geprueft'`, `'abgeschlossen'`, `'abgebrochen'`, `'wiederaufgenommen'`
- `CHECK chk_thema_abschluss_datum`: `(abgeschlossen_am IS NULL) OR (abgeschlossen_am >= erfasst_am)`

---

### 3.2 Tabelle `qm.sitzung`
Bildet formale QM-Gremien, Besprechungstermine, Qualitätszirkel oder Auditmeetings ab.

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `bezeichnung` | `VARCHAR(255)` | `NOT NULL` | - | Name/Bezeichnung der Sitzung (z. B. *QM-Kommission Q3/2026*) |
| `datum` | `DATE` | `NOT NULL` | - | Sitzungsdatum |
| `beginn` | `TIME` | `NULL` | - | Geplante/tatsächliche Startzeit |
| `ende` | `TIME` | `NULL` | - | Geplante/tatsächliche Endzeit |
| `sitzungsart` | `VARCHAR(100)` | `NULL` | - | Sitzungstyp (z. B. `Komplikationsbesprechung`, `QM-Fix`, `Audit`) |
| `ort` | `VARCHAR(255)` | `NULL` | - | Raum, Standort oder Konferenzlink |
| `leitung` | `VARCHAR(100)` | `NULL` | - | Sitzungsleiter / Moderator |
| `protokollfuehrung` | `VARCHAR(100)` | `NULL` | - | Protokollant |
| `status` | `VARCHAR(50)` | `NOT NULL` | `'geplant'` | Status (`geplant`, `durchgefuehrt`, `freigegeben`, `abgesagt`) |
| `erstellt_von` | `VARCHAR(100)` | `NOT NULL` | - | Ersteller des Eintrags |
| `erstellt_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Erstellungszeitstempel |
| `geaendert_von` | `VARCHAR(100)` | `NULL` | - | Letzter Bearbeiter |
| `geaendert_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Änderungszeitstempel |
| `version` | `INTEGER` | `NOT NULL` | `1` | Optimistische Sperre |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `CHECK chk_sitzung_status`: Erlaubte Werte: `'geplant'`, `'durchgefuehrt'`, `'freigegeben'`, `'abgesagt'`
- `CHECK chk_sitzung_zeiten`: `(ende IS NULL) OR (beginn IS NULL) OR (ende >= beginn)`

---

### 3.3 Tabelle `qm.sitzung_teilnehmer`
Dokumentiert die geladenen und anwesenden Personen einer Sitzung.

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `sitzung_id` | `UUID` | `NOT NULL` | - | **FK** auf `qm.sitzung(id)` |
| `person` | `VARCHAR(100)` | `NOT NULL` | - | Name oder Personalidentifikator |
| `rolle` | `VARCHAR(100)` | `NULL` | - | Funktion/Rolle (z. B. `Chefarzt`, `Pflegedienstleitung`, `QM-Beauftragter`) |
| `anwesend` | `BOOLEAN` | `NOT NULL` | `true` | Anwesenheitsstatus (`true` = anwesend, `false` = abwesend/entschuldigt) |
| `vertretung_durch` | `VARCHAR(100)` | `NULL` | - | Name der vertretenden Person |
| `bemerkung` | `TEXT` | `NULL` | - | Ergänzende Anmerkungen |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `FOREIGN KEY (sitzung_id) REFERENCES qm.sitzung(id) ON DELETE CASCADE`
- `UNIQUE (sitzung_id, person)`

---

### 3.4 Tabelle `qm.besprechung`
Bildet die m:n-Verknüpfung zwischen `qm.sitzung` und `qm.thema` ab (Behandlung eines Themas in einer Sitzung als Tagesordnungspunkt).

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `sitzung_id` | `UUID` | `NOT NULL` | - | **FK** auf `qm.sitzung(id)` |
| `thema_id` | `UUID` | `NOT NULL` | - | **FK** auf `qm.thema(id)` |
| `top_nr` | `VARCHAR(50)` | `NULL` | - | Nummer des Tagesordnungspunkts (z. B. *TOP 3.1*) |
| `reihenfolge` | `INTEGER` | `NULL` | - | Numerische Sortierreihenfolge in der Agenda |
| `status` | `VARCHAR(50)` | `NOT NULL` | `'vorgemerkt'` | Behandlungsstatus (`vorgemerkt`, `in_beratung`, `beschlossen`, `vertagt`, `abgesetzt`) |
| `ergebnis` | `TEXT` | `NULL` | - | Diskussionsinhalt und Zusammenfassung |
| `beschluss` | `TEXT` | `NULL` | - | Formaler Beschluss des Gremiums |
| `behandelt_am` | `TIMESTAMPTZ` | `NULL` | - | Genauer Zeitpunkt der Behandlung während der Sitzung |
| `vertagung_nach_sitzung_id` | `UUID` | `NULL` | - | **FK** auf `qm.sitzung(id)`: Folgesitzung bei Vertagung |
| `erstellt_von` | `VARCHAR(100)` | `NOT NULL` | - | Ersteller |
| `erstellt_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Erstellungszeitstempel |
| `geaendert_von` | `VARCHAR(100)` | `NULL` | - | Letzter Bearbeiter |
| `geaendert_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Änderungszeitstempel |
| `version` | `INTEGER` | `NOT NULL` | `1` | Optimistische Sperre |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `FOREIGN KEY (sitzung_id) REFERENCES qm.sitzung(id) ON DELETE CASCADE`
- `FOREIGN KEY (thema_id) REFERENCES qm.thema(id) ON DELETE RESTRICT`
- `FOREIGN KEY (vertagung_nach_sitzung_id) REFERENCES qm.sitzung(id) ON DELETE SET NULL`
- `UNIQUE (sitzung_id, thema_id)`
- `CHECK chk_besprechung_status`: Erlaubte Werte: `'vorgemerkt'`, `'in_beratung'`, `'beschlossen'`, `'vertagt'`, `'abgesetzt'`

---

### 3.5 Tabelle `qm.massnahme`
Konkrete Verbesserungs-, Korrektur- oder Vorbeugemaßnahme (CAPA), zugeordnet zu einem QM-Thema und optional direkt aus einer Besprechung entstanden.

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `thema_id` | `UUID` | `NOT NULL` | - | **FK** auf `qm.thema(id)` |
| `besprechung_id` | `UUID` | `NULL` | - | **FK** auf `qm.besprechung(id)` (optionaler Nachweis des Ursprungsbeschlusses) |
| `vorgaenger_massnahme_id`| `UUID` | `NULL` | - | **FK** auf `qm.massnahme(id)` (Selbstbezug bei fortgeführten/wiederaufgenommenen Maßnahmen) |
| `titel` | `VARCHAR(255)` | `NOT NULL` | - | Titel der Maßnahme |
| `beschreibung` | `TEXT` | `NULL` | - | Beschreibung der durchzuführenden Aktion |
| `ziel` | `TEXT` | `NULL` | - | Angestrebtes Ziel / Soll-Zustand |
| `verantwortlich` | `VARCHAR(100)` | `NOT NULL` | - | Zuständige Person / Stelle |
| `faellig_am` | `DATE` | `NULL` | - | Fälligkeitsdatum / Frist |
| `status` | `VARCHAR(50)` | `NOT NULL` | `'offen'` | Maßnahmenstatus |
| `abgeschlossen_am` | `DATE` | `NULL` | - | Datum der praktischen Umsetzung/Fertigstellung |
| `wirksamkeitspruefung_ergebnis` | `VARCHAR(50)` | `NULL` | - | Bewertung der Wirksamkeit |
| `wirksamkeitspruefung_am` | `DATE` | `NULL` | - | Datum der Wirksamkeitsprüfung |
| `wirksamkeitspruefung_durch` | `VARCHAR(100)` | `NULL` | - | Prüfende Person |
| `begruendung` | `TEXT` | `NULL` | - | Begründung bei Terminverschiebung, Abbruch, Ablehnung oder Wiederaufnahme |
| `erstellt_von` | `VARCHAR(100)` | `NOT NULL` | - | Ersteller |
| `erstellt_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Erstellungszeitstempel |
| `geaendert_von` | `VARCHAR(100)` | `NULL` | - | Letzter Bearbeiter |
| `geaendert_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Änderungszeitstempel |
| `version` | `INTEGER` | `NOT NULL` | `1` | Optimistische Sperre |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `FOREIGN KEY (thema_id) REFERENCES qm.thema(id) ON DELETE RESTRICT`
- `FOREIGN KEY (besprechung_id) REFERENCES qm.besprechung(id) ON DELETE SET NULL`
- `FOREIGN KEY (vorgaenger_massnahme_id) REFERENCES qm.massnahme(id) ON DELETE RESTRICT`
- `CHECK chk_massnahme_status`: Erlaubte Werte: `'offen'`, `'in_bearbeitung'`, `'umgesetzt'`, `'wirksamkeit_zu_pruefen'`, `'wirksam'`, `'nicht_wirksam'`, `'abgebrochen'`, `'zurueckgestellt'`, `'abgelehnt'`
- `CHECK chk_massnahme_wirksamkeit`: Erlaubte Werte: `NULL`, `'wirksam'`, `'teilweise_wirksam'`, `'nicht_wirksam'`, `'nicht_pruefbar'`

---

### 3.6 Tabelle `qm.dokument`
Zentrale relationale Ablage für Binärdateien (z. B. PDF, Word-Dateien, Protokollanhänge, Gutachten) mit SHA-256-Integritätsprüfung und Versionierung.

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `UUID` | `NOT NULL` | `qm.gen_random_uuid()` | Eindeutiger Primärschlüssel |
| `dateiname` | `VARCHAR(255)` | `NOT NULL` | - | Ursprünglicher Dateiname (z. B. *Auditbericht_2026.pdf*) |
| `mime_type` | `VARCHAR(150)` | `NOT NULL` | - | MIME-Typ (z. B. `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`) |
| `dateigroesse` | `BIGINT` | `NOT NULL` | `0` | Dateigröße in Bytes (automatisch via Trigger berechnet) |
| `inhalt` | `BYTEA` | `NOT NULL` | - | Binärer Dateiinhalt |
| `pruefsumme_sha256` | `BYTEA` | `NULL` | - | Kryptografische Prüfsumme (automatisch via Trigger berechnet via `qm.digest(inhalt, 'sha256')`) |
| `dokumenttyp` | `VARCHAR(100)` | `NULL` | - | Typisierung (z. B. `Protokollanhang`, `Gutachten`, `Verfahrensanweisung`, `Nachweis`) |
| `status` | `VARCHAR(50)` | `NOT NULL` | `'entwurf'` | Dokumentstatus (`entwurf`, `in_pruefung`, `freigegeben`, `obsolet`, `archiviert`) |
| `version` | `INTEGER` | `NOT NULL` | `1` | Dokumentversionsnummer |
| `dokument_gruppe_id` | `UUID` | `NULL` | - | Gemeinsame Gruppen-UUID zur Verknüpfung ganzer Versionsketten |
| `vorgaenger_dokument_id`| `UUID` | `NULL` | - | **FK** auf `qm.dokument(id)`: Direkte Vorgängerversion |
| `freigegeben_von` | `VARCHAR(100)` | `NULL` | - | Freigebende Person |
| `freigegeben_am` | `TIMESTAMPTZ` | `NULL` | - | Zeitpunkt der Freigabe |
| `erstellt_von` | `VARCHAR(100)` | `NOT NULL` | - | Ersteller |
| `erstellt_am` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Erstellungszeitstempel |

**Constraints & Fremdschlüssel:**
- `PRIMARY KEY (id)`
- `FOREIGN KEY (vorgaenger_dokument_id) REFERENCES qm.dokument(id) ON DELETE RESTRICT`
- `CHECK chk_dokument_status`: Erlaubte Werte: `'entwurf'`, `'in_pruefung'`, `'freigegeben'`, `'obsolet'`, `'archiviert'`
- `CHECK chk_dokument_freigabe`: Stellt sicher: Wenn `status = 'freigegeben'`, dann müssen `freigegeben_von` und `freigegeben_am` zwingend befüllt sein.
- **Trigger-Schutz**: `trg_dokument_prevent_del` verhindert das physische Löschen freigegebener, ehemals freigegebener und archivierter Dokumente. `trg_dokument_protect_version` schützt Inhalt und Identität vorhandener beziehungsweise archivierter Versionen vor direkter Änderung.

---

### 3.7 Dokument-Zuordnungstabellen (Relationale Verknüpfungen)
Um referenzielle Integrität sicherzustellen, werden Dokumente nicht über lose polymorphe IDs (`objekttyp`, `objekt_id`), sondern über explizite m:n-Zuordnungstabellen verknüpft:

#### A. `qm.thema_dokument`
Verknüpft Dokumente mit einem Thema.
- `id` (`UUID PK DEFAULT qm.gen_random_uuid()`)
- `thema_id` (`UUID NOT NULL REFERENCES qm.thema(id) ON DELETE CASCADE`)
- `dokument_id` (`UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE`)
- `dokument_rolle` (`VARCHAR(100)`): z. B. `Sachverhaltsnachweis`, `Stellungnahme`
- `sichtbarkeit` (`VARCHAR(50) DEFAULT 'intern'`)
- `sortierung` (`INTEGER DEFAULT 0`)
- `erstellt_von` (`VARCHAR(100) NOT NULL`), `erstellt_am` (`TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`)
- `UNIQUE (thema_id, dokument_id)`

#### B. `qm.sitzung_dokument`
Verknüpft Dokumente mit einer Sitzung (z. B. Gesamtsitzungsprotokoll, Präsentationen).
- `id` (`UUID PK DEFAULT qm.gen_random_uuid()`)
- `sitzung_id` (`UUID NOT NULL REFERENCES qm.sitzung(id) ON DELETE CASCADE`)
- `dokument_id` (`UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE`)
- `dokument_rolle` (`VARCHAR(100)`): z. B. `Sitzungsprotokoll`, `Agenda`
- `sichtbarkeit` (`VARCHAR(50) DEFAULT 'intern'`), `sortierung` (`INTEGER DEFAULT 0`)
- `erstellt_von` (`VARCHAR(100) NOT NULL`), `erstellt_am` (`TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`)
- `UNIQUE (sitzung_id, dokument_id)`

#### C. `qm.besprechung_dokument`
Verknüpft Dokumente mit einem konkreten Besprechungspunkt / TOP.
- `id` (`UUID PK DEFAULT qm.gen_random_uuid()`)
- `besprechung_id` (`UUID NOT NULL REFERENCES qm.besprechung(id) ON DELETE CASCADE`)
- `dokument_id` (`UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE`)
- `dokument_rolle` (`VARCHAR(100)`): z. B. `Beschlussvorlage`, `TOP-Anlage`
- `sichtbarkeit` (`VARCHAR(50) DEFAULT 'intern'`), `sortierung` (`INTEGER DEFAULT 0`)
- `erstellt_von` (`VARCHAR(100) NOT NULL`), `erstellt_am` (`TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`)
- `UNIQUE (besprechung_id, dokument_id)`

#### D. `qm.massnahme_dokument`
Verknüpft Dokumente mit einer Maßnahme (z. B. Umsetzungsnachweis, Prüfbericht).
- `id` (`UUID PK DEFAULT qm.gen_random_uuid()`)
- `massnahme_id` (`UUID NOT NULL REFERENCES qm.massnahme(id) ON DELETE CASCADE`)
- `dokument_id` (`UUID NOT NULL REFERENCES qm.dokument(id) ON DELETE CASCADE`)
- `dokument_rolle` (`VARCHAR(100)`): z. B. `Wirksamkeitsnachweis`, `Umsetzungsbeleg`
- `sichtbarkeit` (`VARCHAR(50) DEFAULT 'intern'`), `sortierung` (`INTEGER DEFAULT 0`)
- `erstellt_von` (`VARCHAR(100) NOT NULL`), `erstellt_am` (`TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP`)
- `UNIQUE (massnahme_id, dokument_id)`

---

### 3.8 Tabelle `qm.verlauf` (Revisionssicheres Auditlog)
Zentrales, unveränderliches Auditlog zur Protokollierung aller Änderungen und Statuswechsel im System.

| Feldname | Datentyp | Nullable | Default | Beschreibung |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `BIGSERIAL` | `NOT NULL` | *auto-increment* | Fortlaufende Ereignis-ID (Primärschlüssel) |
| `zeitpunkt` | `TIMESTAMPTZ` | `NOT NULL` | `CURRENT_TIMESTAMP` | Exakter Ausführungszeitpunkt |
| `benutzer` | `VARCHAR(100)` | `NOT NULL` | - | Ausführender Benutzer (aus Datensatz oder `current_user`) |
| `entitaet` | `VARCHAR(100)` | `NOT NULL` | - | Vollqualifizierter Tabellenname (z. B. `qm.thema`, `qm.massnahme`) |
| `entitaet_id` | `VARCHAR(100)` | `NOT NULL` | - | Primärschlüssel (UUID) des betroffenen Datensatzes als String |
| `ereignis_art` | `VARCHAR(100)` | `NOT NULL` | - | Operation (`INSERT`, `UPDATE`, `DELETE`) |
| `begruendung` | `TEXT` | `NULL` | - | Optionale fachliche Begründung (z. B. bei Statuswechsel) |
| `alte_werte` | `JSONB` | `NULL` | - | Vollständiger Zustand des Datensatzes vor der Änderung (`OLD` als JSON) |
| `neue_werte` | `JSONB` | `NULL` | - | Vollständiger Zustand des Datensatzes nach der Änderung (`NEW` als JSON) |
| `transaktion_id` | `BIGINT` | `NULL` | `txid_current()` | PostgreSQL Transaktions-ID zur Korrelation zusammengehöriger Operationen |

**Constraints & Schutzfunktionen:**
- `PRIMARY KEY (id)`
- **Trigger `trg_verlauf_immutable`**: Löst bei jedem Versuch eines `UPDATE` oder `DELETE` eine Exception aus (`Audit log entries in qm.verlauf are immutable`).

---

## 4. Trigger und Trigger-Funktionen

1. **`qm.fn_set_timestamp_and_version()`**:
   - *Verwendung*: `BEFORE UPDATE` auf `qm.thema`, `qm.sitzung`, `qm.besprechung`, `qm.massnahme`.
   - *Funktion*: Aktualisiert automatisch `geaendert_am = CURRENT_TIMESTAMP` und inkrementiert `version = OLD.version + 1`.

2. **`qm.fn_dokument_metadata()`**:
   - *Verwendung*: `BEFORE INSERT OR UPDATE` auf `qm.dokument`.
   - *Funktion*: Berechnet serverseitig `dateigroesse = octet_length(NEW.inhalt)` und `pruefsumme_sha256 = qm.digest(NEW.inhalt, 'sha256')`.

3. **`qm.fn_protect_document_version()`**:
   - *Verwendung*: `BEFORE UPDATE` auf `qm.dokument`.
   - *Funktion*: Verhindert Änderungen an Inhalt und Versionsidentität vorhandener Dokumentzeilen. Archivierte Versionen sind vollständig unveränderlich; geänderte Inhalte werden als Nachfolger gespeichert.

4. **`qm.fn_prevent_released_document_deletion()`**:
   - *Verwendung*: `BEFORE DELETE` auf `qm.dokument`.
   - *Funktion*: Verhindert das physische Löschen freigegebener, ehemals freigegebener und archivierter Dokumente.

5. **`qm.fn_prevent_audit_modification()`**:
   - *Verwendung*: `BEFORE UPDATE OR DELETE` auf `qm.verlauf`.
   - *Funktion*: Blockiert jegliche Manipulation oder Löschung von Auditlog-Einträgen.

6. **`qm.fn_audit_log_writer()`**:
   - *Verwendung*: `AFTER INSERT OR UPDATE OR DELETE` auf `qm.thema`, `qm.sitzung`, `qm.besprechung`, `qm.massnahme`.
   - *Funktion*: Serialisiert `OLD` und `NEW` Datensätze via `to_jsonb()` und fügt einen unveränderlichen Verlaufseintrag in `qm.verlauf` ein.

---

## 5. Indexierungsstrategie

Alle Indizes sind als Standard-B-Tree bzw. partielle Indizes umgesetzt, um optimale Performance und PostgreSQL-10-Kompatibilität zu garantieren:

- **Fremdschlüssel-Indizes**: Zur Beschleunigung von Joins und Kaskaden (`idx_besprechung_sitzung`, `idx_besprechung_thema`, `idx_massnahme_thema`, `idx_massnahme_besprechung`, `idx_sitzung_teilnehmer_sitzung`, alle Dokument-Zuordnungstabellen).
- **Status & Termine**: `idx_thema_status`, `idx_sitzung_datum`, `idx_sitzung_status`, `idx_massnahme_status`, `idx_massnahme_faellig_am`, `idx_massnahme_verantwortlich`, `idx_dokument_status`.
- **Partielle Indizes**:
  - `idx_thema_epz_fall ON qm.thema(epz_fall_id) WHERE epz_fall_id IS NOT NULL`
  - `idx_thema_vorgaenger ON qm.thema(vorgaenger_thema_id) WHERE vorgaenger_thema_id IS NOT NULL`
  - `idx_massnahme_vorgaenger ON qm.massnahme(vorgaenger_massnahme_id) WHERE vorgaenger_massnahme_id IS NOT NULL`
  - `idx_dokument_gruppe ON qm.dokument(dokument_gruppe_id) WHERE dokument_gruppe_id IS NOT NULL`
  - `idx_dokument_vorgaenger ON qm.dokument(vorgaenger_dokument_id) WHERE vorgaenger_dokument_id IS NOT NULL`
  - `uq_dokument_ein_nachfolger UNIQUE ON qm.dokument(vorgaenger_dokument_id) WHERE vorgaenger_dokument_id IS NOT NULL` verhindert verzweigte Versionsketten.
- **Integrität & Audit**: `idx_dokument_pruefsumme`, `idx_verlauf_entitaet (entitaet, entitaet_id)`, `idx_verlauf_zeitpunkt`, `idx_verlauf_benutzer`, `idx_verlauf_transaktion`.

---

## 6. Migrations- und Auskopplungsfähigkeit

- **Entkopplung**: Die externe Fallreferenz `epz_fall_id` in `qm.thema` ist absichtlich als `VARCHAR(100)` ohne Fremdschlüsselbindung implementiert.
- **Umgesetzte Auskopplung**: Das Schema wurde in die eigene Datenbank `qm`
  überführt. Allfällige Fallprüfungen können über API-/Service-Schichten oder
  lose Synchronisation realisiert werden.
- **Reproduzierbarkeit**: `SQL/create_qm_database.sql` erstellt Datenbank und
  Basisrollen, `SQL/generate_schema.sql` die Objekte und
  `SQL/configure_qm_role.sql` die minimalen Anwendungsrechte.

---

## 7. Rollen- und Berechtigungskonzept

- `qm_owner`: Rolle ohne Anmeldung; Eigentümer von Schema, Tabellen, Sequenz
  und anwendungseigenen Funktionen.
- `qm_app`: Rolle ohne Anmeldung und ohne administrative Rechte; besitzt nur
  Verbindungs-, Schema-, Tabellen- und Funktionsrechte für den App-Betrieb.
- `qm`: Anmelderolle ohne administrative Rechte; Mitglied von `qm_app` und ohne
  direkte Tabellenrechte.
- Die zehn operativen Tabellen dürfen über `qm_app` gelesen und geändert werden.
  `qm.verlauf` ist für Anwendungsnutzer ausschließlich lesbar.
- Die Auditfunktion läuft mit den Rechten von `qm_owner`, festem Suchpfad und
  protokolliert über `session_user` den tatsächlich angemeldeten Benutzer.
- Weitere Benutzer erhalten dieselben Rechte durch Mitgliedschaft in `qm_app`;
  ihr datenbankspezifischer Suchpfad muss auf `qm, pg_catalog` gesetzt werden.
- Andere Datenbanken gewähren Verbindungen teilweise allgemein über `PUBLIC`.
  Eine vollständige Verbindungsisolation würde koordinierte `PUBLIC`-Änderungen
  oder eine gezielte Regel in `pg_hba.conf` erfordern.
