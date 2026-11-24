# Implementierungsplan: Bearbeitete Dokumente als neue Version übernehmen

> **Umsetzungsstand 24.11.2026:** Die Kernfunktion ist implementiert. Dazu gehören
> verwaltete und gesperrte Arbeitskopien, SHA-256-Änderungserkennung, ausdrückliche
> Übernahme in der Oberfläche, atomare Archivierung und Nachfolgeranlage,
> Konfliktprüfung, Datenbankmigration, Schutztrigger und automatisierte Tests.
> Die manuelle Prüfung mit realen Office-/PDF-Programmen auf den Zielsystemen
> bleibt Bestandteil der Abnahme.

## 1. Ziel

Dokumente, die aus der QM-Anwendung heraus geöffnet und in einem externen Programm bearbeitet werden, sollen ausdrücklich wieder in die Datenbank übernommen werden können.

Dabei gelten folgende fachliche Regeln:

- Der bestehende Datenbankinhalt wird nicht überschrieben.
- Eine geänderte Arbeitskopie wird als neuer Dokumentdatensatz gespeichert.
- Die bisherige Version erhält atomar den Status `archiviert`.
- Die neue Version wird als `entwurf` angelegt.
- Dokumentgruppe, Vorgängerbeziehung, Dokumenttyp und Zuordnungen bleiben erhalten.
- Unveränderte Arbeitskopien erzeugen keine neue Version.
- Parallele Änderungen oder bereits angelegte Nachfolger werden als Konflikt behandelt.
- Bei Fehlern bleiben Vorgänger und Datenbank unverändert; die lokale Arbeitskopie bleibt erhalten.

## 2. Ermittelte Ausgangslage

### 2.1 Öffnen von Dokumenten

`frontend/qm_app/ui/dokument_widget.py`, Funktion `DokumentWidget.open_document()`:

1. `DokumentRepository.download()` lädt Dateiname und Inhalt.
2. Die Anwendung erzeugt ein `QTemporaryDir`.
3. `write_download()` schreibt die Datei atomar über `QSaveFile`.
4. `QDesktopServices.openUrl()` öffnet die Datei im zugeordneten externen Programm.
5. Das temporäre Verzeichnis wird in `QApplication.qm_open_document_dirs` gehalten und dadurch nicht bereits beim Schließen des Dialogs gelöscht.

Die temporäre Datei wird momentan weder beobachtet noch erneut eingelesen. Änderungen im externen Programm gelangen daher nicht zurück in die Datenbank.

### 2.2 Speichern und Integritätsprüfung

`frontend/qm_app/repositories/dokument_repo.py`:

- `upload()` speichert ein neues Dokument und seine erste Zuordnung in einer Transaktion.
- `download()` liest Inhalt, Dateigröße und SHA-256-Prüfsumme und prüft die geladenen Bytes vor der Rückgabe.
- `new_version()` legt bereits einen neuen Dokumentdatensatz mit `dokument_gruppe_id` und `vorgaenger_dokument_id` an.
- Der vorhandene Dokumentinhalt wird nicht direkt überschrieben.

### 2.3 Vorhandene Versionierung

`DokumentRepository.new_version()`:

- sperrt die Versionsgruppe mit `pg_advisory_xact_lock`;
- sperrt den ausgewählten Vorgänger mit `SELECT ... FOR UPDATE`;
- prüft dessen erwartete `version`;
- verhindert auf Anwendungsebene einen zweiten direkten Nachfolger;
- legt den Nachfolger als `entwurf` an;
- übernimmt Dokumenttyp, Dokumentgruppe und sämtliche Zuordnungen;
- lässt Inhalt und Status des Vorgängers derzeit unverändert.

Die Repository-Operation läuft bereits über `Database.transaction()` und kann deshalb zu einer atomaren Archivierungs- und Versionsoperation erweitert werden.

### 2.4 Vorhandene Archivierung

`archiviert` ist ein zulässiger Dokumentstatus. Er wird momentan nur über `DokumentRepository.set_status()` gesetzt. Eine automatische Archivierung beim Erzeugen eines Nachfolgers gibt es nicht.

Wichtige Eigenschaften des bestehenden Schemas:

- `qm.dokument` besitzt keinen allgemeinen Versions- oder Zeitstempel-Trigger.
- Das Repository erhöht `version` bei Statusänderungen ausdrücklich selbst.
- Dokumente und Dokumentzuordnungen werden nicht in `qm.verlauf` protokolliert.
- Der Löschtrigger schützt nur Dokumente, deren aktueller Status `freigegeben` ist.
- Ein Vorgänger mit Nachfolger ist zusätzlich durch `vorgaenger_dokument_id ... ON DELETE RESTRICT` geschützt.

### 2.5 Datenbankschema

`SQL/generate_schema.sql` definiert für `qm.dokument` insbesondere:

- `inhalt BYTEA`;
- serverseitig berechnete Dateigröße und SHA-256-Prüfsumme;
- die Statuswerte `entwurf`, `in_pruefung`, `freigegeben`, `obsolet` und `archiviert`;
- `version` als optimistischen Änderungsstand;
- `dokument_gruppe_id` für eine Versionsfamilie;
- `vorgaenger_dokument_id` als selbstreferenzierenden Fremdschlüssel;
- Freigabebenutzer und Freigabezeitpunkt;
- vier separate Zuordnungstabellen für Thema, Sitzung, Tagesordnungspunkt und Maßnahme.

Die Spalte `version` ist keine reine Inhaltsversionsnummer. Statusänderungen erhöhen sie ebenfalls. Die fachliche Inhaltskette ergibt sich aus Dokumentgruppe und Vorgänger-ID.

## 3. Geplante Umsetzung

### 3.1 Arbeitskopien verwalten

Neue Datei, beispielsweise:

`frontend/qm_app/document_working_copy.py`

Vorgesehene Bestandteile:

- `WorkingCopy` als Datenträger für:
  - Dokument-ID;
  - beim Öffnen geladene Datenbankversion;
  - Ausgangs-SHA-256;
  - Dateiname und MIME-Typ;
  - Dokumentgruppe;
  - temporären Pfad und temporäres Verzeichnis.
- `WorkingCopyManager` für Erstellung, Wiederverwendung und Bereinigung der Arbeitskopien.
- Pro Dokument nur eine aktive Arbeitskopie. Erneutes Öffnen öffnet dieselbe Kopie oder bietet ein bewusstes Verwerfen und erneutes Laden an.

Die Arbeitskopie muss über das Schließen des jeweiligen Dialogs hinaus bestehen bleiben. Sie darf erst nach erfolgreicher Übernahme, bewusstem Verwerfen oder beim geregelten Ende der Anwendung entfernt werden.

### 3.2 Konsistenten Ausgangsstand laden

In `DokumentRepository` wird eine Methode wie `checkout(id, expected_version)` ergänzt.

Sie lädt in einer Transaktion gemeinsam:

- Dokument-ID und `version`;
- Dateiname und MIME-Typ;
- Dokumentgruppe und Vorgänger-ID;
- Inhalt, Dateigröße und Prüfsumme.

Danach werden Größe und SHA-256 wie bisher kontrolliert. Das Ergebnis bildet den verbindlichen Ausgangsstand der Arbeitskopie. Eine bereits veraltete Auswahl aus der Dokumenttabelle löst einen `ConcurrencyError` aus.

`DokumentWidget.open_document()` verwendet anschließend diesen Snapshot statt einer getrennten Kombination aus Tabellenmetadaten und `download()`.

### 3.3 Explizite Übernahme in der Oberfläche

In `frontend/qm_app/ui/dokument_widget.py` wird ein neuer Button ergänzt:

**Bearbeitete Arbeitskopie übernehmen**

Verhalten:

- Der Button ist nur aktiv, wenn für das ausgewählte Dokument eine Arbeitskopie vorhanden ist.
- Es erfolgt kein automatischer Upload beim Speichern im Fremdprogramm.
- Beim Klick wird die Arbeitskopie unter Beachtung des Upload-Limits erneut eingelesen.
- Größe und Änderungsinformationen werden vor und nach dem Lesen geprüft, damit keine gerade laufende Speicherung übernommen wird.
- Eine gesperrte Datei führt zu einem verständlichen Hinweis, sie im Fremdprogramm zu speichern beziehungsweise zu schließen und die Übernahme erneut zu starten.
- SHA-256 der Arbeitskopie wird mit der Ausgangsprüfsumme verglichen.
- Bei identischem Inhalt erfolgt keine Datenbankänderung.
- Bei verändertem Inhalt bestätigt der Benutzer ausdrücklich, dass eine neue Entwurfsversion erzeugt und der Vorgänger archiviert wird.
- Nach Erfolg wird die Dokumentliste neu geladen und der neue Nachfolger ausgewählt.

Ein `QFileSystemWatcher` kann ergänzend einen Hinweis wie „Arbeitskopie geändert“ anzeigen. Er ist jedoch nicht die verbindliche Änderungserkennung, da externe Programme Dateien mehrfach, verzögert oder durch Ersetzen speichern können. Maßgeblich bleibt der SHA-256-Vergleich beim ausdrücklichen Übernehmen.

### 3.4 Atomare Archivierung und neue Version

`DokumentRepository.new_version()` wird zum gemeinsamen Speicherweg für:

- eine manuell über „Neue Version“ ausgewählte Datei;
- eine bearbeitete temporäre Arbeitskopie.

Vorgesehene Transaktionsfolge:

1. Dateiname, MIME-Typ, Dateigröße und Upload-Limit prüfen.
2. Versionsgruppe und Vorgänger über `_lock()` sperren.
3. Erwartete `version` kontrollieren.
4. Zusätzlich die beim Öffnen gemerkte Ausgangsprüfsumme kontrollieren. Dadurch werden auch direkte Inhaltsänderungen erkannt, bei denen ein externer SQL-Schreiber die Versionsnummer nicht erhöht hat.
5. Prüfen, dass der ausgewählte Vorgänger weiterhin das Ende der Versionskette ist.
6. Vorgänger auf `archiviert` setzen und seine `version` erhöhen.
7. Nachfolger mit neuer UUID, bearbeitetem Inhalt, Status `entwurf`, derselben Dokumentgruppe und `vorgaenger_dokument_id` anlegen.
8. Sämtliche bestehenden Dokumentzuordnungen kopieren.
9. Transaktion bestätigen.

Schlägt ein Schritt fehl, werden die Archivierung und das Anlegen des Nachfolgers gemeinsam zurückgerollt.

Ist der Vorgänger bereits archiviert und besitzt noch keinen Nachfolger, kann die neue Version ohne erneute Statusänderung angelegt werden. Dieser Sonderfall muss ausdrücklich getestet werden.

### 3.5 Bedeutung der Versionsnummer

Die bestehende Spalte `version` bleibt zunächst der optimistische Änderungsstand.

Bei einem bisher nicht archivierten Vorgänger geschieht daher:

1. Archivierung erhöht den Stand des Vorgängers um eins.
2. Der Nachfolger erhält den Stand des archivierten Vorgängers plus eins.

Dadurch können Nummern übersprungen werden. Die Reihenfolge der Inhalte wird weiterhin über `dokument_gruppe_id` und `vorgaenger_dokument_id` bestimmt.

Soll die Oberfläche unabhängig davon strikt „Dokumentversion 1, 2, 3“ darstellen, ist eine zusätzliche Spalte wie `inhaltsversion` erforderlich. Diese Schemaerweiterung ist für die eigentliche Übernahmefunktion nicht zwingend notwendig und sollte als getrennte fachliche Entscheidung behandelt werden.

## 4. Konfliktbehandlung

Folgende Fälle werden unterschieden:

### Status oder Metadaten wurden zwischenzeitlich geändert

Die erwartete `version` stimmt nicht mehr. Die Datenbankoperation wird mit `ConcurrencyError` abgebrochen. Die Arbeitskopie bleibt erhalten.

### Inhalt wurde ohne Versionserhöhung verändert

Die aktuelle Datenbankprüfsumme weicht von der beim Öffnen gespeicherten Ausgangsprüfsumme ab. Die Übernahme wird als Konflikt abgelehnt.

### Es existiert bereits ein Nachfolger

Der ausgewählte Vorgänger ist nicht mehr das Ende der Versionskette. Die Übernahme wird abgelehnt und die Oberfläche verweist auf den aktuellen Nachfolger.

### Zwei Benutzer übernehmen gleichzeitig

Die transaktionsgebundene Gruppensperre serialisiert beide Vorgänge. Nur der erste Vorgang kann erfolgreich sein. Der zweite erkennt anschließend die geänderte Version oder den bereits vorhandenen Nachfolger.

### Die lokale Datei ist gesperrt oder wird gerade gespeichert

Es erfolgt keine Datenbankoperation. Der Benutzer kann die Datei im externen Programm fertig speichern beziehungsweise schließen und es erneut versuchen.

### Ein Datenbankfehler tritt nach Beginn der Archivierung auf

`Database.transaction()` setzt die vollständige Operation zurück. Es darf weder einen archivierten Vorgänger ohne Nachfolger noch einen Nachfolger ohne ordnungsgemäß archivierten Vorgänger geben.

Die lokale Arbeitskopie bleibt bei allen Konflikten und Fehlern erhalten. Sie kann erneut übernommen oder über eine lokale Speicherfunktion gesichert werden.

## 5. Temporäre Dateien

Der bestehende Einsatz von `QTemporaryDir` bleibt grundsätzlich geeignet, wird aber zentral verwaltet.

Vorgesehene Regeln:

- eindeutiges QM-Präfix für temporäre Verzeichnisse;
- zufälliger Verzeichnisanteil, damit Dateinamen anderer Arbeitskopien nicht kollidieren;
- sichere Bereinigung beim geregelten Anwendungsende;
- kein Löschen, solange ein externes Programm die Datei noch geöffnet hält;
- fehlgeschlagene Bereinigung wird beim nächsten Start erneut versucht;
- verwaiste Verzeichnisse werden nur entfernt, wenn sie eindeutig von der QM-Anwendung stammen und keine aktive Sperrdatei besitzen;
- eine Arbeitskopie wird nach einem Konflikt oder fehlgeschlagenen Upload nicht gelöscht;
- nach erfolgreicher Übernahme kann sie nach Bestätigung geschlossen und entfernt werden.

Für die Erkennung aktiver beziehungsweise verwaister Arbeitskopien bietet sich `QLockFile` an. Eine rein altersbasierte Bereinigung könnte Arbeitskopien einer zweiten laufenden Anwendungsinstanz löschen und ist daher nicht ausreichend.

## 6. Datenbankschutz und Migration

### 6.1 Eindeutiger direkter Nachfolger

In `SQL/generate_schema.sql` wird ein eindeutiger Index auf `vorgaenger_dokument_id` ergänzt. Damit verhindert auch PostgreSQL zwei direkte Nachfolger, nicht nur der Anwendungscode.

Beispielhafte Zielregel:

`UNIQUE (vorgaenger_dokument_id)` für alle nicht leeren Vorgänger-IDs.

### 6.2 Schutz archivierter Versionen

Zusätzlich sollte der Datenbankschutz erweitert werden:

- archivierte Dokumente dürfen nicht physisch gelöscht werden;
- Inhalt, Dateiname, MIME-Typ, Dokumentgruppe und Vorgänger-ID einer archivierten Version dürfen nicht mehr verändert werden;
- die einmalige Statusänderung von einem aktiven Status nach `archiviert` bleibt zulässig;
- freigegebene Inhalte dürfen ebenfalls nicht direkt überschrieben werden, sondern nur über eine neue Version fortgeführt werden.

Die neue beziehungsweise erweiterte Triggerfunktion muss in `SQL/configure_qm_role.sql` dem Schema-Eigentümer zugewiesen und mit den vorhandenen Rollenregeln abgestimmt werden.

### 6.3 Migration bestehender Installationen

Eine Änderung ausschließlich in `generate_schema.sql` reicht nicht aus, weil `CREATE TABLE IF NOT EXISTS` vorhandene Tabellen nicht erweitert.

Daher ist ein separates, wiederholbar ausführbares Migrationsskript vorzusehen, beispielsweise:

`SQL/migrate_document_working_copy_versioning.sql`

Es soll:

1. vorhandene Mehrfachnachfolger vor Anlage des eindeutigen Index erkennen und melden;
2. den eindeutigen Index anlegen;
3. die Schutzfunktion und Trigger aktualisieren;
4. keine Dokumentinhalte verändern;
5. vollständig in einer Transaktion laufen.

## 7. Betroffene Dateien und Funktionen

### Bestehende Dateien

- `frontend/qm_app/ui/dokument_widget.py`
  - `DokumentWidget.__init__()`
  - `selection_changed()`
  - `open_document()`
  - `new_version()`
  - neue Funktion zur Übernahme der Arbeitskopie
  - gegebenenfalls neue Statusanzeige für geänderte Arbeitskopien
- `frontend/qm_app/repositories/dokument_repo.py`
  - `_lock()` beziehungsweise ergänzende Snapshot-Funktion
  - neue Methode `checkout()`
  - `new_version()`
  - gegebenenfalls `download()` zur gemeinsamen Nutzung der Integritätsprüfung
- `frontend/qm_app/ui/main_window.py` oder Anwendungsstart
  - Initialisierung und abschließende Bereinigung des Arbeitskopien-Managers
- `SQL/generate_schema.sql`
  - eindeutiger Nachfolgerindex
  - Schutz archivierter Dokumentversionen
- `SQL/configure_qm_role.sql`
  - Eigentümer- und Ausführungsrechte neuer Triggerfunktionen
- `frontend/tests/test_massnahme_dokument.py`
  - Repository-, UI-, Konflikt- und Temporärdateitests
- `frontend/tests/test_schema_contract.py`
  - Prüfung neuer Indizes und Schutztrigger
- `frontend/README.md`
  - Benutzer- und Entwicklerdokumentation
- `frontend/PRUEFUNG.md`
  - manueller End-to-End-Prüfablauf
- `TODO.md`
  - bisherige Grenze der nicht zurückgeladenen Arbeitskopien aktualisieren

### Neue Dateien

- `frontend/qm_app/document_working_copy.py`
- `SQL/migrate_document_working_copy_versioning.sql`

## 8. Testplan

### 8.1 Änderungserkennung

- Unveränderte Arbeitskopie erzeugt keine neue Version.
- Geänderte Arbeitskopie wird anhand von SHA-256 erkannt.
- Eine reine Änderung des Zeitstempels ohne Inhaltsänderung erzeugt keine Version.
- Eine während des Lesens veränderte Datei wird nicht übernommen.
- Eine gesperrte Datei führt zu einer verständlichen Fehlermeldung.
- Das Upload-Limit gilt auch für Arbeitskopien.

### 8.2 Versionierung und Archivierung

- Geänderte Arbeitskopie erzeugt genau einen Entwurfsnachfolger.
- Der Vorgänger erhält atomar den Status `archiviert`.
- Der Inhalt des Vorgängers bleibt bytegenau unverändert.
- SHA-256 und Dateigröße des Nachfolgers stimmen mit der Arbeitskopie überein.
- Dokumentgruppe, Vorgänger-ID und Dokumenttyp werden korrekt übernommen.
- Alle Zuordnungen zu Thema, Sitzung, Tagesordnungspunkt und Maßnahme werden kopiert.
- Freigabeinformationen des Vorgängers bleiben nachvollziehbar erhalten.
- Eine bereits archivierte Version ohne Nachfolger wird definiert behandelt.

### 8.3 Transaktionen

- Fehler nach der Statusänderung, aber vor dem Einfügen des Nachfolgers, setzt die Archivierung zurück.
- Fehler beim Kopieren einer Zuordnung entfernt auch den bereits eingefügten Nachfolger und setzt die Archivierung zurück.
- Nach einem Rollback existiert keine unvollständige Versionskette.

### 8.4 Konflikte

- Statusänderung nach dem Öffnen führt zu `ConcurrencyError`.
- Direkte Inhaltsänderung ohne Versionserhöhung wird über die Prüfsumme erkannt.
- Bereits vorhandener Nachfolger verhindert eine Verzweigung.
- Zwei parallele Übernahmen liefern genau einen Erfolg.
- Der eindeutige Datenbankindex verhindert Mehrfachnachfolger auch außerhalb des Repository-Codes.
- Die Arbeitskopie bleibt nach jedem Konflikt erhalten.

### 8.5 Oberfläche und temporäre Dateien

- Der Übernahme-Button ist ohne Arbeitskopie deaktiviert.
- Öffnen legt eine inhaltlich identische temporäre Datei an.
- Erneutes Öffnen verwendet die bestehende Arbeitskopie oder fordert eine bewusste Entscheidung an.
- Nach erfolgreicher Übernahme wird der Nachfolger ausgewählt.
- Normale temporäre Verzeichnisse werden beim Programmende entfernt.
- Gesperrte Verzeichnisse werden nicht gewaltsam gelöscht.
- Eindeutig verwaiste QM-Verzeichnisse werden beim nächsten Start bereinigt.

### 8.6 Manuelle Prüfung

1. Ein kleines Word-, PDF- oder Textdokument hochladen.
2. Dokument über **Öffnen** starten.
3. Im externen Programm ändern und speichern.
4. **Bearbeitete Arbeitskopie übernehmen** auswählen.
5. Bestätigung der neuen Version durchführen.
6. Prüfen, dass der Vorgänger archiviert und der Nachfolger als Entwurf vorhanden ist.
7. Beide Versionen herunterladen und inhaltlich vergleichen.
8. Den Vorgang parallel in zwei Anwendungsinstanzen wiederholen und die Konfliktmeldung prüfen.
9. Einen simulierten Datenbankfehler auslösen und kontrollieren, dass die Archivierung vollständig zurückgerollt wurde.

## 9. Empfohlene Umsetzungsreihenfolge

1. Repository-Snapshot und gemeinsame Integritätsprüfung einführen.
2. Atomare Archivierungs- und Nachfolgeroperation implementieren.
3. Datenbankindex und Schutztrigger samt Migration ergänzen.
4. Arbeitskopien-Manager implementieren.
5. Öffnen-Workflow auf den Manager umstellen.
6. Expliziten Übernahme-Button und Konflikthinweise ergänzen.
7. Repository- und Datenbanktests ergänzen.
8. UI- und Temporärdateitests ergänzen.
9. Dokumentation und manuelle Prüfanleitung aktualisieren.

## 10. Abnahmekriterien

Die Umsetzung gilt als abgeschlossen, wenn:

- eine extern bearbeitete Arbeitskopie ausdrücklich übernommen werden kann;
- unveränderte Arbeitskopien keine neue Datenbankversion erzeugen;
- Vorgängerarchivierung, Nachfolgeranlage und Zuordnungskopie atomar erfolgen;
- der ursprüngliche Dokumentinhalt unverändert erhalten bleibt;
- keine zwei direkten Nachfolger entstehen können;
- parallele oder zwischenzeitliche Änderungen zuverlässig erkannt werden;
- die Arbeitskopie bei Konflikten und Fehlern nicht verloren geht;
- temporäre Dateien kontrolliert und sicher bereinigt werden;
- alle automatischen Tests sowie der manuelle End-to-End-Test erfolgreich sind.

## 11. Hinweis zum aktuellen Teststand

Die Python-Quellen und Tests wurden nach der Umsetzung vollständig kompiliert.
Direkte Prüfungen der Arbeitskopien-Verwaltung, der neuen UI-Struktur und des
SQL-Schema-Vertrags waren erfolgreich. Am 24.11.2026 sammelte pytest unter
Windows 42 Testfälle: 23 lokale Tests bestanden, 19 PostgreSQL-Tests wurden ohne
gesetztes `QM_TEST_DSN` erwartungsgemäß übersprungen. Für einen vollständigen
Datenbank-Testlauf muss noch eine gesonderte Testdatenbank-Verbindung konfiguriert
werden; die produktive Datenbank wurde dafür nicht als Testziel verwendet.

