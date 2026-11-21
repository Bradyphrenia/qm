# QM mit Cython und PyInstaller bauen

Zwei getrennte Einstiegsskripte, analog zum Prothesen-Projekt:

- `bundle`: macOS → `dist/qm.app`
- `bundle.bat`: Windows 64-Bit → `dist/qm.exe` (Onefile, ohne Konsolenfenster)

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

## Windows

Voraussetzungen: 64-Bit-Python und passende Microsoft C++ Build Tools mit
C++-Werkzeugen und Windows SDK. Den Build bei Bedarf in einer **x64 Native Tools
Command Prompt** starten. Die Compilerwahl muss zur Python-Installation passen.

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

Die Windows-EXE muss auf Windows gebaut werden. Eine macOS-Buildumgebung erzeugt
keine Windows-EXE. Ebenso muss ein Intel-/ARM-Build zur jeweiligen Zielarchitektur
passen. Eine Python-Installation wird auf dem Zielrechner für das fertige Bundle
nicht benötigt; PostgreSQL wird nicht mitgeliefert und muss erreichbar sein.

## Ablauf und Schutz des Quellcodes vor Build-Resten

1. `setup.py build_ext` übersetzt alle regulären `.py`-Module unter
   `frontend/qm_app/` zu nativen Erweiterungen (`.so` oder `.pyd`). Die kleinen
   Paketinitialisierungen und Startdateien bleiben Python.
2. Generiertes C und Objektdateien liegen unter `build/`. Das temporäre Verzeichnis
   `build/compiled/` wird bei jedem Build neu aufgebaut. Die Python-Quelldateien
   im Frontend werden nicht überschrieben; kein `--inplace` im normalen Build.
3. Ein Offline-Selbsttest lädt nachweislich binäre Module und erzeugt Hauptfenster,
   Login sowie Themen-, Sitzungs-, Maßnahmen- und TOP-Dialoge.
4. PyInstaller verpackt ausschließlich aus dem Staging-Verzeichnis. Die Imports
   der Cython-Module werden zuvor aus dem Quellcode ermittelt und als Hidden
   Imports übergeben. So bleiben etwa Qt, Dataclasses und psycopg2 erreichbar.
5. Das fertige Bundle wird erneut mit `--smoke-test` geprüft. Ein Fehler bricht
   den Build ab. Dieser Test benutzt keine Datenbank und keine Zugangsdaten.

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

- Die sechs Offline-Fensterprüfungen ersetzen nicht die fachlichen Tests und
  keinen Test auf einem frischen Zielrechner. Die Datenbankabläufe weiterhin
  nach `frontend/PRUEFUNG.md` prüfen.
- macOS-Bundles werden hier ohne Developer-ID und Notarisierung gebaut.
  Für die Verteilung an andere Macs Signierung/Notarisierung separat vorsehen.
- Windows-Build, SmartScreen/Signierung und Start auf einem Rechner ohne
  Entwicklungsumgebung müssen auf Windows geprüft werden.
- Ein eigenes Icon ist noch nicht festgelegt. Das fremde Prothesen-Icon wird
  deshalb nicht übernommen.
- Beim Verteilen die Lizenzen der gebündelten Bibliotheken berücksichtigen.

## Hier verifizierter Stand

macOS arm64, Python 3.14.10, Cython 3.3.1 und PyInstaller 6.22.3:
Cython-Übersetzung, Offline-Selbsttest der nativen Module und Offline-Selbsttest
des fertigen `qm.app` erfolgreich. Zusätzlich bestanden alle 36 vorhandenen
Tests mit den Cython-Modulen und PostgreSQL. Der Windows-Build wurde auf diesem
Mac nicht ausgeführt; `bundle.bat` muss auf Windows erprobt werden.

Der PyInstaller-Cache liegt ebenfalls unter `build/`, damit `--clean` keine
Caches anderer Projekte bereinigt.

## Referenzen

- [Cython: Compiler und Installation](https://docs.cython.org/en/latest/src/quickstart/install.html)
- [Cython: Python-Annotationen](https://docs.cython.org/en/latest/src/tutorial/pure.html)
- [PyInstaller: Cython und Hidden Imports](https://pyinstaller.org/en/stable/feature-notes.html)
- [PyInstaller: plattformspezifische Builds](https://pyinstaller.org/en/stable/usage.html)
