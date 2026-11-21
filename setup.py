"""Compile QM's application modules; generated files stay under build/."""
from pathlib import Path
from setuptools import Extension, find_packages, setup
from Cython.Build import cythonize

ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / 'frontend'
extensions = [
    Extension('.'.join(path.relative_to(SOURCES).with_suffix('').parts),
              [path.relative_to(ROOT).as_posix()])
    for path in sorted((SOURCES / 'qm_app').rglob('*.py'))
    if path.name != '__init__.py'
]

setup(
    name='qm-desktop', version='0.1.0', author='Steffen Troeger',
    description='QM Desktop', python_requires='>=3.10',
    package_dir={'': 'frontend'}, packages=find_packages('frontend'),
    ext_modules=cythonize(
        extensions, build_dir='build/cython',
        compiler_directives={'language_level': '3', 'binding': True,
                             'annotation_typing': False, 'always_allow_keywords': True},
    ),
)
