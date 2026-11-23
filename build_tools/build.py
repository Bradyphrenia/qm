"""Shared implementation behind the two OS-specific entry scripts."""
import argparse
import ast
import importlib.machinery
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'frontend'
BUILD = ROOT / 'build'
STAGE = BUILD / 'compiled'


def run(command, **kwargs):
    print('+ ' + subprocess.list2cmdline([str(x) for x in command]), flush=True)
    subprocess.run([str(x) for x in command], check=True, **kwargs)


def source_modules():
    return {'.'.join(path.relative_to(FRONTEND).with_suffix('').parts): path
            for path in sorted((FRONTEND / 'qm_app').rglob('*.py'))
            if path.name != '__init__.py'}


def hidden_imports(modules):
    names = set(modules) | {"psycopg2.sql"}
    # Cython binaries hide their imports from PyInstaller's analysis. Read them
    # from the original source before packaging. Include stdlib imports as well.
    for path in [*modules.values(), FRONTEND / 'main.py', ROOT / 'build_tools/smoke_test.py']:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module)
    return sorted(names)


def smoke(command, directory):
    with tempfile.TemporaryDirectory(prefix='qm-build-check-') as tmp:
        marker = Path(tmp) / 'result.json'
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env['QT_QPA_PLATFORM'] = 'offscreen'
        env['QM_SMOKE_RESULT'] = str(marker)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        run(command, cwd=directory, env=env, timeout=120)
        if not marker.exists() or json.loads(marker.read_text()) != {'ok': True, 'windows': 6}:
            raise RuntimeError('Der Anwendungs-Selbsttest hat keinen erfolgreichen Abschluss gemeldet.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--platform', choices=['macos', 'windows'], required=True)
    parser.add_argument('--compile-only', action='store_true', help='Nur Cython plus Offline-Selbsttest')
    args = parser.parse_args()
    expected = 'darwin' if args.platform == 'macos' else 'win32'
    if sys.platform != expected:
        parser.error('Auf dem jeweiligen Zielbetriebssystem bauen; kein Cross-Compiler.')
    if struct.calcsize('P') != 8:
        parser.error('Bitte eine 64-Bit-Python-Umgebung verwenden.')
    os.chdir(ROOT)
    # Only disposable build staging is replaced, never frontend source files.
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    run([sys.executable, 'setup.py', 'build_ext', '--build-lib', STAGE,
         '--build-temp', BUILD / 'objects'])
    modules = source_modules()
    for name in modules:
        relative = Path(*name.split('.'))
        if not any((STAGE / (str(relative) + suffix)).is_file()
                   for suffix in importlib.machinery.EXTENSION_SUFFIXES):
            raise RuntimeError('Übersetztes Modul fehlt: ' + name)
    for path in (FRONTEND / 'qm_app').rglob('__init__.py'):
        dest = STAGE / path.relative_to(FRONTEND)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    shutil.copy2(FRONTEND / 'main.py', STAGE / 'main.py')
    shutil.copy2(FRONTEND / 'qm.ico', STAGE / 'qm.ico')
    for name in ('launcher.py', 'smoke_test.py'):
        shutil.copy2(ROOT / 'build_tools' / name, STAGE / name)
    smoke([sys.executable, STAGE / 'launcher.py', '--smoke-test'], STAGE)
    if args.compile_only:
        print('Cython-Module und Offline-Selbsttest erfolgreich: ' + str(STAGE))
        return
    specdir = BUILD / 'spec'
    specdir.mkdir(parents=True, exist_ok=True)
    icon = FRONTEND / 'qm.ico'
    if args.platform == 'macos' and (FRONTEND / 'qm.icns').is_file():
        icon = FRONTEND / 'qm.icns'
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--windowed', '--name', 'qm', '--noupx', '--paths', STAGE,
               '--distpath', ROOT / 'dist', '--workpath', BUILD / 'pyinstaller',
               '--specpath', specdir, '--exclude-module', 'tkinter',
               '--icon', icon,
               '--add-data', str(STAGE / 'qm.ico') + os.pathsep + '.']
    # A directory-backed .app is the robust macOS bundle format. Windows has a
    # single executable, matching the requested distribution format.
    command.append('--onedir' if args.platform == 'macos' else '--onefile')
    if args.platform == 'macos':
        command += ['--osx-bundle-identifier', 'de.steffentroeger.qm']
    for name in hidden_imports(modules):
        command += ['--hidden-import', name]
    command.append(STAGE / 'launcher.py')
    env = os.environ.copy()
    env["PYINSTALLER_CONFIG_DIR"] = str(BUILD / "pyinstaller-cache")
    run(command, cwd=STAGE, env=env)
    artifact = ROOT / 'dist' / ('qm.app/Contents/MacOS/qm' if args.platform == 'macos' else 'qm.exe')
    smoke([artifact, '--smoke-test'], ROOT / 'dist')
    report = {'python': sys.version, 'platform': sys.platform,
              'artifact': str(artifact), 'compiled_modules': sorted(modules),
              'compiled_smoke': 'passed', 'frozen_smoke': 'passed'}
    (BUILD / 'build-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (BUILD / 'requirements-resolved.txt').open('w', encoding='utf-8') as output:
        subprocess.run([sys.executable, '-m', 'pip', 'freeze'], stdout=output, check=True)
    print('Build und Offline-Selbsttest erfolgreich: ' + str(artifact))


if __name__ == '__main__':
    main()
