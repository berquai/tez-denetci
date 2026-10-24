"""Ayar deposu. Programın yanında 'TASINABILIR.txt' varsa ayarlar program klasörüne yazılır (taşınabilir kip);
yoksa Windows'un kullanıcı ayarlarına (kayıt defteri) yazılır."""
import os
import sys
from PySide6.QtCore import QSettings

MARKER = 'TASINABILIR.txt'


def app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def is_portable():
    return os.path.exists(os.path.join(app_dir(), MARKER))


def make_settings():
    if is_portable():
        return QSettings(os.path.join(app_dir(), 'ayarlar.ini'), QSettings.IniFormat)
    return QSettings('TezDenetci', 'TezDenetci')
