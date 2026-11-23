# QM Desktop

Desktop-Frontend gemäß `.junie/plans/qm-pyside6-frontend.md`.
Python 3.10+, PySide6 und psycopg2; das vorhandene SQL-Schema bleibt maßgeblich.

## Stand

Schritt 1 ist implementiert: Login, passwortfreies Verbindungsprofil,
Datenbankzugriff mit Transaktionskontext und Fehlerübersetzung, Dataclasses,
Statuskonstanten, generisches Tabellenmodell und Hauptfenster mit Navigation.
Schritt 2 ergänzt die Themenliste mit kombinierbaren Status-, Kategorie- und
Freitextfiltern, Anlegen/Bearbeiten, Wiederaufnahme mit Pflichtbegründung und
eine schreibgeschützte Verlaufsansicht. Bei einem Versionskonflikt lädt der
Dialog nach einem Hinweis den aktuellen Stand; eigene ungespeicherte Eingaben
werden ersetzt. Abgeschlossene/abgebrochene Themen werden über die eigene
Wiederaufnahme-Aktion reaktiviert. Beim Abschließen wird der Abschlusszeitpunkt
gesetzt, bei Wiederaufnahme gelöscht.
Schritt 3 ergänzt Sitzungen mit Datum, optionalen Zeiten, Teilnehmenden und
Tagesordnung. TOPs unterstützen Themenzuordnung, Nummer, Reihenfolge, Status,
Ergebnis/Beschluss und den Verweis auf eine Folgesitzung. Sitzungen und TOPs haben
Verlaufsansichten.
Schritt 4 ergänzt Maßnahmen als Gesamtübersicht und Themen-Tab, Filter,
Überfälligkeitsmarkierung, Begründungen, Wirksamkeitsprüfung und Anlage aus einem
bereits gespeicherten TOP.
Schritt 5 ergänzt Dokumente in allen vier Kontexten sowie eine Gesamtübersicht:
Upload, Zuordnung, Download/Öffnen, Statuswechsel, Dateinamensuche und neue
Versionen. Die Anwendung verändert das Datenbankschema nicht.
Eine manuelle Prüfanleitung und die konkreten Speicherregeln stehen in `PRUEFUNG.md`.

## Auslieferbares App-Bundle bauen

Die [Buildanleitung](../BUILD.md) beschreibt Cython-/PyInstaller-Builds für
macOS und Windows sowie die genauen Befehle für `frontend/.venv`.
Dafür `requirements-build.txt` aus dem Projektordner installieren.
Unter macOS wird ein vorhandenes `frontend/qm.icns` bevorzugt; ansonsten
konvertiert Pillow das `.ico`-Icon. Bei `No module named 'PIL'` die
[Icon-Fehlerbehebung](../BUILD.md#app-icon-und-fehler-no-module-named-pil) beachten.

## Installation und Start

Im Projektverzeichnis eine eigene Umgebung für das Frontend erstellen.
Die vorhandene `venv` muss dafür nicht verändert werden.

macOS/Linux:

```sh
python3 -m venv frontend/.venv
frontend/.venv/bin/python -m pip install -r frontend/requirements-dev.txt
frontend/.venv/bin/python frontend/main.py
```

Windows (PowerShell):

```powershell
py -3 -m venv frontend/.venv
frontend/.venv/Scripts/python.exe -m pip install -r frontend/requirements-dev.txt
frontend/.venv/Scripts/python.exe frontend/main.py
```

Für den reinen Betrieb genügt `requirements.txt`.
Die Anwendung verwendet standardmäßig Port `5432`, Datenbank `qm` und Benutzer
`qm`. Unter Windows ist der Standardhost `139.64.201.9`, unter macOS
`localhost`. Alte gespeicherte Datenbankwerte `epz` und `epz.qm` werden beim
Laden auf `qm` normalisiert. Im Login können Host, Port, Datenbank und Benutzer
bei Bedarf geändert werden.

Die Datenbank und das Schema `qm` müssen bereits vorhanden sein. Die Anwendung
erstellt oder verändert keine Tabellen. Der Login prüft die Verbindung und das
Vorhandensein von `qm.thema`.
Das Passwort wird nicht in QSettings gespeichert; erfolgreich verwendete
Verbindungsdaten ohne Passwort werden lokal gespeichert.

Die Anmelderolle `qm` besitzt keine Datenbankobjekte und keine direkten
Tabellenrechte. Sie erbt die benötigten Rechte von der nicht anmeldbaren
Gruppenrolle `qm_app`; Eigentümer der Objekte ist `qm_owner`. Weitere Benutzer
werden ebenfalls `qm_app` zugeordnet und erhalten in der Datenbank `qm` den
Suchpfad `qm, pg_catalog`.

## Tests

```sh
frontend/.venv/bin/python -m pytest -c frontend/pytest.ini frontend/tests
```

Die UI-Tests verwenden automatisch Qt im Offscreen-Modus. Sie prüfen Login,
Navigation, Filter/Sortierung und die Speicherung des Verbindungsprofils.
Weitere Tests prüfen den Transaktionskontext und gleichen Datenmodelle sowie
Statuswerte mit dem SQL-Schema ab.

Datenbanktests nutzen `QM_TEST_DSN` (libpq-Verbindungszeichenfolge einer separaten
Testdatenbank mit bestehendem QM-Schema). Ohne diese Variable werden sie
übersprungen. Der Verbindungstest liest ausschließlich. Repository- und
Datenbank-UI-Tests erzeugen Testdatensätze, rollen aber sämtliche Änderungen
einschließlich Audit-Einträgen zurück. PostgreSQL-Sequenzen können dabei Lücken
erhalten. Ein Schema wird nicht automatisch angelegt. Zugangsdaten nicht einchecken.

Stand nach Schritt 5: 36 Tests bestanden gegen PostgreSQL 17.12 auf macOS.
Der Start externer Programme zum Öffnen von Dokumenten wird im automatischen
Test simuliert; Dateiexport und temporäre Dateien werden tatsächlich geprüft.

## Speicherregeln

Repository-Operationen verwenden `Database.transaction()`; zusammengehörige
Schreibvorgänge teilen sich einen Cursor. Transaktionen nicht verschachteln.
Für fachliche Benutzerfelder gilt `Database.user` (vom Server ermittelter
`current_user`). Der Datenbank-Audittrigger verwendet `session_user`, damit bei
der Ausführung als geschützte Eigentümerfunktion der tatsächlich angemeldete
Benutzer protokolliert wird.
Versionskonflikte werden durch `UPDATE ... WHERE id = %s AND version = %s`
und Prüfung von `rowcount` erkannt. Dokumente werden zusätzlich je Versionsgruppe
mit einer transaktionsgebundenen PostgreSQL-Advisory-Sperre serialisiert.

## Dokumente

Im Dokument-Tab eines gespeicherten Themas **Hochladen** wählen; die Zuordnung
wird zusammen mit den Datei-Bytes gespeichert. Die globale Dokumentenübersicht
fragt beim Upload nach dem Ziel. Ein bestehendes Dokument lässt sich dort über
**Zuordnen** mit weiteren Themen/Sitzungen/TOPs/Maßnahmen verknüpfen.
**Zuordnung lösen** entfernt im jeweiligen Tab nur die Verbindung, nicht die Datei.

**Neue Version** legt eine neue Datei als Entwurf an und übernimmt alle vorhandenen
Zuordnungen der ausgewählten Vorgängerversion. Deren Inhalt bleibt unverändert.
Bereits abgelöste Versionen können keine weiteren direkten Nachfolger erhalten;
bitte den letzten Nachfolger auswählen. Die Liste zeigt auch ältere Versionen.

Die vorhandene Spalte `version` dient zugleich als optimistischer Änderungsstand:
Neue Dateien starten mit 1, Statuswechsel erhöhen den Stand der jeweiligen Zeile,
ein neuer Nachfolger startet mit Vorgängerstand + 1. Sie ist deshalb **keine reine
Zählung der Inhaltsversionen**; die Inhaltskette ergibt sich aus Dokumentgruppe
und Vorgänger-UUID. Stände unterschiedlicher Zeilen können sich überschneiden.
Das ist die MVP-Lösung ohne Schemaänderung. Eine getrennte Inhaltsversionsnummer
ist als spätere Entscheidung in `TODO.md` festgehalten.

Freigaben setzen Benutzer und Zeitpunkt. `qm.dokument` hat weder einen
Versions-Trigger noch `geaendert_von`; der Repository-Code erhöht die Version
explizit. Das bestehende Schema auditiert Dokumente/Zuordnungen nicht in
`qm.verlauf`. Diese Grenze bleibt sichtbar in der Prüfanleitung und TODO-Liste.

Listen laden nur Metadaten. Download prüft Dateigröße und, sofern vorhanden,
SHA-256 gegen die ausgelesenen Bytes. **Öffnen** erzeugt eine temporäre Kopie,
die bis zum Beenden der Anwendung verfügbar bleibt. Änderungen dieser Kopie
werden nicht automatisch zurückgeladen; dafür **Neue Version** verwenden.

Das Upload-Limit beträgt standardmäßig 25 MB und ist über **Upload-Limit** lokal
konfigurierbar (QSettings). Übertragungen erfolgen synchron mit Wartecursor.
Eine Volltextsuche ist weiterhin nicht Teil des MVP.

## Nächster Schritt

Manuelle Abnahme nach `PRUEFUNG.md`, anschließend die offenen Prüfungen und
fachlichen Entscheidungen in der Projektdatei `TODO.md` bearbeiten.
