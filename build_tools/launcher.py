"""Small, uncompiled boot entry so PyInstaller can discover basic dependencies."""
import sys
from main import main

if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        from smoke_test import run
        run()
    else:
        sys.exit(main())
