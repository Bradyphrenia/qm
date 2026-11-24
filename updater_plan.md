# Plan für einen Windows-Updater der QM-Anwendung

## Umsetzungsstand vom 24. November 2026

Der Kern dieses Plans ist umgesetzt. Das Rust-Projekt liegt unter `updater/`;
die Windows-App besitzt den benannten Einzelinstanzschutz, und der Windows-Build
erzeugt `qm.exe` sowie `qm-updater.exe` gemeinsam unter `dist/`. Implementiert
sind feste Pfade, Datumsentscheidung, Stabilitätsprüfung, lokales Staging,
Größe/SHA-256/PE-Prüfung, `.old`-Rücksicherung, Protokollierung, lokaler Start
bei nicht erreichbarer Netzquelle und dasselbe `frontend/qm.ico` für beide EXEs.

Verifiziert wurden am 24.11.2026 `cargo fmt --check`, Clippy ohne Warnungen,
elf Rust-Tests, Release-Build, EXE-Selbsttest sowie 44 Python-Tests gegen
`qm_test`. Auch der vollständige gemeinsame `bundle.bat`-Lauf mit beiden
Selbsttests und die Übereinstimmung der eingebetteten Symbole wurden bestätigt.
Noch offen sind die manuelle Abnahme mit echter Veröffentlichung auf dem
Netzlaufwerk, das Verhalten des eingesetzten Virenscanners/SmartScreen und eine
optionale digitale Signatur.

## Verbindliche Pfade – hier direkt eintragen

Die beiden folgenden Zeilen sind die verbindliche Quelle für die spätere
Implementierung. Bitte jeweils den vollständigen Wert rechts vom Gleichheitszeichen
ersetzen:

```text
NETWORK_EXE=r"J:\EPZ\Daten OA Troeger\qm.exe"
LOCAL_INSTALL_DIR=r"C:\Users\chir-arzt\Documents\qm"
```

Dabei gilt:

- `NETWORK_EXE` ist der vollständige UNC-Pfad einschließlich `qm.exe`;
- `LOCAL_INSTALL_DIR` ist nur der feste lokale Ordner ohne abschließendes
  `qm.exe`;
- `qm.exe` und `qm-updater.exe` müssen beide unmittelbar in diesem Ordner liegen;
- beide Werte bleiben absolute Windows-Pfade;
- Anführungszeichen sind in diesem Block nicht erforderlich;
- der Updater verwendet unabhängig von diesen Pfaden immer
  `frontend/qm.ico` als Programmsymbol.

Bei der Implementierung werden diese Werte aus dem Plan geprüft und als feste
Konstanten nach `updater/src/config.rs` übertragen. Die Markdown-Datei selbst wird
nicht von der Anwendung oder vom Updater zur Laufzeit gelesen. Dadurch bleibt
der Updater unabhängig von einer veränderbaren externen Konfigurationsdatei.

## 1. Ziel

Unter Windows soll die QM-Anwendung ausschließlich über einen separaten Updater
gestartet werden. Der Anwender startet nicht direkt `qm.exe`, sondern den lokal
installierten `qm-updater.exe`.

Der Updater soll:

1. prüfen, ob die QM-Anwendung bereits läuft;
2. auf einer festgelegten Netzfreigabe nach einer neueren `qm.exe` suchen;
3. bei Bedarf die neue Datei sicher lokal installieren;
4. bei fehlendem Update unmittelbar die vorhandene lokale Version verwenden;
5. abschließend immer die lokale QM-Anwendung starten;
6. bei Fehlern die letzte funktionsfähige Version erhalten.

Die Updateentscheidung darf bewusst anhand des Dateidatums erfolgen. Zusätzlich
wird SHA-256 verwendet, um Übertragungsfehler oder unvollständige Dateien zu
erkennen, nicht um die fachliche Versionsreihenfolge zu bestimmen.

## 2. Abgrenzung

- Die Funktion wird ausschließlich unter Windows bereitgestellt.
- macOS-Build und macOS-Startverhalten bleiben unverändert.
- Die QM-Anwendung prüft nicht selbständig im Hintergrund nach Updates.
- Es gibt keinen automatischen Internetzugriff.
- Updates stammen ausschließlich aus einer fest konfigurierten internen
  Netzfreigabe.
- UNC-Quellpfad und lokaler Windows-Installationspfad sind feste Konstanten im
  Quelltext des Updaters; Umgebungsvariablen und externe Pfadkonfigurationen
  werden nicht verwendet.
- Der Updater aktualisiert zunächst nur `qm.exe`, nicht sich selbst.
- Eine automatische Virenscanner-Freigabe oder Ausnahmeregel ist ausdrücklich
  nicht Bestandteil der Lösung.

## 3. Vorhandene Ausgangslage

Der aktuelle Windows-Build erzeugt über Cython und PyInstaller eine einzelne
Datei:

`dist/qm.exe`

Der Windows-Build verwendet:

- PyInstaller `--onefile`;
- eine Anwendung ohne Konsolenfenster;
- das vorhandene QM-Icon;
- deaktivierte UPX-Komprimierung;
- einen Offline-Selbsttest des fertigen Artefakts.

Ein automatischer Updater, eine Ein-Instanz-Sperre und ein installerunabhängiger
Rollbackmechanismus existieren bislang nicht.

## 4. Grundablauf

```text
Anwender startet qm-updater.exe
              │
              ├─ Läuft qm.exe bereits?
              │      └─ Ja: Hinweis anzeigen und Updater beenden
              │
              ├─ Netzfreigabe erreichbar?
              │      ├─ Nein: vorhandene lokale qm.exe starten
              │      └─ Ja: Netzdatei prüfen
              │
              ├─ Netzdatei neuer als lokale Datei?
              │      ├─ Nein: lokale qm.exe starten
              │      └─ Ja: Datei lokal zwischenspeichern und prüfen
              │
              ├─ Sicheren Austausch mit Rollback durchführen
              │
              └─ lokale qm.exe starten und Updater beenden
```

Die Anwendung wird niemals direkt von der Netzfreigabe gestartet.

## 5. Feste Pfade im Quelltext

Der Rust-Updater erhält genau zwei zentrale, fest kompilierte Pfadkonstanten. Sie
werden nicht aus Umgebungsvariablen, Registry, Kommandozeilenargumenten oder
externen Konfigurationsdateien gelesen.

Vorgesehene Datei im Cargo-Projekt:

`updater/src/config.rs`

Vorgesehene Struktur:

```rust
use std::path::PathBuf;

pub const NETWORK_EXE: &str = r"<FESTER-UNC-PFAD>\qm.exe";
pub const LOCAL_INSTALL_DIR: &str = r"<FESTER-WINDOWS-INSTALLATIONSPFAD>";

pub fn local_exe() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("qm.exe")
}

pub fn local_updater() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("qm-updater.exe")
}

pub fn updater_log() -> PathBuf {
    PathBuf::from(LOCAL_INSTALL_DIR).join("logs").join("updater.log")
}
```

Alle Updater-Komponenten importieren diese Konstanten. Pfade dürfen nicht an
weiteren Stellen dupliziert werden. Eine spätere Pfadänderung erfordert bewusst
eine Quelltextänderung, einen neuen Updater-Build und dessen geregelte Verteilung.

Beispiel für die Netzquelle:

```text
\\server\software\qm\qm.exe
```

Beispiel für einen statischen lokalen Installationspfad:

```text
C:\QM\qm.exe
```

Der konkrete Pfad `C:\QM` ist nur ein Beispiel und wird vor der Implementierung
durch den verbindlich festgelegten Installationspfad ersetzt. Liegt der endgültige
Pfad unter `C:\Program Files`, benötigt der Updater in der Regel erhöhte
Schreibrechte. Ein statischer Pfad außerhalb geschützter Systemverzeichnisse kann
ohne Administratorrechte aktualisierbar sein, muss aber organisatorisch und
sicherheitstechnisch freigegeben werden.

Der lokale Installationsordner enthält mindestens:

```text
QM\
├── qm-updater.exe
├── qm.exe
├── qm.exe.old        # nur während oder nach einem Update
├── qm.exe.new        # nur während des Kopiervorgangs
└── logs\
    └── updater.log
```

Der Anwender kann weder Netzquelle noch Installationsziel verändern. Der Updater
akzeptiert keine Pfade aus Kommandozeilenargumenten und startet ausschließlich
die fest kompilierte lokale `qm.exe`.

### Gemeinsamer Installationsordner

`qm.exe` und `qm-updater.exe` liegen zwingend unmittelbar im selben statischen
Installationsordner. Beim Start ermittelt der Rust-Updater seinen eigenen Pfad
über `current_exe()` und prüft:

- Dateiname ist `qm-updater.exe`;
- übergeordnetes Verzeichnis entspricht dem fest kompilierten
  `LOCAL_INSTALL_DIR`;
- die zu startende Hauptanwendung ist ausschließlich die benachbarte `qm.exe`.

Bei abweichendem Startort zeigt der Updater einen verständlichen Hinweis und
führt weder Update noch Programmstart aus. Er kopiert sich nicht selbst in das
Installationsverzeichnis und startet keine Anwendung aus einem fremden Ordner.

Desktop- und Startmenüverknüpfungen zeigen ausschließlich auf
`qm-updater.exe`. `qm.exe` bleibt zwar direkt ausführbar, ist aber nicht der
vorgesehene Einstieg für Anwender.

### 5.1 Rust-Projekt im Repository

Der Updater wird als eigenständiges Cargo-Projekt innerhalb des QM-Repositories
geführt:

```text
updater\
├── Cargo.toml
├── Cargo.lock
├── build.rs
├── src\
│   ├── main.rs
│   ├── config.rs
│   ├── update.rs
│   ├── windows_mutex.rs
│   ├── integrity.rs
│   └── logging.rs
```

Die tatsächlich umgesetzten Rust-Tests liegen als `#[cfg(test)]`-Module direkt
in `src/update.rs` und `src/windows_mutex.rs`. Dadurch können sie auch interne
Fehlerpfade prüfen, ohne öffentliche Test-Schnittstellen einzuführen.

Vorteile gegenüber einem zweiten PyInstaller-Programm:

- native, kleine Windows-EXE ohne gebündelte Python-Laufzeit;
- kein temporäres Entpacken des Updaters beim Start;
- direkter Zugriff auf Windows-Mutex, Prozessstart und Dateifunktionen;
- klar vom Python-Anwendungsbuild getrennte Fehler- und Rollbacklogik;
- geringeres Risiko heuristischer Virenscanner-Treffer, ohne eine Garantie dafür
  geben zu können.

Die Rust-Abhängigkeiten sollen klein und fest versioniert bleiben. Voraussichtlich
werden nur Windows-API-Bindings und eine etablierte SHA-256-Implementierung
benötigt. `Cargo.lock` wird eingecheckt, damit der Updater reproduzierbar mit
denselben Abhängigkeitsversionen gebaut wird.

## 6. Update-Trigger und Ein-Instanz-Sperre

### 6.1 Windows-Mutex der QM-Anwendung

Die QM-Anwendung legt beim Start einen benannten Windows-Mutex an:

```text
Local\QMDesktop-Application
```

Der Mutex bleibt bis zum vollständigen Programmende belegt.

Beim Start einer zweiten Instanz gilt:

- existiert der Mutex bereits, wird keine zweite Hauptanwendung geöffnet;
- stattdessen erscheint ein Hinweis, dass QM bereits läuft;
- die zweite Instanz beendet sich kontrolliert.

### 6.2 Prüfung durch den Updater

Vor dem Dateivergleich und unmittelbar vor dem Austausch prüft der Updater:

- ist `Local\QMDesktop-Application` belegt?
- läuft zusätzlich ein Prozess mit dem erwarteten Installationspfad von `qm.exe`?

Ist eine Prüfung positiv, darf kein Update erfolgen. Der Updater zeigt eine
verständliche Meldung an und beendet sich. Die Prozessprüfung dient nur als
zweite Absicherung; der Mutex ist die maßgebliche Sperre.

### 6.3 Sperre mehrerer Updater

Der Updater verwendet zusätzlich:

```text
Local\QMDesktop-Updater
```

Dadurch können nicht zwei Updater gleichzeitig dieselbe Datei kopieren oder
ersetzen.

## 7. Ermittlung einer neueren Version

### 7.1 Zu verwendender Zeitstempel

Verglichen wird `LastWriteTimeUtc`, nicht `CreationTime`.

Begründung:

- das Erstellungsdatum ändert sich beim Kopieren häufig auf den lokalen
  Installationszeitpunkt;
- ein lokales Erstellungsdatum könnte dadurch neuer als die tatsächliche
  Netzversion wirken;
- das UTC-Änderungsdatum lässt sich nach dem Kopieren ausdrücklich übernehmen.

### 7.2 Vergleichsregel

Ein Update ist erforderlich, wenn:

- die lokale `qm.exe` fehlt; oder
- `Netzdatei.LastWriteTimeUtc` mindestens zwei Sekunden neuer als
  `LokaleDatei.LastWriteTimeUtc` ist.

Die Toleranz berücksichtigt unterschiedliche Zeitauflösungen von Dateisystemen.

Sind die Zeitstempel praktisch gleich, aber die Dateigrößen unterschiedlich,
wird zur Sicherheit SHA-256 verglichen. Bei unterschiedlichem Inhalt wird der
Vorgang protokolliert und das Update nur nach einer klar definierten Regel
durchgeführt. Empfohlen ist in diesem Sonderfall die Netzdatei als maßgeblich zu
behandeln, sofern sie stabil und vollständig veröffentlicht wurde.

### 7.3 Zeitstempel nach dem Update

Nach erfolgreichem Austausch setzt der Updater das lokale `LastWriteTimeUtc`
ausdrücklich auf den Wert der Netzdatei. Dadurch bleibt der nächste Vergleich
deterministisch.

## 8. Prüfung auf eine vollständig veröffentlichte Netzdatei

Vor dem Kopieren liest der Updater zweimal mit kurzem Abstand:

- Dateigröße;
- `LastWriteTimeUtc`.

Ändert sich einer der Werte, wird die Datei vermutlich noch veröffentlicht. Der
Updater wartet begrenzt oder bricht mit einer verständlichen Meldung ab und
startet die vorhandene lokale Version.

Zusätzlich gilt für die Veröffentlichung:

1. neue EXE unter `qm.exe.uploading` auf die Netzfreigabe kopieren;
2. Kopiervorgang vollständig abschließen;
3. finale Dateigröße kontrollieren;
4. erst danach atomar in `qm.exe` umbenennen.

Der Updater berücksichtigt ausschließlich `qm.exe` und ignoriert
`qm.exe.uploading`.

## 9. Lokales Staging und Integritätsprüfung

Eine neuere Netzdatei wird zunächst nach `qm.exe.new` kopiert. Die bestehende
`qm.exe` bleibt währenddessen unangetastet.

Anschließend prüft der Updater:

- lokale Staging-Datei existiert;
- Dateigröße entspricht der Netzdatei;
- SHA-256 der Staging-Datei entspricht SHA-256 der Netzdatei;
- Datei besitzt eine plausible PE-/EXE-Struktur;
- optional: Authenticode-Signatur und erwarteter Herausgeber stimmen.

Schlägt eine Prüfung fehl, wird `qm.exe.new` entfernt, die vorhandene lokale
Version bleibt bestehen und wird gestartet.

SHA-256 verhindert keine absichtliche Manipulation, wenn ein Angreifer die
Netzdatei kontrolliert. Dafür sind eingeschränkte Schreibrechte auf der
Freigabe und möglichst eine digitale Windows-Signatur erforderlich.

## 10. Atomarer Austausch und Rollback

Nach erfolgreicher Prüfung und erneuter Kontrolle des QM-Mutex:

1. eventuell vorhandene alte `qm.exe.old` entfernen, sofern sie nicht mehr für
   einen vorherigen Rollback benötigt wird;
2. lokale `qm.exe` nach `qm.exe.old` umbenennen;
3. `qm.exe.new` nach `qm.exe` umbenennen;
4. `LastWriteTimeUtc` der Netzdatei übernehmen;
5. neue lokale EXE auf Existenz, Größe und Lesbarkeit prüfen;
6. neue lokale Anwendung starten.

Kann Schritt 2 oder 3 nicht abgeschlossen werden:

- Austausch sofort abbrechen;
- `qm.exe.old` wieder als `qm.exe` herstellen;
- keine unvollständige neue Datei starten;
- Fehler protokollieren und anzeigen.

`qm.exe.old` wird nicht sofort nach dem Austausch gelöscht. Sie bleibt mindestens
bis zum nächsten erfolgreichen Updater-Start erhalten. So kann ein fehlgeschlagener
Start der neuen Version manuell oder künftig automatisiert zurückgerollt werden.

## 11. Start der Anwendung

Unabhängig davon, ob ein Update erforderlich war, startet der Updater nur die
neben ihm im gemeinsamen Installationsordner liegende Datei:

```text
<LOCAL_INSTALL_DIR>\qm.exe
```

Dabei wird der lokale Installationsordner als Arbeitsverzeichnis gesetzt.

Der Updater wartet nur so lange, bis der Prozess erfolgreich erzeugt wurde. Er
bleibt nicht während der gesamten Programmlaufzeit aktiv.

Mögliche spätere Erweiterung:

- `qm.exe` bestätigt über einen kurzen Startparameter oder eine lokale Markerdatei
  den erfolgreichen Start;
- fehlt diese Bestätigung, kann der nächste Updater-Lauf einen Rollback anbieten.

## 12. Verhalten bei Fehlern

### Netzfreigabe nicht erreichbar

- Fehler protokollieren;
- optional kurzer Hinweis an den Anwender;
- vorhandene lokale Version starten.

### Keine lokale Version vorhanden und Netzfreigabe nicht erreichbar

- verständliche Fehlermeldung anzeigen;
- kein Programmstart möglich;
- Updater beenden.

### QM läuft bereits

- kein Kopieren oder Ersetzen;
- Hinweis „QM ist bereits geöffnet. Bitte zunächst vollständig schließen.“;
- Updater beenden.

### Netzdatei wird gerade kopiert

- begrenzt erneut prüfen;
- bei weiterhin instabiler Datei lokale Version starten;
- kein Austausch.

### Prüfsumme oder Größe stimmt nicht

- Staging-Datei verwerfen;
- lokale Version starten;
- Fehler deutlich protokollieren.

### Austausch schlägt fehl

- alte Version wiederherstellen;
- keine unvollständige Datei starten;
- Fehlermeldung anzeigen.

### Neue Version startet nicht

- `qm.exe.old` erhalten;
- Fehler protokollieren;
- im ersten Umsetzungsschritt kein automatischer Rücktausch nach einem bloßen
  Prozessstartfehler; stattdessen klarer Wiederherstellungshinweis.

## 13. Virenscanner und SmartScreen

Es kann nicht garantiert werden, dass kein Virenscanner reagiert. Das Risiko wird
durch einen transparenten und stabilen Ablauf reduziert:

- Updater bleibt eine feste lokale Datei und wird nicht bei jedem Update ersetzt;
- keine PowerShell-, Batch- oder Skriptbefehle im Hintergrund;
- keine Ausführung direkt von der Netzfreigabe;
- feste Dateinamen und feste Installationspfade;
- UPX bleibt deaktiviert;
- neue EXE wird vor dem Start vollständig lokal kopiert und geprüft;
- Anwendung und Updater möglichst mit demselben vertrauenswürdigen
  Code-Signing-Zertifikat signieren;
- Pilotprüfung mit dem tatsächlich eingesetzten Virenscanner durchführen.

Besonders kritisch ist der aktuelle PyInstaller-Onefile-Build, weil er sich beim
Start temporär entpackt. Dies betrifft weiterhin `qm.exe`, nicht den nativen
Rust-Updater. Falls der eingesetzte Virenscanner auf die Hauptanwendung reagiert,
sollte als Alternative ein signierter `onedir`-Build in einem Installer geprüft
werden. Dies ist kein zwingender Bestandteil der ersten Updater-Version.

## 14. Protokollierung

Der Updater schreibt eine begrenzte lokale Protokolldatei, beispielsweise:

```text
<FESTER-WINDOWS-INSTALLATIONSPFAD>\logs\updater.log
```

Zu protokollieren sind:

- Startzeitpunkt;
- lokale und entfernte Pfade ohne Zugangsdaten;
- lokale und entfernte Änderungszeit;
- lokale und entfernte Dateigröße;
- Entscheidung „Update erforderlich“ oder „kein Update“;
- Ergebnis von Kopie, Prüfsumme, Austausch und Programmstart;
- Fehlerklasse und verständliche Fehlerbeschreibung.

Nicht protokolliert werden:

- Passwörter;
- Datenbankverbindungszeichenfolgen;
- Dokumentinhalte;
- personenbezogene QM-Daten.

Das Protokoll soll rotiert oder auf eine begrenzte Größe beschränkt werden.

## 15. Betroffene Projektdateien

### Neue Dateien

- `frontend/qm_app/windows_instance.py`
  - Windows-Mutex der Hauptanwendung;
  - unter Nicht-Windows-Systemen wirkungsloser Ersatz.
- `updater/Cargo.toml` und `updater/Cargo.lock`
  - Rust-Paket, feste Abhängigkeiten und reproduzierbare Auflösung.
- `updater/build.rs`
  - Windows-Programmsymbol und EXE-Metadaten einbetten;
  - vorhandenes `frontend/qm.ico` direkt verwenden.
- `updater/src/main.rs`
  - Programmablauf, Fehlermeldungen und Start der lokalen Anwendung.
- `updater/src/config.rs`
  - fester UNC-Quellpfad;
  - fester lokaler Installationspfad;
  - daraus abgeleitete Datei- und Protokollpfade.
- `updater/src/update.rs`
  - Datumsvergleich, Staging, Austausch und Rollback.
- `updater/src/windows_mutex.rs`
  - Windows-Mutex und Prüfung einer laufenden QM-Instanz.
- `updater/src/integrity.rs`
  - Dateigröße, SHA-256 und Plausibilitätsprüfung der EXE.
- `updater/src/logging.rs`
  - begrenztes lokales Updateprotokoll ohne sensible Daten.
- Testmodule in `updater/src/update.rs` und `updater/src/windows_mutex.rs`
  - isolierte Updatertests ohne echte Netzfreigabe.

### Anzupassende Dateien

- `frontend/main.py`
  - QM-Mutex unmittelbar nach Start anlegen;
  - zweite Instanz kontrolliert ablehnen.
- `build_tools/build.py`
  - Windows-Updater über `cargo build --release` separat bauen;
  - für `qm-updater.exe` dasselbe `frontend/qm.ico` wie für `qm.exe` verwenden;
  - Buildzeitpunkt der fertigen `qm.exe` kontrolliert festlegen;
  - Updater-Selbsttest ergänzen;
  - beide Artefakte im Buildbericht aufführen;
  - ein gemeinsames Windows-Ausgabeverzeichnis erzeugen, das unmittelbar
    `qm.exe` und `qm-updater.exe` enthält.
- `build_tools/smoke_test.py`
  - gebündelte Anwendung und Fensterstart offline prüfen;
  - Mutex-Verhalten wird separat durch pytest und Cargo geprüft.
- `bundle.bat`
  - Windows-Build von `qm.exe` und anschließend den Cargo-Release-Build von
    `qm-updater.exe` auslösen;
  - verständlich abbrechen, wenn Rust/Cargo nicht installiert ist.
- `requirements-build.txt`
  - bleibt auf Python-Buildwerkzeuge beschränkt; Rust-Abhängigkeiten werden
    ausschließlich über `updater/Cargo.toml` und `Cargo.lock` verwaltet.
- `BUILD.md`
  - Erzeugung, Veröffentlichung und Verteilung dokumentieren.
- `frontend/README.md`
  - Anwenderablauf „immer den Updater starten“ dokumentieren.
- `frontend/PRUEFUNG.md`
  - manuelle Windows-Prüfschritte aufnehmen.
- `TODO.md`
  - Code-Signierung und Pilotprüfung nachhalten.

Der macOS-Build darf den Updater nicht erzeugen und durch die Mutex-Ergänzung
nicht verändert werden.

Der Windows-Build gilt erst als erfolgreich, wenn beide Dateien gemeinsam im
Verteilungsverzeichnis liegen, der App-Selbsttest die gebündelte Anwendung
offline startet und der separate Updater-Selbsttest PE-Struktur sowie
SHA-256-Funktion der fertigen Updater-EXE bestätigt.

### Gemeinsames Icon

Es wird keine zweite Icondatei für den Updater gepflegt. `qm.exe` und
`qm-updater.exe` verwenden beide ausschließlich:

```text
frontend/qm.ico
```

Der Windows-Build übergibt diese Datei für `qm.exe` an PyInstaller. Das Rust-
`build.rs` bindet dieselbe Datei über die Windows-Ressourcen des Updaters ein;
es wird keine Iconkopie unter `updater/` gepflegt. Der Updater setzt
außerdem dieselbe Windows-AppUserModelID-Familie mit einer eigenen Unterkennung,
beispielsweise `de.steffentroeger.qm.updater`, damit Windows beide Dateien dem
QM-Produkt zuordnet, sie aber als getrennte Programme behandeln kann.

## 16. Automatisierte Tests

### Zeitvergleich

- lokale Datei fehlt;
- Netzdatei ist neuer;
- Dateien besitzen denselben Zeitstempel;
- Netzdatei ist älter;
- Zeitunterschied liegt innerhalb der Toleranz;
- gleicher Zeitstempel, aber unterschiedliche Größe beziehungsweise Inhalt.

### Laufende Anwendung

- QM-Mutex ist frei;
- QM-Mutex ist belegt;
- zweite Hauptanwendung wird abgelehnt;
- zweiter Updater wird abgelehnt;
- Prozess existiert trotz unerwartet freiem Mutex.

### Netzquelle

- Freigabe nicht erreichbar;
- Datei fehlt;
- Leserechte fehlen;
- Größe oder Zeitstempel ändern sich während der Stabilitätsprüfung;
- Quelle wird ordnungsgemäß über `.uploading` veröffentlicht.

### Integrität

- Kopie ist bytegleich;
- Dateigröße weicht ab;
- SHA-256 weicht ab;
- Staging-Datei ist nicht als EXE plausibel;
- optional Signatur fehlt oder Herausgeber stimmt nicht.

### Austausch und Rollback

- erfolgreiche Erstinstallation;
- erfolgreiches Update;
- Umbenennen der alten EXE schlägt fehl;
- Einsetzen der neuen EXE schlägt fehl;
- alte Version wird korrekt wiederhergestellt;
- `qm.exe.old` bleibt nach Erfolg erhalten;
- lokale Zeit wird auf die Netzzeit gesetzt.

### Start

- kein Update, lokale Anwendung startet;
- erfolgreiches Update, neue Anwendung startet;
- Netzfehler, lokale Anwendung startet;
- lokale und entfernte Anwendung fehlen;
- Prozessstart schlägt fehl;
- Updater wurde aus dem korrekten gemeinsamen Installationsordner gestartet;
- Updater wurde aus einem fremden Verzeichnis gestartet und lehnt die Ausführung ab;
- benachbarte `qm.exe` fehlt.

### Rust-spezifische Prüfung

- `cargo fmt --check` ist erfolgreich;
- `cargo clippy --all-targets -- -D warnings` ist erfolgreich;
- `cargo test` ist erfolgreich;
- Release-Build verwendet die eingecheckte `Cargo.lock`;
- fertige `qm-updater.exe` enthält das QM-Icon und startet ohne Rust-Installation.

## 17. Manuelle Windows-Abnahme

1. Updater bei fehlender lokaler `qm.exe` starten.
2. Updater ohne neue Netzversion starten.
3. Neuere EXE auf der Freigabe veröffentlichen und Update prüfen.
4. QM geöffnet lassen und Updater starten; Update muss abgelehnt werden.
5. Zwei Updater gleichzeitig starten; nur einer darf arbeiten.
6. Netzfreigabe vorübergehend trennen; lokale Anwendung muss starten.
7. Netzdatei während der Prüfung verändern; kein Austausch darf erfolgen.
8. Beschädigte Netzdatei bereitstellen; Hashprüfung muss abbrechen.
9. Schreibrechte im lokalen Verzeichnis entziehen; alte Version muss erhalten
   bleiben.
10. Austausch gezielt unterbrechen und Rollback prüfen.
11. Verhalten des eingesetzten Virenscanners und von SmartScreen kontrollieren.
12. Funktion auf einem Windows-Rechner ohne Python-Entwicklungsumgebung prüfen.
13. Beide EXE-Dateien gemeinsam in den endgültigen Installationsordner kopieren
    und Start über `qm-updater.exe` prüfen.
14. Nur den Updater in einen fremden Ordner kopieren; er muss Update und Start
    mit einem verständlichen Hinweis ablehnen.

## 18. Umsetzungsreihenfolge

1. Statischen lokalen Installationspfad und statischen UNC-Netzpfad verbindlich
   festlegen und in `updater/src/config.rs` eintragen.
2. Mutex für die QM-Hauptanwendung implementieren und testen.
3. Cargo-Projekt unter `updater/` anlegen und minimalen nativen Updater mit
   Prozessprüfung sowie Start der lokalen Anwendung erstellen.
4. Datumsvergleich über `LastWriteTimeUtc` ergänzen.
5. Stabilitätsprüfung der Netzdatei implementieren.
6. Lokales Staging und SHA-256-Prüfung ergänzen.
7. Atomaren Austausch und Rollback implementieren.
8. Cargo-Release-Build des Updaters in den Windows-Build integrieren.
9. Automatisierte Tests ergänzen.
10. Veröffentlichung über `.uploading` dokumentieren und erproben.
11. Virenscanner-Pilotprüfung durchführen.
12. Optional Code-Signierung ergänzen, bevor der Updater breit verteilt wird.

## 19. Abnahmekriterien

Die Umsetzung gilt als abgeschlossen, wenn:

- der Benutzer ausschließlich `qm-updater.exe` starten muss;
- `qm.exe` und `qm-updater.exe` unmittelbar im selben statischen
  Installationsordner liegen;
- der Updater einen Start aus einem anderen Verzeichnis ablehnt;
- bei gleicher oder älterer Netzdatei ohne Kopiervorgang die lokale Anwendung
  startet;
- eine neuere, stabile Netzdatei anhand `LastWriteTimeUtc` erkannt wird;
- die neue Datei zunächst lokal zwischengespeichert und per Größe sowie SHA-256
  geprüft wird;
- während einer laufenden QM-Instanz kein Austausch möglich ist;
- nicht zwei Updater gleichzeitig arbeiten können;
- ein fehlgeschlagenes Update die vorhandene lokale Version nicht beschädigt;
- nach erfolgreichem Update die neue lokale Anwendung startet;
- bei nicht erreichbarer Freigabe die vorhandene lokale Version nutzbar bleibt;
- macOS unverändert ohne Windows-Updater funktioniert;
- alle automatisierten Tests und die manuelle Windows-Abnahme erfolgreich sind.

## 20. Verbleibende Entscheidungen und Abnahmen

Die festen Pfade sind umgesetzt. Bei nicht erreichbarer oder noch instabiler
Netzquelle startet die vorhandene lokale Version; die Stabilitätsprüfung misst
zweimal mit 750 ms Abstand. `qm.exe.old` bleibt bis zum nächsten erfolgreichen
Austausch erhalten und wird dann durch die bisherige lokale Version ersetzt.

Noch offen sind:

- manuelle Abnahme mit der echten Netzfreigabe und den vorgesehenen Rechten;
- Zeitpunkt und Zertifikat für eine digitale Windows-Signierung;
- Pilotprüfung mit dem tatsächlich eingesetzten Virenscanner und SmartScreen;
- Verfahren zur späteren Aktualisierung des Updaters selbst;
- optional eine längere Wiederholungsstrategie, falls die Veröffentlichung über
  `.uploading` und atomare Umbenennung organisatorisch nicht zuverlässig erfolgt.

Die einfache Datumsentscheidung ist für eine kontrollierte interne Verteilung
vertretbar. Nicht verzichtet werden sollte auf Mutex, lokales Staging,
SHA-256-Prüfung und Rollback, da diese Maßnahmen unabhängig von der
Versionslogik vor beschädigten oder unvollständigen Updates schützen.
