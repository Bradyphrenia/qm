# QM-Projekt – bisherige Entwicklung

Stand: 21. November 2026

## Infrastrukturstand vom 23. November 2026

Das QM-Modul wurde aus der Datenbank `epz` in die eigenständige Datenbank `qm`
überführt. Das gleichnamige Schema enthält elf Tabellen. Die frühere Struktur
unter `epz.qm` bleibt vorerst als Rückfallmöglichkeit bestehen.

Die Eigentümerrolle `qm_owner` kann sich nicht anmelden. Die ebenfalls nicht
anmeldbare Gruppenrolle `qm_app` bündelt die minimalen Anwendungsrechte. Der
Login `qm` besitzt keine direkten Tabellenrechte mehr und erbt den Zugriff als
Mitglied von `qm_app`. Das Auditlog ist für die Anwendung nur lesbar.

Das Frontend verwendet als Datenbanknamen `qm`; der Standardhost lautet unter
Windows `139.64.201.9` und unter macOS `localhost`. Alte gespeicherte Werte
`epz` beziehungsweise `epz.qm` werden automatisch auf `qm` umgestellt.

## Ausgangspunkt und Architektur

Das Projekt enthielt zunächst die fachliche Planung, die Schemadokumentation
und `SQL/generate_schema.sql`. Grundlage der Umsetzung war der vorhandene Plan
`.junie/plans/qm-pyside6-frontend.md` mit fünf Entwicklungsschritten.

Darauf wurde unter `frontend/` eine Desktopanwendung mit Python und PySide6
aufgebaut. Der Datenbankzugriff erfolgt mit psycopg2 und handgeschriebenem SQL
in einer Repository-Schicht, getrennt von Datenmodellen und Oberfläche.
Während der ursprünglichen Frontendentwicklung wurde das bestehende
PostgreSQL-Schema `qm` nicht verändert; getestet wurde damals gegen die lokale
Datenbank `epz` mit PostgreSQL 17.12.

## Umgesetzte Funktionen

1. **Grundgerüst und Anmeldung:** Login, Verbindungsprofil ohne gespeichertes
   Passwort, Transaktionen, verständliche Fehlermeldungen, Datenmodelle und
   Hauptfenster mit Navigation.
2. **Themen:** Anlegen, Bearbeiten, Status-/Kategorie-/Textfilter, Wiederaufnahme
   mit Pflichtbegründung und schreibgeschützter Änderungsverlauf.
3. **Sitzungen:** Stammdaten, Teilnehmende, Themen als Tagesordnungspunkte,
   Reihenfolge, Ergebnisse, Beschlüsse und Verweise auf Folgesitzungen bei Vertagung.
4. **Maßnahmen:** Gesamtübersicht und Themen-Tab, Verantwortlichen-/Statusfilter,
   Überfälligkeitsmarkierung, Begründungen, Wirksamkeitsprüfung und Anlage aus TOPs.
5. **Dokumente:** Upload, Zuordnung zu Themen/Sitzungen/TOPs/Maßnahmen,
   Download/Öffnen, Dateinamensuche, Statuswechsel und neue Versionen.
   Dateiinhalte bleiben als BYTEA in der Datenbank; Listen laden nur Metadaten.
   Das Upload-Limit beträgt standardmäßig 25 MB und ist konfigurierbar.

Parallele Änderungen werden über Versionsstände erkannt. Dokumentnachfolger
bewahren den bisherigen Inhalt und übernehmen dessen Zuordnungen. Drei
synthetische Musterdokumente wurden einem ausdrücklich gekennzeichneten
Testthema zugeordnet; Dateigröße, SHA-256 und unverändertes Auslesen wurden geprüft.

Die Fensterzeile enthält `© <aktuelles Jahr> Steffen Troeger`.
Die native Anwendung wurde auf macOS gestartet und mit geladenem Musterthema
sichtbar bestätigt.

## Build und Prüfung

Für die Auslieferung wurden `setup.py` für Cython sowie zwei getrennte Skripte
nach dem Vorbild des Prothesen-Projekts angelegt:

- `bundle`: macOS-Build nach `dist/qm.app`.
- `bundle.bat`: Windows-Build nach `dist/qm.exe`.

Die Anwendungsmodule werden in einem separaten Buildverzeichnis übersetzt und
anschließend mit PyInstaller verpackt. Der macOS-arm64-Build mit Python 3.14.10,
Cython 3.3.1 und PyInstaller 6.22.3 wurde erfolgreich erstellt. Offline-Selbsttests
prüfen sowohl die übersetzten Module als auch das fertige Bundle.
Alle 36 Anwendungstests bestanden auch mit den Cython-Modulen und PostgreSQL;
automatisch erzeugte Testdatensätze wurden zurückgerollt.

## Verbleibende Grenzen und nächste Schritte

- Manuelle fachliche Abnahme sowie Windows-Build und Windows-Bedienung stehen aus.
  PostgreSQL 10.10 und die vollständige Python-Versionsmatrix sind noch nicht geprüft.
- Das Schema bietet keinen vollständigen Auditverlauf für Teilnehmerlisten,
  Dokumente und Dokumentzuordnungen.
- Bei Dokumenten ist `version` zugleich Änderungsstand; Statusänderungen zählen
  mit. Die Inhaltskette ergibt sich aus Gruppe und Vorgänger, nicht allein aus
  dieser Nummer.
- Maßnahmen-, TOP- und Dokumentaktionen werden teilweise unabhängig von den
  Stammdaten des umgebenden Dialogs gespeichert. Konflikte laden nach einem
  Hinweis den aktuellen Stand und ersetzen ungespeicherte Eingaben.
- Volltextsuche/OCR, automatische TOP-Übernahme bei Vertagung und Hintergrund-
  Dateiübertragung bleiben spätere Erweiterungen.
- Eine Qt-Auffälligkeit beim Beenden eines separaten Python-Testlaufs ist in der
  TODO-Liste festgehalten. Die erfolgreichen Cython-/Bundle-Prüfungen ersetzen
  nicht die weitere Untersuchung dieses Testabschlusses.
- Signierung/Notarisierung, ein eigenes App-Icon und Tests auf weiteren
  Zielrechnern sind vor einer breiteren Verteilung zu prüfen.

Weitere Details: `TODO.md`, `frontend/README.md`, `frontend/PRUEFUNG.md` und
`BUILD.md`. Das Prothesen-Projekt wurde nur als Buildvorbild gelesen und nicht verändert.
