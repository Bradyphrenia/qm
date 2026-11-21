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
Verlaufsansichten. Maßnahmen und Dokumente bleiben Platzhalter für Schritte 4–5.
Eine manuelle Prüfanleitung und die konkreten Speicherregeln stehen in `PRUEFUNG.md`.

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
Im Login Host, Port, Datenbank, Benutzer und Passwort eintragen. Das Schema
`qm` muss bereits vorhanden sein. Die Anwendung erstellt oder verändert keine
Tabellen. Der Login prüft die Verbindung und das Vorhandensein von `qm.thema`.
Das Passwort wird nicht in QSettings gespeichert; erfolgreich verwendete
Verbindungsdaten ohne Passwort werden lokal gespeichert.

## Tests

```sh
frontend/.venv/bin/python -m pytest -c frontend/pytest.ini frontend/tests
```

Die UI-Tests verwenden automatisch Qt im Offscreen-Modus. Sie prüfen Login,
Navigation, Filter/Sortierung und die Speicherung des Verbindungsprofils.
Weitere Tests prüfen den Transaktionskontext und gleichen Datenmodelle sowie
Statuswerte mit dem SQL-Schema ab.

Ein optionaler, ausschließlich lesender Datenbanktest nutzt `QM_TEST_DSN`
(libpq-Verbindungszeichenfolge einer separaten Testdatenbank mit bestehendem
QM-Schema). Ohne diese Variable wird er übersprungen. Die Themen-Repositorytests nutzen das vorhandene Schema und rollen sämtliche
Teständerungen einschließlich Audit-Einträgen am Ende zurück. PostgreSQL-Sequenzen
können dabei wie üblich Lücken erhalten. Ein Schema wird nicht automatisch angelegt. Zugangsdaten nicht einchecken.

## Fortsetzung

Als Nächstes folgen Maßnahmen (Schritt 4) und Dokumente einschließlich
Zuordnung zu Themen (Schritt 5).

Repository-Operationen verwenden `Database.transaction()`; zusammengehörige
Schreibvorgänge teilen sich einen Cursor. Transaktionen nicht verschachteln.
Für Auditfelder gilt `Database.user` (vom Server ermittelter `current_user`).
Versionskonflikte werden durch `UPDATE ... WHERE id = %s AND version = %s`
und Prüfung von `rowcount` erkannt; `ConcurrencyError` liegt bereits bereit.

Schemahinweis für Schritt 5: Nur Thema, Sitzung, Besprechung und Maßnahme haben
den automatischen Versions-Trigger. `qm.dokument` besitzt einen Metadaten-Trigger,
aber keinen automatischen Versionszähler und keine `geaendert_von`-Spalte.
Dokumentversionen müssen deshalb gesondert entsprechend dem Schema behandelt
werden. Das Dokument-Datenmodell enthält nur Metadaten, keine Binärinhalte.
