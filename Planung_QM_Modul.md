# Planung QM-Modul

## 1. Zielbild und fachlicher Rahmen

Das bestehende EPZ verwendet PostgreSQL. Das Qualitätsmanagement wird als neues, logisch eigenständiges Modul im Schema `qm` derselben Datenbank aufgebaut.

Das Modul ist allgemein für folgende Inhalte vorgesehen:

- Komplikationsbesprechungen,
- Auditfeststellungen und Auditmaßnahmen,
- organisatorische und prozessbezogene Themen,
- weitere qualitätsrelevante Sachverhalte.

Ein QM-Thema kann optional auf einen Fall im EPZ verweisen. Themen ohne EPZ-Fallbezug müssen vollständig unterstützt werden.

Die Umsetzung erfolgt in zwei Hauptphasen: Zunächst wird das Datenbankschema fachlich und technisch stabil aufgebaut. Das Frontend wird anschließend auf Grundlage dieses Schemas entwickelt.

## 2. Technische Ausgangslage

Aktuelles Zielsystem:

```text
PostgreSQL 10.10
Windows 64-Bit
Visual C++ Build 1800
```

Alle SQL-Migrationen, Funktionen, Trigger und Constraints müssen mit PostgreSQL 10.10 kompatibel sein und auf der tatsächlichen Windows-Installation getestet werden.

PostgreSQL 10 ist seit dem 10. November 2022 nicht mehr unterstützt. Die letzte Version dieser Hauptreihe war PostgreSQL 10.23. Eine Aktualisierung auf eine unterstützte PostgreSQL-Hauptversion soll deshalb als eigene technische Maßnahme eingeplant werden.

Bis zu einer Aktualisierung dürfen keine Funktionen vorausgesetzt werden, die erst nach PostgreSQL 10 eingeführt wurden. Dazu gehören insbesondere:

- gespeicherte generierte Spalten,
- `CREATE PROCEDURE`,
- Indizes mit `INCLUDE`,
- neuere Partitionierungs- und Verwaltungsfunktionen.

Benötigte Logik wird PostgreSQL-10-kompatibel mit Tabellen, Constraints, Funktionen, Triggern und gewöhnlichen Indizes umgesetzt.

In PostgreSQL 10 nutzbar sind unter anderem:

- `BYTEA`,
- `JSONB`,
- `timestamptz`,
- Identity-Spalten,
- Row-Level Security,
- `INSERT ... ON CONFLICT`,
- UUID und SHA-256 über die Erweiterung `pgcrypto`.

Die Verfügbarkeit von `pgcrypto` ist auf dem Zielserver zu prüfen. Bei vorhandener Erweiterung können insbesondere folgende Funktionen verwendet werden:

```sql
gen_random_uuid()
digest(dateiinhalt, 'sha256')
```

Die Prüfsumme kann als `BYTEA` gespeichert oder mit `encode(..., 'hex')` als Hexadezimaltext ausgegeben werden.

## 3. Architekturgrundsätze

- PostgreSQL bleibt das zentrale Datenbanksystem.
- Das QM-Modul befindet sich im eigenen Schema `qm`.
- Tabellen, Constraints, Indizes, Funktionen und Rollen werden möglichst innerhalb dieses Schemas gekapselt.
- Die Kopplung an das bestehende EPZ-Modell wird auf das notwendige Minimum begrenzt.
- Primärschlüssel sollen systemübergreifend stabile Identifikatoren verwenden, vorzugsweise UUIDs.
- Fachliche Änderungen, Abschlüsse und Wiederaufnahmen müssen nachvollziehbar bleiben.
- Physisches Löschen ist nur für klar definierte Ausnahmefälle vorgesehen.
- Das Design soll eine spätere Migration oder Auskopplung in eine eigenständige Datenbank ermöglichen.

## 4. Kernentitäten

### 4.1 `qm.thema`

Zentrale Entität für einen qualitätsrelevanten Sachverhalt.

Vorgesehene Inhalte:

- stabile ID,
- Titel und Beschreibung,
- Kategorie beziehungsweise Themenart,
- Priorität oder Risikoeinstufung,
- Bearbeitungsstatus,
- Erfassungs- und Abschlusszeitpunkt,
- verantwortliche Person oder Organisationseinheit,
- optionaler Bezug zu einem EPZ-Fall,
- Angaben zur Wiederaufnahme,
- gegebenenfalls Verweis auf ein vorausgegangenes Thema,
- Ersteller sowie Zeitstempel für Anlage und letzte Änderung,
- Versionsnummer für optimistische Sperrung.

Die technische Form des optionalen EPZ-Fallbezugs ist noch offen.

### 4.2 `qm.sitzung`

Bildet einen Besprechungstermin oder eine formale QM-Sitzung ab.

Vorgesehene Inhalte:

- stabile ID,
- Bezeichnung,
- Datum, Beginn und optional Ende,
- Sitzungsart,
- Ort oder Besprechungsform,
- Leitung und Protokollführung,
- Status, beispielsweise `geplant`, `durchgefuehrt`, `freigegeben` oder `abgesagt`,
- Ersteller sowie Zeitstempel.

Teilnehmende können über eine eigene relationale Tabelle mit Person, Rolle, Anwesenheit und gegebenenfalls Vertretung abgebildet werden.

### 4.3 `qm.besprechung`

`qm.besprechung` ist die Zuordnungstabelle zwischen `qm.thema` und `qm.sitzung`. Sie bildet eine m:n-Beziehung ab:

- Ein Thema kann in mehreren Sitzungen behandelt werden.
- Eine Sitzung kann mehrere Themen behandeln.

Zusätzliche Angaben an der Zuordnung:

- Tagesordnungspunkt und Reihenfolge,
- Besprechungsstatus,
- Ergebnis oder Beschluss,
- Zeitpunkt der Behandlung,
- Vertagung oder erneute Vorlage.

Standardmäßig soll für ein Thema innerhalb einer Sitzung nur eine aktive Zuordnung bestehen. Ob mehrere getrennte Behandlungspunkte desselben Themas innerhalb einer Sitzung zulässig sind, ist offen.

### 4.4 `qm.massnahme`

Eine Maßnahme gehört grundsätzlich zu einem Thema und kann zusätzlich auf die konkrete Besprechung verweisen, aus der sie hervorgegangen ist.

Vorgesehene Inhalte:

- stabile ID,
- Beschreibung und Ziel,
- zugehöriges Thema,
- optional zugehörige Besprechung,
- verantwortliche Person oder Organisationseinheit,
- Erstellungsdatum,
- Fälligkeit,
- Status,
- Abschlussdatum,
- Wirksamkeitsprüfung mit Ergebnis und Prüfdatum,
- Begründung bei Abbruch, Ablehnung, Terminverschiebung oder Wiederaufnahme,
- Ersteller sowie Zeitstempel,
- Versionsnummer für optimistische Sperrung.

#### Maßnahmenstatus

Als Ausgangspunkt ist folgendes Statusmodell vorgesehen:

1. `offen`
2. `in_bearbeitung`
3. `umgesetzt`
4. `wirksamkeit_zu_pruefen`
5. `wirksam`
6. `nicht_wirksam`
7. `abgebrochen`

Optional können `zurueckgestellt` und `abgelehnt` ergänzt werden.

Zulässige Statusübergänge werden kontrolliert und im Verlauf protokolliert. Das endgültige Statusmodell und die erlaubten Übergänge sind noch offen.

#### Wiederaufnahme

Abgeschlossene Themen und Maßnahmen dürfen fachlich wiederaufgenommen werden. Folgende Angaben sind zwingend zu protokollieren:

- Zeitpunkt,
- ausführende Person,
- Begründung,
- vorheriger Status,
- neuer Status.

Offen ist, ob derselbe Datensatz erneut geöffnet oder ein neuer, mit dem Ursprung verknüpfter Folgedatensatz angelegt wird.

Ein Folgedatensatz ist für revisionssichere Auswertungen tendenziell vorzuziehen, weil der ursprüngliche Abschluss unverändert erhalten bleibt.

### 4.5 `qm.dokument`

Dokumente werden direkt in PostgreSQL gespeichert. Der Binärinhalt liegt als `BYTEA` vor. Damit können insbesondere Word-Dateien, PDFs und weitere Dateiformate gemeinsam mit den fachlichen Daten gesichert und berechtigt werden.

Vorgesehene Metadaten:

- stabile ID,
- ursprünglicher Dateiname,
- MIME-Typ,
- Dateigröße,
- Binärinhalt als `BYTEA`,
- kryptografische Prüfsumme, vorzugsweise SHA-256,
- Dokumenttyp,
- fachlicher Status,
- Versionsnummer,
- Dokumentgruppe und/oder Vorgängerversion,
- Ersteller und Erstellungszeitpunkt,
- optional Freigebender und Freigabezeitpunkt.

#### Flexible relationale Zuordnung

Dokumente werden über explizite Zuordnungstabellen angebunden:

- `qm.thema_dokument`,
- `qm.sitzung_dokument`,
- `qm.besprechung_dokument`,
- `qm.massnahme_dokument`.

Diese Tabellen können zusätzliche Angaben wie Dokumentrolle, Sichtbarkeit und Sortierung enthalten. Ein Dokument darf mehreren fachlichen Objekten zugeordnet werden.

Eine polymorphe Zuordnung über `objekttyp` und `objekt_id` wird vermieden, weil damit keine vollständige referenzielle Integrität durch PostgreSQL gewährleistet werden kann.

#### Versionierung und Prüfsummen

- Jede neue inhaltliche Fassung wird als neuer Dokumentdatensatz gespeichert.
- Freigegebene Versionen werden nicht überschrieben.
- Die Versionskette wird über eine Dokumentgruppe und/oder eine Vorgängerversion abgebildet.
- Die SHA-256-Prüfsumme wird serverseitig oder in der kontrollierten Anwendungsschicht berechnet.
- Die Prüfsumme dient dem Integritätsnachweis.
- Ob identische Inhalte nur erkannt oder zusätzlich dedupliziert werden, ist offen.
- Die Behandlung reiner Metadatenänderungen im Versionsmodell ist offen.

Unter PostgreSQL 10 kann die Prüfsumme bei aktivierter Erweiterung `pgcrypto` beispielsweise mit `digest(inhalt, 'sha256')` berechnet werden. Eine generierte Spalte darf dafür nicht verwendet werden, weil diese Funktion in PostgreSQL 10 noch nicht zur Verfügung steht. Stattdessen kommen ein Trigger, eine Schreibfunktion oder die Anwendungsschicht infrage.

### 4.6 `qm.verlauf` / Auditlog

Ein zentraler, unveränderlicher Verlauf protokolliert mindestens:

- Anlage, Änderung, Abschluss und Wiederaufnahme eines Themas,
- Anlage und Statuswechsel einer Maßnahme,
- Änderungen von Verantwortlichkeit und Fälligkeit,
- Ergebnisse von Wirksamkeitsprüfungen,
- Zuordnung und Entfernung von Dokumenten,
- neue Dokumentversionen und Freigaben,
- relevante Änderungen an Sitzungen und Besprechungsergebnissen.

Ein Verlaufseintrag enthält:

- Ereignis-ID,
- Ereigniszeitpunkt,
- ausführende Benutzer- oder technische Identität,
- betroffene Entität und deren ID,
- Ereignisart,
- Begründung oder Kommentar,
- alte und neue fachlich relevante Werte, gegebenenfalls als `JSONB`,
- optional eine Korrelations- oder Transaktions-ID.

Das Auditlog wird über PostgreSQL-10-kompatible Funktionen und Trigger befüllt. Für normale Anwendungsrollen ist es nur lesbar. Umfang, Aufbewahrungsdauer und mögliche Pseudonymisierung sind noch festzulegen.

## 5. Beziehungen

- `thema` ↔ `sitzung`: m:n über `besprechung`.
- `thema` → `massnahme`: 1:n.
- `besprechung` → `massnahme`: optional 1:n.
- `thema` → EPZ-Fall: optional n:1 oder fachlich gleichwertige lose Referenz.
- `dokument` ↔ fachliche Entitäten: m:n über explizite Zuordnungstabellen.
- `dokument` → `dokument`: Versionsbeziehung beziehungsweise gemeinsame Dokumentgruppe.
- `thema` → `thema`: Selbstbezug für Wiederaufnahme oder Fortführung.
- gegebenenfalls `massnahme` → `massnahme`: Selbstbezug für eine fortgeführte Maßnahme.
- `verlauf` → fachliche Entitäten: protokollierende Zuordnung.

## 6. Datenintegrität

- Primär- und Fremdschlüssel, Eindeutigkeiten und Prüfbedingungen werden in PostgreSQL definiert.
- Pflichtfelder, Statuswerte und zulässige Datumsfolgen werden soweit möglich durch Constraints abgesichert.
- Dokumentgröße und Prüfsumme werden serverseitig oder in der kontrollierten Anwendungsschicht geprüft.
- Statusänderungen und wichtige Schreibvorgänge erfolgen über definierte Funktionen oder eine kontrollierte Anwendungsschicht.
- Eine Versionsnummer ermöglicht optimistische Sperrung bei paralleler Bearbeitung.
- Indizes sind mindestens für Fremdschlüssel, Status, Fälligkeiten, Sitzungsdatum, EPZ-Fallbezug und Dokumentprüfsummen vorzusehen.
- Es werden nur unter PostgreSQL 10 unterstützte gewöhnliche, partielle oder ausdrucksbasierte Indizes verwendet.
- Ereignisse und technische Zeitangaben verwenden `timestamptz`.
- Physisches Löschen freigegebener Dokumente oder auditierter Fachobjekte wird verhindert oder besonders beschränkt.

## 7. Rechte und Datenschutz

Das Modul kann medizinische und personenbezogene Daten enthalten. Es gilt das Prinzip der minimal erforderlichen Berechtigung.

Konzeptionell vorgesehene Rollen:

- reine Leseberechtigung,
- QM-Bearbeitung,
- Sitzungs- und Protokollverantwortung,
- Freigabe von Dokumenten und Abschlüssen,
- Administration ohne unnötigen Zugriff auf fachliche Inhalte,
- technische Anwendungsrolle.

Zu berücksichtigen sind:

- getrennte Rechte auf Schema-, Tabellen- und Funktionsebene,
- gegebenenfalls Row-Level Security,
- eingeschränkter Zugriff auf sensible Themen und Dokumente,
- erforderliche Protokollierung sicherheitsrelevanter Lese- und Schreibzugriffe,
- Datenminimierung beim EPZ-Fallbezug,
- definierte Aufbewahrungs-, Archivierungs- und Löschfristen,
- verschlüsselte Datenübertragung,
- verschlüsselte Datenträger und Sicherungen,
- Schutz vor direkter Umgehung der Audit- und Statuslogik,
- datenschutzgerechte Testdaten,
- geregelte Exporte und Akteneinsicht.

Offen sind das endgültige Rollenmodell, der konkrete Einsatz von Row-Level Security, der Umfang eines Lesezugriffsprotokolls sowie Aufbewahrungs- und Löschfristen.

## 8. Migration und spätere Auskopplung

Das Schema `qm` soll später in eine eigenständige Datenbank überführt werden können.

Dafür gelten folgende Leitlinien:

- keine unnötigen direkten Abhängigkeiten von EPZ-Tabellen,
- stabile, transportierbare Identifikatoren,
- dokumentierte Schnittstellen und Fremdreferenzen,
- gekapselte Datenbankobjekte im Schema `qm`,
- keine Geschäftslogik, die ausschließlich durch schemaübergreifende Trigger funktioniert,
- exportierbare Dokumentinhalte und Metadaten,
- reproduzierbare Migrationen,
- automatisierte Integritätsprüfungen.

Für den EPZ-Fallbezug stehen zwei Varianten zur Entscheidung:

1. Echter Fremdschlüssel auf den EPZ-Fall: hohe unmittelbare Integrität, aber engere Kopplung.
2. Externe Fall-ID ohne schemaübergreifenden Fremdschlüssel: leichtere Auskopplung, aber Integritätsprüfung über Anwendung oder Synchronisation.

Bei einer späteren Auskopplung ist außerdem zu entscheiden, ob Fallstammdaten ausschließlich referenziert, minimal gespiegelt oder über eine Schnittstelle abgerufen werden.

## 9. Gestufter Implementierungsplan

### Stufe 1 – Fachliche Festlegung

- Begriffe, Kategorien und Pflichtangaben präzisieren.
- Statusmodelle festlegen.
- Abschluss, Wiederaufnahme und Wirksamkeitsprüfung definieren.
- Rollen, Sichtbarkeit und Datenschutzanforderungen abstimmen.
- Form des EPZ-Fallbezugs auswählen.

**Ergebnis:** Abgestimmtes Fachmodell mit dokumentierten offenen Restpunkten.

### Stufe 2 – PostgreSQL-10-Kompatibilitätsprüfung

- Verfügbarkeit von `pgcrypto` prüfen.
- UUID- und Prüfsummenstrategie festlegen.
- Zeichensatz, Collation und Zeitzoneneinstellungen dokumentieren.
- PostgreSQL-10-kompatible Migrationskonventionen festlegen.
- Testumgebung passend zu PostgreSQL 10.10 unter Windows bereitstellen.
- Aktualisierungspfad auf eine unterstützte PostgreSQL-Version planen.

**Ergebnis:** Verbindliches technisches Kompatibilitätsprofil.

### Stufe 3 – Relationales Kernschema

- Schema `qm` und Basisrollen anlegen.
- `thema`, `sitzung`, `besprechung` und `massnahme` erstellen.
- Schlüssel, Constraints, Statuswerte und Indizes umsetzen.
- Wiederaufnahme und Verantwortlichkeiten abbilden.
- Datenbankmigrationen versioniert und wiederholbar bereitstellen.

**Ergebnis:** Ohne Frontend nutzbares, konsistentes Kernschema.

### Stufe 4 – Dokumentenverwaltung

- `dokument` mit `BYTEA`, Metadaten und Prüfsumme erstellen.
- Zuordnungstabellen anlegen.
- Versionierungs- und Freigaberegeln implementieren.
- Dateigrößen und erlaubte Dateitypen festlegen.
- Sicherung und Wiederherstellung mit realistischen Dokumentmengen testen.

**Ergebnis:** Versionierte, revisionsnahe Dokumentablage.

### Stufe 5 – Verlauf, Audit und Sicherheit

- unveränderliches Auditlog implementieren,
- Statusübergänge und Begründungspflichten absichern,
- Rollen und Berechtigungen umsetzen,
- Datenschutz-, Aufbewahrungs- und Löschkonzept anwenden,
- Schutz vor Umgehung testen.

**Ergebnis:** Nachvollziehbare und abgesicherte Bearbeitungsprozesse.

### Stufe 6 – Integration und Erprobung

- optionalen EPZ-Fallbezug integrieren,
- typische Abläufe und Beispieldaten testen,
- Parallelbearbeitung und Wiederaufnahme prüfen,
- Dokumentversionierung und Wiederherstellung testen,
- Auswertungs- und Exportanforderungen validieren,
- spätere Auskopplung probeweise durchspielen.

**Ergebnis:** Fachlich und technisch validiertes Datenbankmodul.

### Stufe 7 – Frontend

- Bedienabläufe auf Basis des stabilen Schemas entwerfen,
- Suche, Filter und Übersichten entwickeln,
- Sitzungs- und Protokollworkflow umsetzen,
- Maßnahmenverfolgung und Wiedervorlagen ergänzen,
- Dokumentanzeige, Upload und Versionierung integrieren,
- rollenabhängige Oberfläche und Auditansicht bereitstellen.

**Ergebnis:** Nutzbare QM-Anwendung auf dem validierten Datenmodell.

## 10. Offene Entscheidungen

- technische Form des EPZ-Fallbezugs,
- UUID-Variante und Verfahren zur ID-Erzeugung,
- Verfügbarkeit und Freigabe von `pgcrypto`,
- endgültige Kategorien, Prioritäten und Statuswerte,
- zulässige Statusübergänge,
- Wiederaufnahme durch erneutes Öffnen oder Folgedatensatz,
- Maßnahmenbezug nur zum Thema oder zusätzlich zur Besprechung,
- mehrere Behandlungspunkte desselben Themas innerhalb einer Sitzung,
- Modellierung von Personen, Organisationseinheiten und Teilnehmenden,
- Dokumentfreigabe- und Versionsmodell,
- Deduplizierung anhand der Prüfsumme,
- maximale Dateigröße und erlaubte Dateitypen,
- Volltextsuche in Metadaten oder Dokumentinhalten,
- Rollenmodell einschließlich Row-Level Security,
- Umfang des Lesezugriffsprotokolls,
- Aufbewahrungs-, Archivierungs- und Löschfristen,
- Exporte, Berichte und Schnittstellen,
- Zielversion und Zeitplan für die PostgreSQL-Aktualisierung,
- Strategie für die spätere Auskopplung.

## 11. Zusammenfassung

Das QM-Modul wird als fachlich eigenständiges Schema `qm` innerhalb der bestehenden EPZ-Datenbank aufgebaut. Sein Kern besteht aus Themen, Sitzungen, der m:n-Zuordnung Besprechung, Maßnahmen, versionierten Dokumenten mit `BYTEA`, relationalen Dokumentzuordnungen und einem unveränderlichen Verlauf.

Der EPZ-Fallbezug bleibt optional. Datenintegrität, Wiederaufnahme, Prüfsummen, Berechtigungen, Datenschutz und spätere Auskopplung werden bereits beim Datenbankentwurf berücksichtigt.

Die erste Umsetzung bleibt vollständig mit PostgreSQL 10.10 unter Windows 64-Bit kompatibel. Wegen des ausgelaufenen Supports wird parallel eine Aktualisierung auf eine unterstützte PostgreSQL-Hauptversion geplant. Das Frontend wird erst nach Aufbau und Validierung des Datenbankschemas entwickelt.

## 12. Technische Referenzen

- PostgreSQL 10 – `pgcrypto`: https://www.postgresql.org/docs/10/pgcrypto.html
- PostgreSQL-Versionierungsrichtlinie: https://www.postgresql.org/support/versioning/
- PostgreSQL 10 – `CREATE TABLE`: https://www.postgresql.org/docs/10/sql-createtable.html