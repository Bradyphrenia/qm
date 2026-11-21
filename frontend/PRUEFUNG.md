# Prüfanleitung – Stand nach Schritt 3

## Umfang

Umgesetzt: Anmeldung, Themen und Verlauf sowie Sitzungen, Teilnehmende und
Tagesordnung. Maßnahmen und Dokumentenbedienung folgen gemäß Plan in Schritt 4
und 5. Das vorhandene SQL-Schema wurde nicht verändert.

## Manuell ausprobieren

1. Anwendung nach README starten und mit `localhost`, Port `5432`, Datenbank
   `epz` und dem vereinbarten Datenbankbenutzer anmelden. Das Passwort im Login
   eingeben; es wird nicht im Verbindungsprofil gespeichert.
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

## Automatische Prüfung

23 Tests prüfen unter anderem Login, Filter, Schemaabgleich, Themenlebenszyklus,
Sitzungen mit Teilnehmern, atomare Speicherung, Versionskonflikte, doppelte
Themenzuordnung, Sortierung, Beschluss, Vertagung und Verlauf. Die Tests liefen
gegen die lokale PostgreSQL-17-Datenbank `epz`; die Fensterprüfungen liefen im
Qt-Offscreen-Modus auf macOS. Windows und PostgreSQL 10 wurden nicht getestet.

Die Tests erstellen keine Datenbankstrukturen. Mit gesetztem `QM_TEST_DSN`
verwenden sie das vorhandene Schema und rollen ihre neuen Datensätze zurück.
Das kann reguläre Lücken in Audit-Sequenznummern erzeugen. Die bereits angelegten
Musterdokumente und ihr Thema bleiben erhalten.
