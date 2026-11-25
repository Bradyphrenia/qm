# QM mit Cython und PyInstaller bauen

Zwei getrennte Einstiegsskripte, analog zum Prothesen-Projekt:

- `bundle`: macOS → `dist/qm.app`
- `bundle.bat`: Windows 64-Bit → `dist/qm.exe` und `dist/qm-updater.exe`
  (beide ohne Konsolenfenster)

Beide verwenden `setup.py` für Cython und anschließend PyInstaller. Gemeinsame
Buildlogik liegt in `build_tools/build.py`; Änderungen an der Modulliste müssen
nicht in zwei langen Shellskripten dupliziert werden. Das Prothesen-Projekt wird
nicht verändert.

## macOS

Voraussetzungen: 64-Bit-Python und Xcode Command Line Tools (C-Compiler).
Falls der Compiler fehlt, einmal `xcode-select --install` ausführen.

Im QM-Projektordner:

```sh
python3 -m venv frontend/.venv  # nur falls noch nicht vorhanden
frontend/.venv/bin/python -m pip install -r requirements-build.txt
./bundle
open dist/qm.app
```

Das Skript verwendet bevorzugt `frontend/.venv/bin/python`, alternativ `python3`.
Ein anderer Interpreter kann über `QM_PYTHON=/absoluter/pfad/python ./bundle`
gewählt werden. Gebaut wird für die Architektur des verwendeten Interpreters.
Das komplette `.app`-Bundle weitergeben, nicht nur die Datei aus `Contents/MacOS`.

### App-Icon und Fehler „No module named 'PIL'“

Windows verwendet `frontend/qm.ico`. Für das macOS-Bundle erwartet PyInstaller
`.icns`: `build_tools/build.py` bevorzugt dort `frontend/qm.icns`, sofern diese
Datei vorhanden ist. Andernfalls wird `frontend/qm.ico` über Pillow automatisch
in `.icns` konvertiert. Eine bloße Umbenennung der Datei genügt nicht.
`frontend/qm.ico` bleibt auf beiden Plattformen als Qt-Laufzeitressource erforderlich.

Fehlt Pillow, scheitert diese Konvertierung beim Erstellen des macOS-Bundles mit
`ModuleNotFoundError: No module named 'PIL'` und anschließendem Formatfehler.
Das zu installierende Paket heißt **Pillow**, der Python-Import heißt `PIL`.
`requirements-build.txt` enthält deshalb `Pillow>=12; sys_platform == "darwin"`.
Die Frontend-/Testabhängigkeiten allein reichen für den Build nicht aus.

Für die vorhandene Python-3.14-Umgebung exakt denselben Interpreter zum
Installieren und Bauen verwenden; die Umgebung muss nicht neu erstellt werden:

```sh
cd /Users/steffen/IdeaProjects/qm
frontend/.venv/bin/python -m pip install -r requirements-build.txt
frontend/.venv/bin/python -c "import sys, PIL; print(sys.executable); print(PIL.__version__)"
frontend/.venv/bin/python build_tools/build.py --platform macos
```

Für die gezielte Reparatur genügt alternativ
`frontend/.venv/bin/python -m pip install 'Pillow>=12'` vor dem erneuten Build.
Für diesen Iconfehler ist kein Python-Downgrade erforderlich.

## Windows

Voraussetzungen: 64-Bit-Python, Rust/Cargo und passende Microsoft C++ Build Tools
mit C++-Werkzeugen und Windows SDK. Den Build bei Bedarf in einer **x64 Native
Tools Command Prompt** starten. Die Compilerwahl muss zur Python-Installation
passen. `rustc --version` und `cargo --version` müssen funktionieren.

In der Eingabeaufforderung im QM-Projektordner:

```bat
py -3 -m venv frontend\.venv
frontend\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
bundle.bat
```

Eine vorhandene Umgebung muss nicht erneut erstellt werden. `bundle.bat`
verwendet bevorzugt `frontend\.venv\Scripts\python.exe`, sonst `python` aus PATH.
Optional vorher `set "QM_PYTHON=C:\Pfad\python.exe"` setzen.
In PowerShell das Skript mit `.\bundle.bat` aufrufen.

Die Windows-EXEs müssen auf Windows gebaut werden. Eine macOS-Buildumgebung
erzeugt keine Windows-EXE. Ebenso muss ein Intel-/ARM-Build zur jeweiligen
Zielarchitektur passen. Python und Rust werden auf dem Zielrechner für die
fertigen Dateien nicht benötigt; PostgreSQL muss erreichbar sein.

Der Windows-Build führt zusätzlich `cargo fmt --check`, Clippy mit als Fehler
behandelten Warnungen, die Rust-Tests und den Release-Build mit gesperrter
`Cargo.lock` aus. Anschließend prüft `qm-updater.exe --self-test` PE-Struktur und
SHA-256-Funktion. Das Windows-SDK-Werkzeug `rc.exe` bindet direkt dasselbe
`frontend/qm.ico` ein, das auch die Hauptanwendung verwendet.

Die festen Updaterpfade stehen in `updater/src/config.rs`:

```text
Netzquelle: J:\EPZ\Daten OA Troeger\qm.exe
Lokaler Ordner: C:\Users\chir-arzt\Documents\qm
```

Für die Einrichtung beide Dateien aus `dist` unmittelbar in den lokalen Ordner
kopieren und die Verknüpfung ausschließlich auf `qm-updater.exe` setzen. Der
Updater lehnt einen normalen Start aus einem anderen Ordner ab; sein
`--self-test` bleibt davon unabhängig.

Eine neue Hauptanwendung wird zuerst als `qm.exe.uploading` auf das Netzlaufwerk
kopiert und erst nach vollständig beendeter Übertragung in `qm.exe` umbenannt.
Der Updater startet nie die Netzdatei direkt.

## Ablauf und Schutz des Quellcodes vor Build-Resten

1. `setup.py build_ext` übersetzt alle regulären `.py`-Module unter
   `frontend/qm_app/` zu nativen Erweiterungen (`.so` oder `.pyd`). Die kleinen
   Paketinitialisierungen und Startdateien bleiben Python.
2. Generiertes C und Objektdateien liegen unter `build/`. Das temporäre Verzeichnis
   `build/compiled/` wird bei jedem Build neu aufgebaut. Die Python-Quelldateien
   im Frontend werden nicht überschrieben; kein `--inplace` im normalen Build.
3. Ein Offline-Selbsttest lädt nachweislich binäre Module und erzeugt Hauptfenster,
   Login, Themen-, Sitzungs-, Maßnahmen- und TOP-Dialoge sowie die Dokumentenverwaltung.
   Zusätzlich prüft er offline die Umwandlung von Word-Vorlagen (.dotx → .docx)
   und dass die deutsche Qt-Übersetzung (`qtbase_de`) geladen ist. Fehlen die
   Übersetzungsdateien im Bundle, bricht der Build ab.
4. PyInstaller verpackt ausschließlich aus dem Staging-Verzeichnis. Die Imports
   der Cython-Module werden zuvor aus dem Quellcode ermittelt und als Hidden
   Imports übergeben. So bleiben etwa Qt, Dataclasses und psycopg2 erreichbar.
   Das QM-Icon wird zusätzlich als Laufzeitressource verpackt, von Qt als
   Anwendungsicon gesetzt und unter Windows mit einer festen AppUserModelID
   verbunden. Dadurch verwenden auch Fenster und Taskleiste das QM-Icon.
5. Das fertige Bundle wird erneut mit `--smoke-test` geprüft. Ein Fehler bricht
   den Build ab. Dieser Test benutzt keine Datenbank und keine Zugangsdaten.
6. Nur unter Windows wird der native Rust-Updater gebaut, getestet und als
   `dist/qm-updater.exe` neben `dist/qm.exe` abgelegt. Eine laufende App und ein
   zweiter Updater werden über benannte Windows-Sperren erkannt.

Nur Cython und den ersten Selbsttest ausführen:

```sh
./bundle --compile-only
```

Unter Windows: `bundle.bat --compile-only`.

Das vollständige Buildprotokoll der verwendeten Versionen liegt nach Erfolg in
`build/requirements-resolved.txt`, der Prüfbericht in `build/build-report.json`.
Die generierte PyInstaller-Spec liegt unter `build/spec/`. `build/` und `dist/`
sind Buildausgaben und gehören nicht in Git.

Cython wird mit deaktivierter Typableitung aus Annotationen verwendet, damit die
vorhandenen Python-Dataclasses und Qt-Schnittstellen ihre Semantik behalten.
Cython ist kein Ersatz für die Paketierung und keine Garantie gegen
Reverse Engineering. PyInstaller enthält weiterhin eine Python-Laufzeit.

## Abnahme und Verteilung

- Die sieben Offline-Fensterprüfungen ersetzen nicht die fachlichen Tests und
  keinen Test auf einem frischen Zielrechner. Die Datenbankabläufe weiterhin
  nach `frontend/PRUEFUNG.md` prüfen.
- macOS-Bundles werden hier ohne Developer-ID und Notarisierung gebaut.
  Für die Verteilung an andere Macs Signierung/Notarisierung separat vorsehen.
- Der Windows-Build ist geprüft. SmartScreen/Signierung und Start auf einem
  separaten Rechner ohne Entwicklungsumgebung müssen noch geprüft werden.
- Der Windows-Build verwendet das projektspezifische Icon `frontend/qm.ico`.
- `qm.exe.old` ist die letzte lokale Vorversion. Bei einem Austauschfehler wird
  sie automatisch zurückgespielt; nach einem erfolgreichen Update bleibt sie
  für eine manuelle Wiederherstellung erhalten.
- Beim Verteilen die Lizenzen der gebündelten Bibliotheken berücksichtigen.

## Hier verifizierter Stand

### Bisheriger vollständiger Build

macOS arm64, Python 3.14.10, Cython 3.3.1 und PyInstaller 6.22.3:
Cython-Übersetzung, Offline-Selbsttest der nativen Module und Offline-Selbsttest
des fertigen `qm.app` erfolgreich. Zusätzlich bestanden alle 36 vorhandenen
Tests mit den Cython-Modulen und PostgreSQL. Der Windows-Build wurde auf diesem
Mac nicht ausgeführt; `bundle.bat` muss auf Windows erprobt werden.

Der PyInstaller-Cache liegt ebenfalls unter `build/`, damit `--clean` keine
Caches anderer Projekte bereinigt.

### Iconkorrektur vom 23. November 2026

Pillow 13.0.0 wurde in `frontend/.venv` unter Python 3.14.10 installiert.
Die tatsächliche Datei `frontend/qm.ico` wurde mit PyInstallers
`normalize_icon_type` erfolgreich zu einer lesbaren ICNS-Datei (1024 × 1024)
konvertiert. Syntaxprüfung von `build_tools/build.py` und `git diff --check`
waren erfolgreich. Nach dieser Iconkorrektur wurde kein vollständiger
Anwendungsbuild erneut ausgeführt; die obigen Bundle-/Datenbankprüfungen
beschreiben den bisherigen Stand.

### Windows-Updater vom 24. November 2026

Der native Rust-Updater wurde unter Windows mit Rust 1.98.1 erstellt. Elf
Rust-Tests, `cargo fmt --check`, Clippy ohne Warnungen, der optimierte
Release-Build und der Selbsttest der fertigen EXE waren erfolgreich. Die
Frontend-Suite bestand anschließend mit 44 Tests gegen `qm_test`. Auch der
vollständige gemeinsame PyInstaller-/Updater-Build über `bundle.bat` war
erfolgreich; `dist/qm.exe` und `dist/qm-updater.exe` bestanden ihre Selbsttests
und zeigen dasselbe eingebettete QM-Symbol. Die manuelle Abnahme mit echter
Netzveröffentlichung steht noch aus.

## Referenzen

- [Cython: Compiler und Installation](https://docs.cython.org/en/latest/src/quickstart/install.html)
- [Cython: Python-Annotationen](https://docs.cython.org/en/latest/src/tutorial/pure.html)
- [PyInstaller: Cython und Hidden Imports](https://pyinstaller.org/en/stable/feature-notes.html)
- [PyInstaller: plattformspezifische Builds](https://pyinstaller.org/en/stable/usage.html)
