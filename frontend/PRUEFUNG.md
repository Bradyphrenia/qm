# Prüfanleitung – Stand nach Schritt 5

## Umfang

Umgesetzt: Anmeldung, Themen und Verlauf sowie Sitzungen, Teilnehmende und
Tagesordnung, Maßnahmen und Dokumentenverwaltung. Das vorhandene SQL-Schema
wurde nicht verändert.

## Manuell ausprobieren

1. Anwendung nach README starten. Unter Windows den Standardhost
   `139.64.201.9`, unter macOS `localhost`, Port `5432`, Datenbank `qm` und den
   Benutzer `qm` verwenden. Das Passwort im Login eingeben; es wird nicht im
   Verbindungsprofil gespeichert.
2. Unter **Themen** das vorhandene Musterthema suchen. Stammdaten und Verlauf
   öffnen. Für eigene Versuche ein neues, ausdrücklich als Test gekennzeichnetes
   Thema verwenden.
3. Unter **Sitzungen** eine neue Testsitzung anlegen. Bezeichnung und Datum
   setzen, nach Bedarf Beginn/Ende aktivieren. Im Tab **Teilnehmende** eine
   fiktive Person mit Rolle, Anwesenheit und Vertretung eintragen.
4. **Sitzung speichern**, anschließend die Sitzung erneut öffnen. Personen
   kontrollieren; eine Änderung speichern und erneut überprüfen.
5. Im Tab **Tagesordnung** mit **Thema zuordnen** das Testthema auswählen,
   TOP-Nummer und numerische Reihenfolge vergeben. Einen zweiten TOP mit einem
   anderen Thema zuordnen und die Reihenfolge kontrollieren.
6. Einen TOP bearbeiten, Status `beschlossen`, Ergebnis und Beschluss eingeben.
   Speichern, erneut öffnen und den Verlauf ansehen. Ein Thema darf pro Sitzung
   nur einmal zugeordnet sein; ein zweiter Versuch muss verständlich abgewiesen
   werden.
7. Eine weitere Testsitzung anlegen. Im ersten TOP Status `vertagt` und die
   zweite Sitzung als Ziel wählen. Nach erneutem Öffnen muss das Ziel erhalten
   sein. Es wird in der Folgesitzung kein TOP automatisch erzeugt.
8. Optional zwei Anwendungsfenster öffnen, denselben Datensatz laden und in
   beiden bearbeiten: Nach dem ersten Speichern muss das zweite Fenster einen
   Versionskonflikt melden und den aktuellen Stand laden.

Diese manuellen Schritte speichern Testdaten dauerhaft. Die automatischen
Repositorytests rollen ihre Änderungen dagegen zurück.

## Maßnahmen und Dokumente ausprobieren

1. Ein gespeichertes Thema öffnen und im Tab **Maßnahmen** eine Maßnahme mit
   Titel, Verantwortlichen und Fälligkeit anlegen. Alternativ bei einem
   gespeicherten TOP **Maßnahme aus gespeichertem TOP anlegen** verwenden:
   der gespeicherte Beschluss wird als Beschreibung vorgeschlagen.
2. Die Maßnahme erneut öffnen, Umsetzung und Abschlussdatum erfassen. Unter
   **Wirksamkeitsprüfung** Ergebnis, Datum und prüfende Person eingeben.
   Status `wirksam`/`nicht_wirksam` muss zum Prüfungsergebnis passen.
3. Eine offene Maßnahme mit gestriger Fälligkeit anlegen. In der Übersicht muss
   sie orange hervorgehoben sein. Status- und Verantwortlichenfilter ausprobieren.
   Bei Verschiebung des Termins nach hinten oder Entfernen eines vorhandenen
   Termins eine Begründung eingeben. Ebenso bei Abbruch/Ablehnung/Zurückstellung.
4. Ein gespeichertes Thema öffnen, Tab **Dokumente**, **Hochladen**. Eine kleine
   Testdatei wählen und optional den Dokumenttyp angeben. Dateiname, Dateigröße
   und bei Auswahl SHA-256 kontrollieren. Die bestehenden Musterdokumente lassen
   sich ebenfalls anzeigen und herunterladen.
5. **Speichern unter** ausprobieren und die Datei vergleichen. **Öffnen** muss
   das zugehörige externe Programm starten; dies ist noch manuell zu prüfen.
6. In der globalen Dokumentenübersicht den Dateinamen suchen. Mit **Zuordnen**
   das Dokument zusätzlich einer Sitzung, einem TOP oder einer Maßnahme zuordnen.
   Im jeweiligen Dokument-Tab prüfen. **Zuordnung lösen** lässt die Datei und
   andere Zuordnungen bestehen.
7. **Neue Version** mit einer veränderten Testdatei wählen. Beide Inhalte müssen
   erhalten bleiben, der Vorgänger ist anschließend archiviert und der neue
   Datensatz ist ein Entwurf mit denselben Zuordnungen. Vorgänger/Gruppe prüfen.
   Der archivierte Vorgänger ist in der Standardauswahl **Aktuelle (ohne
   archiviert/obsolet)** ausgeblendet; über **Alle Status** oder `archiviert`
   wird er wieder sichtbar. Die Zählzeile nennt dann „x von y Dokumenten“.
   Eine erneute Versionierung vom bereits abgelösten Vorgänger muss abgewiesen werden.
8. Den neuen Entwurf mit **Öffnen** starten, im externen Programm bearbeiten und
   speichern. Danach **Bearbeitete Arbeitskopie übernehmen** wählen. Die Anwendung
   muss die Änderung bestätigen lassen, den geöffneten Entwurf archivieren und
   einen neuen Entwurfsnachfolger erzeugen. Ohne Inhaltsänderung darf kein neuer
   Datensatz entstehen.
9. Optional dieselbe Version in zwei Anwendungsinstanzen öffnen. Nach der ersten
   erfolgreichen Übernahme muss die zweite einen Versionskonflikt melden; deren
   lokale Arbeitskopie muss weiterhin vorhanden sein.
10. Eine Word-Vorlage (`.dotx`) einem Sammelthema, z. B. „Vorlagen und
   Formulare“, hochladen. In der globalen Dokumentenübersicht auswählen und
   **Öffnen** wählen. Nach Bestätigung und Auswahl einer Sitzung muss ein neues
   Dokument `<Vorlagenname>_<Datum>.docx` als Entwurf entstehen, der Sitzung
   zugeordnet sein und sich in Word als normale Datei öffnen. Text ergänzen,
   mit Strg+S speichern (es darf kein „Speichern unter“-Dialog erscheinen) und
   **Bearbeitete Arbeitskopie übernehmen** wählen. Die Vorlage muss unverändert
   bleiben (gleiche Prüfsumme). Abbruch der Rückfrage darf nichts anlegen.
8. Den neuen Datensatz auswählen, Status auf `freigegeben` setzen und neu laden.
   Freigabebenutzer und erhöhter Änderungsstand müssen vorhanden sein.
9. Das Upload-Limit vorübergehend reduzieren; eine zu große Datei muss
   verständlich abgewiesen werden. Danach den gewünschten Wert wiederherstellen.

## Speicherregeln und Grenzen

- Stammdaten und Teilnehmende werden zusammen mit **Sitzung speichern** in einer
  Transaktion gespeichert. Fehlschläge lassen beide unverändert.
- Teilnehmende besitzen im Schema keine eigene Versionsspalte. Änderungen durch
  diese Anwendung werden über die Sitzungs-Version geschützt. Direkte externe
  Änderungen an der Teilnehmertabelle umgehen diesen Schutz.
- Das Schema protokolliert Sitzungsstammdaten und TOPs, aber keine eigenen
  Teilnehmer-Snapshots. Eine Teilnehmeränderung erhöht zwar die Sitzungs-Version,
  ihr vollständiger vorheriger/nachheriger Teilnehmerbestand steht nicht im Audit.
- TOPs werden mit **TOP speichern** separat gespeichert. Das spätere Schließen
  des Sitzungsdialogs ohne Speichern nimmt solche TOP-Änderungen nicht zurück.
- Bei Versionskonflikten werden ungespeicherte Eingaben nach einem Hinweis durch
  den aktuellen Datenbankstand ersetzt.
- Ein neues Thema wird nicht automatisch für eine Sitzung erzeugt: zuerst unter
  **Themen** anlegen, dann der Tagesordnung zuordnen.
- TOP-Reihenfolge wird numerisch gepflegt; Drag-and-drop ist nicht implementiert.
- Vertagungen speichern eine Referenz; automatische Übernahme in die
  Folgesitzung ist nicht implementiert. Ein Ziel darf vorerst offen bleiben.
- `behandelt_am` wird beim ersten Speichern mit `in_beratung` oder `beschlossen`
  gesetzt. Ein früherer Behandlungszeitpunkt bleibt bei Folgeschritten erhalten.
- Eine Löschfunktion für Sitzungen/TOPs ist nicht vorgesehen; TOPs können den
  Status `abgesetzt`, Sitzungen den Status `abgesagt` erhalten.

## Ergänzende Grenzen von Maßnahmen und Dokumenten

- Neue Themen und Maßnahmen zuerst speichern und erneut öffnen, bevor
  zugehörige Dokumente verwaltet werden. Dokument- und Maßnahmenaktionen werden
  sofort und unabhängig von ungespeicherten Stammdaten des umgebenden Dialogs
  gespeichert.
- Orange bedeutet überfällige Umsetzung: Datum vor heute, kein Abschlussdatum,
  Status `offen`, `in_bearbeitung` oder `zurueckgestellt`. Für ausstehende
  Wirksamkeitsprüfungen gibt es im Schema keine eigene Fälligkeit.
- Der Abschluss einer Maßnahme wird mit explizitem Abschlussdatum gepflegt;
  ein Statuswechsel allein ergänzt dieses Datum nicht automatisch.
- `version` beim Dokument ist zugleich Änderungsstand, nicht ausschließlich
  Inhaltsversionsnummer. Statusänderungen zählen mit. Vorgänger/Gruppe bilden
  die Inhaltskette; Details und Beispiele zur Semantik stehen in der README.
- Dokumentinhalte werden beim Bearbeiten nicht überschrieben, sondern als neue
  Zeile gespeichert. Es gibt keine allgemeine Löschaktion in der Oberfläche;
  für nicht mehr aktuelle Dateien den Status wechseln oder eine Zuordnung lösen.
- Das bestehende Schema protokolliert Dokumentstatus und Dokumentzuordnungen
  nicht im Audit. Es gibt deshalb keinen vollständigen Dokument-Verlauf.
- Das Migrationsskript schützt Inhalt und Versionsidentität bestehender
  Dokumentzeilen gegen direkte SQL-Änderungen und erzwingt höchstens einen
  direkten Nachfolger. Die transaktionsgebundene Gruppensperre bleibt ein
  zusätzlicher Schutz für kooperierende Anwendungsschreiber.
- Änderungen an einer extern geöffneten Arbeitskopie werden bewusst nicht
  automatisch hochgeladen. Nach dem Speichern ist **Bearbeitete Arbeitskopie
  übernehmen** zu verwenden. Konflikte lassen die lokale Kopie bestehen.
- Word-Vorlagen benötigen derzeit eine Zuordnung zu einem Datensatz (Sammelthema),
  da es keine eigene Vorlagenverwaltung gibt. `.dotm` wird nicht umgewandelt.

## Automatische Prüfung

44 Tests prüfen Login, Filter, Schemaabgleich, Themen-/Sitzungs-/Maßnahmenabläufe,
atomare Speicherung, Versionskonflikte, doppelte Themenzuordnung, Beschlüsse,
Vertagung, Wirksamkeitsprüfung sowie Dokument-Upload, Download, Größenlimit,
Prüfsummen, Versionen, Zuordnungen, den Datenbank-Löschschutz und den
Windows-Einzelinstanzschutz.
Seit 25.11.2026 kommen zwei Tests für Word-Vorlagen hinzu (insgesamt 46); sie
sind noch nicht gegen `qm_test` gelaufen. Der Build-Selbsttest prüft zusätzlich
die Dokumentenverwaltung als siebtes Fenster und die Vorlagenumwandlung im
kompilierten Modul.
Auch der durchgängige Weg vom Thema über den TOP zur Maßnahme und ihrem Dokument
ist geprüft. Das Öffnen externer Programme wird simuliert; temporäre Dateikopien
und Dateiexport werden tatsächlich geprüft. Die Tests liefen
historisch gegen die lokale PostgreSQL-17-Datenbank `epz`; die Fensterprüfungen
liefen zunächst im Qt-Offscreen-Modus auf macOS. Am 24.11.2026 bestanden alle 44
Tests unter Windows mit Python 3.12.4 und pytest 9.2.0 gegen `qm_test`. Der
gemeinsame Windows-Build und beide EXE-Selbsttests bestanden ebenfalls.
PostgreSQL 10 ist weiterhin nicht getestet.

Die Tests erstellen keine Datenbankstrukturen. Mit gesetztem `QM_TEST_DSN`
verwenden sie das vorhandene Schema und rollen ihre neuen Datensätze zurück.
Das kann reguläre Lücken in Audit-Sequenznummern erzeugen. Die bereits angelegten
Musterdokumente und ihr Thema bleiben erhalten.

## Windows-Updater manuell abnehmen

1. `bundle.bat` ausführen und prüfen, dass `dist/qm.exe` und
   `dist/qm-updater.exe` vorhanden sind und dasselbe QM-Symbol zeigen.
2. Beide Dateien unmittelbar nach `C:\Users\chir-arzt\Documents\qm` kopieren.
   Den normalen Start nur über `qm-updater.exe` ausführen.
3. Ohne neuere Netzdatei prüfen, dass die lokale App startet. Danach das
   Netzlaufwerk vorübergehend trennen; die lokale App muss weiterhin starten.
4. Eine neue `qm.exe` erst als `qm.exe.uploading` nach
   `J:\EPZ\Daten OA Troeger` kopieren und nach vollständigem Abschluss in
   `qm.exe` umbenennen. Beim nächsten Updater-Start muss sie lokal übernommen
   werden; die Vorversion muss als `qm.exe.old` erhalten bleiben.
5. QM geöffnet lassen und den Updater erneut starten. Er muss den Austausch mit
   einem verständlichen Hinweis ablehnen. Auch ein zweiter direkter Start von
   `qm.exe` darf kein zweites Anwendungsfenster öffnen.
6. Zwei Updater nahezu gleichzeitig starten. Nur einer darf weiterarbeiten.
7. Eine unvollständige oder nicht als PE lesbare Netzdatei bereitstellen. Die
   vorhandene lokale Anwendung darf nicht ersetzt werden.
8. `qm-updater.exe` testweise in einen anderen Ordner kopieren. Ein normaler
   Start muss wegen des falschen Installationsorts abgelehnt werden.
9. `logs/updater.log`, Größe und Änderungszeit der lokalen EXE sowie das
   Verhalten des tatsächlich eingesetzten Virenscanners und SmartScreen prüfen.

Die automatisierte Prüfung umfasst zusätzlich elf Rust-Tests für Zeitvergleich,
Erstinstallation, Austausch mit Vorversion, PE-Prüfung, Staging, Windows-Mutex
und Prozesspfadprüfung. Am
24.11.2026 waren Rust-Tests, Clippy, Release-Build, EXE-Selbsttest und alle 44
Python-Tests erfolgreich. Eine Signatur-, SmartScreen- und Virenscannerprüfung
ist weiterhin eine manuelle Abnahme auf dem Zielrechner.
