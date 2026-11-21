# TODO – QM Desktop

Stand: 21.11.2026, nach Umsetzung der Planschritte 1–3.
Grundlage: `.junie/plans/qm-pyside6-frontend.md` und `frontend/PRUEFUNG.md`.
Die folgenden Punkte sind offene Arbeiten, bekannte Grenzen oder noch zu
entscheidende Erweiterungen. Sie sind keine bereits umgesetzten Funktionen.
Das bestehende SQL-Schema bleibt für den MVP maßgeblich.

## Nächste Arbeiten gemäß Plan

- [ ] **Schritt 4 – Maßnahmen:** Repository, Gesamtübersicht und Themen-Tab,
  Status-/Verantwortlichenfilter, Hervorhebung überfälliger Maßnahmen,
  Bearbeitung mit Begründung und Wirksamkeitsprüfung, Anlage aus einem TOP.
- [ ] **Schritt 5 – Dokumente:** Upload, Zuordnung zu Thema/Sitzung/TOP/Maßnahme,
  Download/Öffnen, Metadaten, Statuswechsel und neue Dokumentversionen.
  Schwerpunkt: Dokumente zunächst zuverlässig zu Themen anlegen und verwalten.
- [ ] Dokument-Upload und Zuordnung in einer Transaktion speichern; Listen ohne
  Binärinhalt laden. Größenlimit (Standard 25 MB) und Wartecursor ergänzen.
- [ ] Dokumenttests ergänzen: Prüfsumme, Dateigröße, Byte-Gleichheit,
  Versionskette, Konfliktbehandlung und Löschschutz freigegebener Dokumente.

## Bei der Dokumentenumsetzung beachten

- [ ] **Dokumentversionierung ausdrücklich implementieren:** Anders als die
  vier operativen Haupttabellen hat `qm.dokument` keinen automatischen
  Versions-Trigger. `dokument_gruppe_id` und `vorgaenger_dokument_id` für neue
  Versionen nutzen; fachliche Versionen und Schutz vor parallelen Änderungen
  konsistent behandeln.
- [ ] `qm.dokument` hat keine Spalte `geaendert_von`. Schreiboperationen am
  tatsächlichen Schema ausrichten; keine nicht vorhandenen Auditfelder annehmen.
- [ ] Freigabe setzt `freigegeben_von` und `freigegeben_am` voraus. Verständliche
  Fehlerbehandlung und passende Bedienung vorsehen.
- [ ] **Suche nach Dateinamen** in der Dokumentenverwaltung ergänzen. Ein eigenes
  Dokumenttitelfeld existiert bisher nicht. Ein separates Titelfeld ist eine
  spätere, gesondert zu entscheidende Schemaerweiterung.

## Bekannte Grenzen zur späteren Revision

- [ ] **Teilnehmer-Verlauf fachlich entscheiden:** Das Schema auditiert
  Sitzungen und TOPs, aber keine Teilnehmer-Snapshots. Teilnehmeränderungen
  erhöhen über die Anwendung die Sitzungs-Version; die vollständigen alten und
  neuen Teilnehmerlisten fehlen im Audit. Eine Erweiterung separat planen.
- [ ] **Externe Teilnehmeränderungen berücksichtigen:** Die optimistische
  Sperre schützt Teilnehmeränderungen durch die Anwendung über die Sitzung.
  Direkte Änderungen an `qm.sitzung_teilnehmer` umgehen diesen Schutz. Klären,
  ob weitere schreibende Anwendungen unterstützt werden müssen.
- [ ] **Versionskonflikte komfortabler behandeln:** Aktuell werden eigene
  ungespeicherte Eingaben nach einem Hinweis durch den aktuellen Datenbankstand
  ersetzt. Später Eingaben erhalten und einen Vergleich bzw. Übernahme anbieten.
- [ ] **Getrennte Speichervorgänge prüfen:** Sitzungsstammdaten und Teilnehmende
  werden gemeinsam gespeichert, TOPs separat. Das Schließen des Sitzungsdialogs
  ohne Speichern nimmt zuvor gespeicherte TOPs nicht zurück. Verständlichkeit
  der Hinweise beim manuellen Test prüfen.
- [ ] **Neue Sitzung bequemer weiterbearbeiten:** Aktuell erst speichern und
  erneut öffnen, bevor Themen der Tagesordnung zugeordnet werden können.
- [ ] **Vertagungen fachlich abstimmen:** Aktuell nur Referenz auf eine andere
  Sitzung, keine automatische TOP-Anlage dort; ein Ziel darf offen bleiben.
  Entscheiden, ob automatische Übernahme oder ein Pflichtziel gewünscht sind.
- [ ] **Behandlungszeitpunkt prüfen:** `behandelt_am` wird beim ersten Speichern
  mit `in_beratung` oder `beschlossen` gesetzt und danach beibehalten.
  Entscheiden, ob eine manuelle Korrektur benötigt wird.

## Noch ausstehende Verifikation

- [ ] Manuelle Durchsicht der Abläufe nach `frontend/PRUEFUNG.md`, insbesondere
  Speicherverhalten, Abbruch, Konflikthinweise und Bedienung der Tabellen.
- [ ] Gleichzeitige Bearbeitung mit zwei getrennten Anwendungsfenstern bzw.
  Verbindungen prüfen. Die bisherigen Tests decken veraltete Versionsstände ab,
  aber keinen vollständigen parallelen Mehrbenutzerbetrieb.
- [ ] Installation, Start und Bedienung unter **Windows 64-Bit** prüfen.
- [ ] Kompatibilität mit dem vorgesehenen **PostgreSQL 10.10** verifizieren.
  Bisherige Datenbanktests liefen mit PostgreSQL 17.12 auf macOS.
- [ ] Unterstützte Python-Versionen ab 3.10 samt passenden Abhängigkeiten
  verifizieren; die bisherigen Testläufe decken keine vollständige Versionsmatrix ab.
- [ ] Vor dem späteren Abschluss des MVP einen durchgängigen Ablauf testen:
  Thema → Sitzung/TOP → Beschluss → Maßnahme → Dokument → Verlauf.

## Optionale Erweiterungen nach dem MVP

- [ ] Volltextsuche über Dokumentinhalte separat planen: Textextraktion für
  PDF/Word/Text, gegebenenfalls OCR, separate Textablage und PostgreSQL-Volltextindex.
  Der aktuelle BYTEA-Inhalt ist nicht inhaltlich indexiert; der vorhandene
  SHA-256-Index unterstützt keine Wortsuche. Volltextsuche ist laut Plan außerhalb
  des MVP und für das erste Anlegen/Verwalten von Dokumenten nicht erforderlich.
- [ ] Drag-and-drop für TOP-Reihenfolge erwägen; aktuell numerische Sortierung.
- [ ] Direktes Anlegen eines Themas aus der Tagesordnung erwägen; aktuell zuerst
  in der Themenverwaltung anlegen, anschließend zuordnen.
- [ ] Bei Bedarf Hintergrundübertragung für größere Dokumente ergänzen;
  zunächst ist der synchrone Upload/Download gemäß Plan vorgesehen.

## Bereits erledigt – nicht erneut als Fehler behandeln

- [x] UUID-Auswahl in Themen-/Folgesitzungs-Comboboxen korrigiert und durch
  Bearbeitungs- und Vertagungstests abgesichert.
- [x] 23 automatisierte Tests nach Schritt 3 erfolgreich ausgeführt,
  einschließlich Datenbanktests; Testdatensätze wurden zurückgerollt.
- [x] Drei synthetische Musterdokumente zu einem Testthema gespeichert;
  Dateigröße, SHA-256 und unverändertes Auslesen geprüft.

Hinweis: Automatische Repositorytests rollen Daten und Audit-Einträge zurück.
Lücken in Audit-Sequenznummern können dabei regulär entstehen. Dauerhafte
manuelle Musterdaten sind davon getrennt zu betrachten.
