# TODO – QM Desktop

Stand: 21.11.2026, nach Umsetzung der Planschritte 1–5.
Grundlage: `.junie/plans/qm-pyside6-frontend.md` und `frontend/PRUEFUNG.md`.
Nicht abgehakte Punkte sind offene Arbeiten, bekannte Grenzen oder noch zu
entscheidende Erweiterungen. Erledigte Arbeiten sind ausdrücklich markiert.
Das bestehende SQL-Schema bleibt für den MVP maßgeblich.

## Umgesetzte Arbeiten gemäß Plan

- [x] **Schritt 4 – Maßnahmen:** Repository, Gesamtübersicht und Themen-Tab,
  Status-/Verantwortlichenfilter, Hervorhebung überfälliger Maßnahmen,
  Bearbeitung mit Begründung und Wirksamkeitsprüfung, Anlage aus einem TOP.
- [x] **Schritt 5 – Dokumente:** Upload, Zuordnung zu Thema/Sitzung/TOP/Maßnahme,
  Download/Öffnen, Metadaten, Statuswechsel und neue Dokumentversionen.
  Schwerpunkt: Dokumente zunächst zuverlässig zu Themen anlegen und verwalten.
- [x] Dokument-Upload und Zuordnung in einer Transaktion speichern; Listen ohne
  Binärinhalt laden. Größenlimit (Standard 25 MB) und Wartecursor ergänzen.
- [x] Dokumenttests ergänzen: Prüfsumme, Dateigröße, Byte-Gleichheit,
  Versionskette, Konfliktbehandlung und Löschschutz freigegebener Dokumente.

## Dokumentenumsetzung – berücksichtigt

- [x] **Dokumentversionierung ausdrücklich implementieren:** Anders als die
  vier operativen Haupttabellen hat `qm.dokument` keinen automatischen
  Versions-Trigger. `dokument_gruppe_id` und `vorgaenger_dokument_id` für neue
  Versionen nutzen; fachliche Versionen und Schutz vor parallelen Änderungen
  konsistent behandeln.
- [x] `qm.dokument` hat keine Spalte `geaendert_von`. Schreiboperationen am
  tatsächlichen Schema ausrichten; keine nicht vorhandenen Auditfelder annehmen.
- [x] Freigabe setzt `freigegeben_von` und `freigegeben_am` voraus. Verständliche
  Fehlerbehandlung und passende Bedienung vorsehen.
- [x] **Suche nach Dateinamen** in der Dokumentenverwaltung ergänzen. Ein eigenes
  Dokumenttitelfeld existiert bisher nicht. Ein separates Titelfeld ist eine
  spätere, gesondert zu entscheidende Schemaerweiterung.
- [x] **Statusfilter in der Dokumentenliste** (24.11.2026): Auswahlfeld neben der
  Dateinamensuche, analog zu Themen und Maßnahmen. Standard ist **Aktuelle (ohne
  archiviert/obsolet)**; „Alle Status“ oder ein einzelner Status blenden ältere
  Versionen wieder ein. Reiner Anzeigefilter, keine Schemaänderung, Auswahl wird
  nicht gespeichert. Gilt in der Gesamtübersicht und allen Dokument-Tabs.
- [ ] Datenbanktest `test_document_widget_status_and_version` mit erweiterter
  Filterprüfung gegen `qm_test` (inzwischen PostgreSQL 18) ausführen.
- [x] **Neues Dokument aus Word-Vorlage** (25.11.2026): **Öffnen** einer `.dotx`
  erzeugt nach Rückfrage eine `.docx`, speichert sie sofort als Entwurf mit
  Zuordnung und öffnet sie als Arbeitskopie. Die Vorlage bleibt unverändert.
  Keine Schemaänderung, keine neue Abhängigkeit. Build-Selbsttest um
  Dokumentenverwaltung und Vorlagenumwandlung erweitert (7 Fenster).
- [ ] Neue Tests `test_template_to_docx` und
  `test_document_widget_creates_document_from_template` gegen `qm_test` ausführen;
  Build mit erweitertem Selbsttest (`--compile-only`, danach vollständig) prüfen.
- [ ] Protokollvorlage Komplikationsbesprechung als `.dotx` speichern, einem
  Sammelthema „Vorlagen und Formulare“ zuordnen und freigeben.
- [x] Ablauf mit realem Word unter Windows geprüft (Schritt 12 in `PRUEFUNG.md`,
  25.11.2026). Eine nur umbenannte `.docx` mit Endung `.dotx` wird seitdem
  ebenfalls akzeptiert und unverändert übernommen.
- [x] **Deutsche Qt-Standardtexte** (25.11.2026): `main.py` lädt `qtbase_de` und
  setzt die Locale fest auf Deutsch; Ja/Nein, Abbrechen und Dateidialoge waren
  zuvor englisch. Unter Windows aus dem Quellcode bestätigt. Der Build-Selbsttest
  bricht ab, wenn die Übersetzung im Bundle fehlt.
- [ ] Vollständigen Windows-Build ausführen und prüfen, dass PyInstaller die
  Qt-Übersetzungsdateien mitpackt (Selbsttest schlägt sonst fehl).

## Bekannte Grenzen zur späteren Revision

- [ ] **Dokument-Verlauf fachlich entscheiden:** Im vorhandenen Schema werden
  Dokumente, Freigabestatus und Zuordnungen nicht auditiert. Die Anwendung kann
  dafür ohne Schemaergänzung keinen vollständigen Verlauf anbieten.
- [ ] **Inhaltsversion und Änderungsstand trennen?** Im MVP dient `version` auch
  der optimistischen Sperre: Statusänderungen erhöhen den Stand, ein neuer
  Nachfolger startet mit Vorgängerstand + 1. Die Inhaltskette folgt Gruppe und
  Vorgänger-ID, nicht einer strikt fortlaufenden Inhaltsversionsnummer. Falls
  eine eigene fachliche Nummer benötigt wird, Schemaerweiterung planen.
- [x] **Externe Dokument-Schreiber berücksichtigen:** Inhalts- und Kettenfelder
  vorhandener Dokumentversionen werden per Trigger geschützt; ein eindeutiger
  Index verhindert mehrere direkte Nachfolger. Die Versionsgruppen-Sperre
  serialisiert zusätzlich die kooperierenden Anwendungsschreiber.
- [ ] **Vorlagenverwaltung entscheiden:** Vorlagen brauchen derzeit eine
  Zuordnung zu einem Sammelthema, weil jedes Dokument einem Datensatz zugeordnet
  sein muss. Eine eigene Vorlagenauswahl (z. B. direkt in der Sitzung) wäre die
  sauberere Lösung. `.dotm` wird bewusst nicht umgewandelt.
- [ ] **Maßnahmenabschluss abstimmen:** Abschlussdatum wird explizit gepflegt;
  Statuswechsel ergänzen es nicht automatisch. Prüfen, ob künftig ein Pflichtfeld
  oder eine automatische Vorbelegung gewünscht wird.
- [ ] **Fälligkeit der Wirksamkeitsprüfung:** Es gibt bisher nur die
  Umsetzungsfälligkeit. Ein eigenes Prüfdatum für Überfälligkeitswarnungen wäre
  eine gesonderte Erweiterung.
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

- [ ] **Qt-Testprozess beim Beenden untersuchen (Python 3.14.10):** In der neu
  eingerichteten `frontend/.venv` bestanden ohne gesetztes `QM_TEST_DSN` 19 Tests,
  17 Datenbanktests wurden übersprungen. Danach meldete Qt
  `shared QObject was deleted directly`; der Testprozess endete mit Code 139.
  Lebensdauer/Aufräumen der Testwidgets und QApplication prüfen. Der separat
  gestartete native Anwendungsprozess lief weiter; Hauptfenster und geladenes
  Musterthema wurden sichtbar bestätigt. Das ist kein Nachweis eines fehlerfreien
  Beendens der Anwendung selbst.

- [ ] Öffnen verschiedener Dateitypen mit realen externen Programmen auf macOS
  und Windows prüfen. Automatische Tests simulieren den Programmstart und prüfen
  die temporäre Kopie, Änderungserkennung, Übernahme und Lebensdauer.
- [ ] Bedienung mit größeren realistischen PDF-/Word-Dateien und Zeitbedarf bei
  Upload/Download prüfen; diese Inhaltsformate werden unverändert als Bytes gespeichert.

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
- [x] Durchgängigen Ablauf automatisiert getestet:
  Thema → Sitzung/TOP → Beschluss → Maßnahme → Dokument → Verlauf.

## Build und Auslieferung

- [x] Cython-`setup.py` und zwei Einstiegsskripte angelegt: `bundle` (macOS)
  sowie `bundle.bat` (Windows); Anleitung in `BUILD.md`.
- [x] macOS-arm64-Build mit Python 3.14.10, Cython 3.3.1 und PyInstaller 6.22.3
  erfolgreich. Offline-Selbsttest für übersetzte Module und fertiges `qm.app`
  bestanden; zusätzlich alle 36 Tests gegen Cython-Module mit Testdatenbank bestanden.
- [x] Windows-Build auf einem 64-Bit-Windows-Rechner mit passenden MSVC Build
  Tools durchgeführt; beide EXE-Selbsttests bestanden.
- [ ] `qm.exe` und `qm-updater.exe` auf einem Zielrechner ohne Python- und
  Rust-Entwicklungsumgebung testen.
- [ ] macOS-Bundle auf einem weiteren Ziel-Mac testen; Intel-Build bei Bedarf
  separat erstellen. Developer-ID-Signierung/Notarisierung für Verteilung planen.
- [x] QM-Icon eingebunden: Windows verwendet `frontend/qm.ico`; macOS bevorzugt
  `frontend/qm.icns`, falls vorhanden, sonst automatische Konvertierung mit Pillow.
  Pillow ist als macOS-Buildabhängigkeit hinterlegt; die tatsächliche ICO→ICNS-
  Konvertierung wurde unter Python 3.14.10 geprüft (siehe [BUILD.md](BUILD.md)).
- [ ] Vollständigen macOS-Build nach der Iconkorrektur erneut ausführen und die
  Darstellung des App-Icons im Finder/Dock visuell prüfen.
- [ ] Gegebenenfalls Windows-Code-Signierung ergänzen.
- [x] Nativen Windows-Updater als Rust-Unterprojekt umgesetzt: feste Netz- und
  Installationspfade, App-/Updater-Einzelinstanzschutz, Zeitvergleich, stabiles
  Staging, Größe/SHA-256/PE-Prüfung, Austausch mit `.old`-Rücksicherung,
  Protokollierung, lokaler Fallback und gemeinsames Icon.
- [x] Updater in den Windows-Build integriert. `bundle.bat` erzeugt über
  `build_tools/build.py` gemeinsam `dist/qm.exe` und `dist/qm-updater.exe` und
  führt Rust-Format-, Clippy-, Test-, Release- und Selbstprüfung aus.
- [x] Vollständigen gemeinsamen Build mit `bundle.bat` durchgeführt. Beide
  Selbsttests bestanden; `dist/qm.exe` und `dist/qm-updater.exe` wurden erzeugt
  und ihre eingebetteten 32×32-QM-Symbole stimmen überein.
- [ ] Beide fertigen Dateien im festgelegten lokalen Ordner installieren und
  die Anwenderverknüpfung auf `qm-updater.exe` setzen.
- [ ] Echte Veröffentlichung über `J:\EPZ\Daten OA Troeger\qm.exe.uploading`
  mit anschließendem Umbenennen abnehmen; Netzunterbrechung, parallele Starts,
  beschädigte Quelle, Rollback und Protokoll kontrollieren.
- [ ] `qm.exe` und `qm-updater.exe` mit demselben Code-Signing-Zertifikat
  signieren und Pilotprüfung mit dem tatsächlich eingesetzten Virenscanner
  sowie SmartScreen durchführen. Der Code kann keine Alarmfreiheit garantieren.

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

- [x] 36 Tests nach Schritt 5 bestanden; neue Testdatensätze wurden zurückgerollt.
- [x] Maßnahmen- und Dokumentdialoge visuell im Offscreen-Modus kontrolliert.

- [x] UUID-Auswahl in Themen-/Folgesitzungs-Comboboxen korrigiert und durch
  Bearbeitungs- und Vertagungstests abgesichert.
- [x] 23 automatisierte Tests nach Schritt 3 erfolgreich ausgeführt,
  einschließlich Datenbanktests; Testdatensätze wurden zurückgerollt.
- [x] Drei synthetische Musterdokumente zu einem Testthema gespeichert;
  Dateigröße, SHA-256 und unverändertes Auslesen geprüft.

Hinweis: Automatische Repositorytests rollen Daten und Audit-Einträge zurück.
Lücken in Audit-Sequenznummern können dabei regulär entstehen. Dauerhafte
manuelle Musterdaten sind davon getrennt zu betrachten.
