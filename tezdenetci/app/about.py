"""Hakkında ve Lisans pencereleri."""
import platform
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
                               QPlainTextEdit, QDialogButtonBox)
import PySide6
from .. import __version__, APP_NAME, AUTHOR, EMAIL, YEARS, SOURCE_URL

RES = Path(__file__).resolve().parent.parent / 'resources'


def res(name):
    return str(RES / name)


def read_res(name):
    try:
        return (RES / name).read_text(encoding='utf-8')
    except Exception:
        return f'({name} bulunamadı)'


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{APP_NAME} Hakkında')
        self.setMinimumSize(620, 540)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        ic = QLabel()
        pm = QPixmap(res('tezdenetci.png'))
        if not pm.isNull():
            ic.setPixmap(pm.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        ic.setAlignment(Qt.AlignTop)
        top.addWidget(ic)
        txt = QLabel(f'''
<div style="font-size:11pt">
<div style="font-size:20pt;font-family:Georgia,serif;font-weight:bold">{APP_NAME}</div>
<div style="opacity:.75">Sürüm {__version__}</div>
<p style="margin-top:12px">Akademik çalışmalarda dipnot, kaynakça ve biçim tutarlılığını denetleyen;
hataları kaynağıyla birlikte gösterip doğrusunu öneren bir araçtır.</p>
<p><b>{APP_NAME}, {AUTHOR} tarafından akademik çalışmalara yardımcı olmak amacıyla
tasarlanmış ve geliştirilmiştir.</b></p>
<p>Copyright © {YEARS} {AUTHOR} &lt;<a href="mailto:{EMAIL}">{EMAIL}</a>&gt;</p>
<p>Bu program özgür yazılımdır ve <b>GNU Affero Genel Kamu Lisansı sürüm 3 ya da sonraki sürümleri</b>
(AGPL-3.0-or-later) ile NOTICE dosyasındaki ek koşullar kapsamında dağıtılır. Yazar atfı ve telif
bildirimleri kaldırılamaz. Program <b>hiçbir garanti olmaksızın</b> sunulur.</p>
<p>Kaynak kodu: <a href="{SOURCE_URL}">{SOURCE_URL}</a></p>
<p style="opacity:.7;font-size:9pt">Program belgelerinizi yalnızca okur; hiçbir dosyayı değiştirmez ve internete bağlanmaz.<br>
Python {platform.python_version()} · PySide6 {PySide6.__version__} · Qt {PySide6.QtCore.qVersion()}</p>
</div>''')
        txt.setWordWrap(True)
        txt.setOpenExternalLinks(True)
        txt.setTextInteractionFlags(Qt.TextBrowserInteraction)
        txt.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        top.addWidget(txt, 1, Qt.AlignTop)
        lay.addLayout(top)
        row = QHBoxLayout()
        b = QPushButton('Lisans ve Bildirimler')
        b.clicked.connect(lambda: LicenseDialog(self).exec())
        row.addWidget(b)
        row.addStretch(1)
        ok = QPushButton('Kapat')
        ok.setDefault(True)
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)


class LicenseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Lisans ve Bildirimler')
        self.resize(760, 620)
        lay = QVBoxLayout(self)
        tabs = QTabWidget()
        for title, name in (('Bildirim ve ek koşullar', 'NOTICE.txt'), ('AGPL-3.0', 'AGPL-3.0.txt'),
                            ('Üçüncü taraf bileşenler', 'THIRD_PARTY.txt'), ('LGPL-3.0 (Qt)', 'LGPL-3.0.txt'),
                            ('GPL-3.0', 'GPL-3.0.txt')):
            e = QPlainTextEdit(read_res(name))
            e.setReadOnly(True)
            f = e.font()
            f.setFamily('Consolas')
            e.setFont(f)
            tabs.addTab(e, title)
        lay.addWidget(tabs)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
