"""python -m tezdenetci.app"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon


def main():
    if sys.platform == 'win32':
        try:   # görev çubuğunda Python'un değil uygulamanın simgesi görünsün
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('BerkayCelik.TezDenetci')
        except Exception:
            pass
    app = QApplication(sys.argv)
    from .. import APP_NAME, AUTHOR, __version__
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(AUTHOR)
    app.setStyle('Fusion')
    app.setFont(QFont('Segoe UI', 9))
    from .about import res
    app.setWindowIcon(QIcon(res('tezdenetci.ico')))
    from .main_window import MainWindow
    w = MainWindow()
    w.show()
    if '--selftest' in sys.argv:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: _selftest(app, w))
    sys.exit(app.exec())


def _selftest(app, w):
    """Kurulum denetimi: TezDenetci.exe --selftest"""
    import os
    from .about import res, read_res
    from .settings import is_portable, app_dir
    from .manual import full_html
    from .. import __version__
    checks = {
        'sürüm': __version__,
        'simge': not QIcon(res('tezdenetci.ico')).isNull(),
        'lisans metinleri': all(len(read_res(n)) > 500 for n in ('NOTICE.txt', 'AGPL-3.0.txt', 'LGPL-3.0.txt', 'GPL-3.0.txt', 'THIRD_PARTY.txt')),
        'kılavuz': len(full_html()) > 10000,
        'taşınabilir kip': is_portable(),
        'program klasörü': app_dir(),
        'PDF modülü': _has_pdf(),
    }
    w.close()
    lines = [f'{k}: {v}' for k, v in checks.items()]
    out = os.path.join(app_dir(), 'selftest.txt') if is_portable() else None
    print('\n'.join(lines), flush=True)
    if out:
        try:
            with open(out, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(lines))
        except OSError:
            pass
    app.quit()


def _has_pdf():
    try:
        from PySide6.QtPdf import QPdfDocument  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == '__main__':
    main()
