"""Tez Denetçi — ana pencere."""
import json
import os
import traceback
from PySide6.QtCore import Qt, QObject, QThread, Signal, QTimer, QSettings, QFileSystemWatcher, QMimeData, QUrl, QSize
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QIcon, QPixmap, QColor, QPainter, QDesktopServices, QFont
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, QLineEdit,
                               QCheckBox, QComboBox, QTextBrowser, QPushButton, QDockWidget, QFileDialog, QLabel,
                               QMessageBox, QApplication, QToolBar, QStyle, QSizePolicy, QMenu, QInputDialog,
                               QHeaderView, QDialog, QFormLayout, QDialogButtonBox, QColorDialog, QAbstractItemView)
from .. import __version__, APP_NAME, AUTHOR
from . import model as mdl
from .themes import THEMES, CUSTOM, DEFAULT_THEME, palette_for, colors_for, EDITABLE_ROLES, is_dark
from .about import AboutDialog, LicenseDialog, res
from . import wordlink
from .state import WorkState, item_key, finding_key, state_path_for
from ..engine import run_audit, finding_keys
from .model import build_items, detail
from .viewer import SourceViewer

LEVEL_COLORS = {'hata': '#b42318', 'uyari': '#c27c0e', 'oneri': '#2f5f8a', 'bilgi': '#8a8f96', 'ok': '#2e6b3f'}
GROUP_ORDER = ['Dipnotlar', 'Gövde', 'Kaynakça', 'Excel', 'Dosyalar', 'Genel']


def dot_icon(color):
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(1, 1, 10, 10)
    p.end()
    return QIcon(pm)


def check_icon():
    pm = QPixmap(12, 12)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    from PySide6.QtGui import QPen
    pen = QPen(QColor('#3f8f5a'))
    pen.setWidthF(2.2)
    p.setPen(pen)
    p.drawLine(2, 6, 5, 9)
    p.drawLine(5, 9, 10, 2)
    p.end()
    return QIcon(pm)


class AuditWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, docx, xlsx, folder):
        super().__init__()
        self.args = (docx, xlsx, folder)

    def run(self):
        try:
            A = run_audit(*self.args, progress=self.progress.emit)
            self.finished.emit(A)
        except Exception:
            self.failed.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f'{APP_NAME} — {AUTHOR}')
        self.setWindowIcon(QIcon(res('tezdenetci.ico')))
        self.resize(1500, 900)
        from .settings import make_settings, is_portable
        self.settings = make_settings()
        self.portable = is_portable()
        self.A = None
        self.items = []
        self.prev_keys = None
        self.current = None
        self.current_fixed = None
        self.current_style = 'dipnot'
        self._thread = None
        self.icons = {k: dot_icon(v) for k, v in LEVEL_COLORS.items()}
        self.icons['done'] = check_icon()
        self.wstate = WorkState()
        self.state_path = None
        self._state_timer = QTimer(self, singleShot=True, timeout=self.save_state)

        # ---------------- araç çubuğu
        tb = QToolBar('Ana')
        tb.setObjectName('toolbar')
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)
        st = self.style()
        self.act_docx = QAction(st.standardIcon(QStyle.SP_FileIcon), 'Tez (.docx)', self, triggered=self.pick_docx)
        self.act_xlsx = QAction(st.standardIcon(QStyle.SP_FileDialogDetailedView), 'Bilgiler Listesi (.xlsx)', self, triggered=self.pick_xlsx)
        self.act_dir = QAction(st.standardIcon(QStyle.SP_DirIcon), 'Kaynak klasörü', self, triggered=self.pick_dir)
        self.act_scan = QAction(st.standardIcon(QStyle.SP_BrowserReload), 'Tara', self, triggered=self.scan)
        self.act_scan.setShortcut(QKeySequence('F5'))
        self.act_watch = QAction('Otomatik izle', self, checkable=True, triggered=self._watch_toggled)
        self.act_watch.setToolTip('Tez ya da Excel kaydedildiğinde kendiliğinden yeniden tarar')
        self.act_copy = QAction(st.standardIcon(QStyle.SP_DialogApplyButton), 'Doğrusunu kopyala', self, triggered=self.copy_fixed)
        self.act_copy.setShortcut(QKeySequence('Ctrl+Shift+C'))
        self.act_word = QAction(st.standardIcon(QStyle.SP_ArrowForward), 'Word’de göster', self, triggered=lambda: self.goto_word('ref'))
        self.act_word.setShortcut(QKeySequence('Ctrl+Shift+W'))
        self.act_word.setToolTip('Açık Word belgesinde bu dipnotun metindeki numarasına ya da bu paragrafa git (Ctrl+Shift+W)')
        self.act_word_text = QAction('Dipnot metnine git', self, triggered=lambda: self.goto_word('text'))
        self.act_word_text.setToolTip('Word’de bu dipnotun sayfa altındaki metnine git')
        self.act_word.setEnabled(False)
        self.act_word_text.setEnabled(False)
        self.act_audit_layout = QAction('Bulgular', self, checkable=True, triggered=lambda: self.set_layout('denetim'))
        self.act_audit_layout.setShortcut(QKeySequence('F8'))
        self.act_audit_layout.setToolTip('Bulgular görünümü (F8): yalnızca hata, uyarı ya da öneri içeren kayıtlar; düzeltme çalışması için.')
        self.act_def_layout = QAction('Dipnot Atlası', self, checkable=True, triggered=lambda: self.set_layout('savunma'))
        self.act_def_layout.setShortcut(QKeySequence('F9'))
        self.act_def_layout.setToolTip('Dipnot Atlası görünümü (F9): hatalı ya da hatasız BÜTÜN dipnotların listesi.\n'
                                       'Bir dipnotun kaynağını numarasıyla anında açmak için — örneğin tez savunmasında\n'
                                       'jüri bir dipnotu sorduğunda. Ctrl+G ile numaraya gidilir.')
        lg = QActionGroup(self)
        lg.addAction(self.act_audit_layout)
        lg.addAction(self.act_def_layout)
        exp_menu = QMenu(self)
        exp_menu.addAction('HTML rapor…', self.export_html)
        exp_menu.addAction('Excel: dipnot listesi + Kaynak Kütüğü…', self.export_xlsx)
        exp_menu.addAction('Word: yeni kaynakça…', self.export_bib)
        self.act_export = QAction(st.standardIcon(QStyle.SP_DialogSaveButton), 'Dışa aktar', self)
        self.act_export.setMenu(exp_menu)
        self.act_export.triggered.connect(lambda: exp_menu.exec(self.cursor().pos()))
        for a in (self.act_docx, self.act_xlsx, self.act_dir):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.act_scan)
        tb.addAction(self.act_watch)
        tb.addSeparator()
        tb.addAction(self.act_copy)
        tb.addAction(self.act_word)
        tb.addAction(self.act_export)
        tb.addSeparator()
        tb.addAction(self.act_audit_layout)
        tb.addAction(self.act_def_layout)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.paths_lbl = QLabel('')
        self.paths_lbl.setStyleSheet('padding-right:8px')
        tb.addWidget(self.paths_lbl)

        # ---------------- sol: bulgular
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(4, 4, 4, 4)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Ara: yazar, başlık, kelime, dipnot no…  (Ctrl+F)')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda: self._filter_timer.start(200))
        ll.addWidget(self.search)
        row = QHBoxLayout()
        self.lv = {}
        for k, lbl in (('hata', 'Hata'), ('uyari', 'Uyarı'), ('oneri', 'Öneri'), ('bilgi', 'Bilgi')):
            cb = QCheckBox(lbl)
            cb.setChecked(k != 'bilgi')
            cb.setIcon(self.icons[k])
            cb.stateChanged.connect(self.refresh_tree)
            self.lv[k] = cb
            row.addWidget(cb)
        ll.addLayout(row)
        row2 = QHBoxLayout()
        self.cat = QComboBox()
        self.cat.addItem('Tüm kategoriler')
        self.cat.currentIndexChanged.connect(self.refresh_tree)
        row2.addWidget(self.cat, 1)
        self.clean = QCheckBox('Temiz dipnotlar')
        self.clean.setToolTip('Bulgu olmayan dipnotları da listele')
        self.clean.stateChanged.connect(self.refresh_tree)
        row2.addWidget(self.clean)
        self.show_done = QCheckBox('İncelenenler')
        self.show_done.setToolTip('İncelendi olarak işaretlediğiniz kayıtları da listele')
        self.show_done.stateChanged.connect(self.refresh_tree)
        row2.addWidget(self.show_done)
        ll.addLayout(row2)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.currentItemChanged.connect(self._selected)
        ll.addWidget(self.tree, 1)
        self._filter_timer = QTimer(self, singleShot=True, timeout=self.refresh_tree)
        dl = QDockWidget('Bulgular', self)
        dl.setObjectName('dock_findings')
        dl.setWidget(left)
        self.addDockWidget(Qt.LeftDockWidgetArea, dl)

        # ---------------- orta: ayrıntı
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(4, 4, 4, 4)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        cl.addWidget(self.detail, 1)
        brow = QHBoxLayout()
        self.copy_btn = QPushButton('Doğrusunu kopyala  (Ctrl+Shift+C)')
        self.copy_btn.clicked.connect(self.copy_fixed)
        self.copy_btn.setEnabled(False)
        brow.addWidget(self.copy_btn)
        self.word_btn = QPushButton('Word’de göster  (Ctrl+Shift+W)')
        self.word_btn.clicked.connect(lambda: self.goto_word('ref'))
        self.word_btn.setEnabled(False)
        brow.addWidget(self.word_btn)
        self.word_text_btn = QPushButton('Dipnot metnine git')
        self.word_text_btn.clicked.connect(lambda: self.goto_word('text'))
        self.word_text_btn.setEnabled(False)
        brow.addWidget(self.word_text_btn)
        self.review_btn = QPushButton('✓ İncelendi  (Ctrl+D)')
        self.review_btn.setCheckable(True)
        self.review_btn.setToolTip('Bu kaydı incelendi olarak işaretle ve sıradakine geç. Tekrar basınca işaret kalkar.')
        self.review_btn.clicked.connect(self.toggle_reviewed)
        self.review_btn.setEnabled(False)
        brow.addWidget(self.review_btn)
        self.copy_lbl = QLabel('')

        brow.addWidget(self.copy_lbl, 1)
        cl.addLayout(brow)
        self.setCentralWidget(center)

        # ---------------- sağ: kaynak
        self.viewer = SourceViewer()
        try:
            self.viewer.offsets = json.loads(self.settings.value('offsets', '{}'))
        except Exception:
            self.viewer.offsets = {}
        self.viewer.offsetChanged.connect(self._save_offset)
        dr = QDockWidget('Kaynak', self)
        dr.setObjectName('dock_source')
        dr.setWidget(self.viewer)
        self.addDockWidget(Qt.RightDockWidgetArea, dr)

        # ---------------- Dipnot Atlası (savunma çalışma alanı)
        atlas = QWidget()
        al = QVBoxLayout(atlas)
        al.setContentsMargins(4, 4, 4, 4)
        arow = QHBoxLayout()
        self.atlas_search = QLineEdit()
        self.atlas_search.setPlaceholderText('Dipnot no, yazar, eser, kelime…   (Ctrl+G: numaraya git)')
        self.atlas_search.setClearButtonEnabled(True)
        self.atlas_search.textChanged.connect(lambda: self._atlas_timer.start(200))
        arow.addWidget(self.atlas_search, 1)
        self.atlas_count = QLabel('')
        arow.addWidget(self.atlas_count)
        al.addLayout(arow)
        self.atlas = QTreeWidget()
        self.atlas.setColumnCount(5)
        self.atlas.setHeaderLabels(['No', 'Dipnot', 'Kaynak', 's.', 'Bölüm'])
        self.atlas.setRootIsDecorated(False)
        self.atlas.setUniformRowHeights(True)
        self.atlas.setAlternatingRowColors(True)
        self.atlas.setSelectionBehavior(QAbstractItemView.SelectRows)
        hh = self.atlas.header()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setStretchLastSection(False)
        self.atlas.currentItemChanged.connect(self._atlas_selected)
        al.addWidget(self.atlas, 1)
        self._atlas_timer = QTimer(self, singleShot=True, timeout=self.refresh_atlas)
        self.dock_atlas = QDockWidget('Dipnot Atlası', self)
        self.dock_atlas.setObjectName('dock_atlas')
        self.dock_atlas.setWidget(atlas)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock_atlas)
        self.tabifyDockWidget(dl, self.dock_atlas)
        dl.raise_()
        self.dock_findings = dl
        self.dock_source = dr
        self.resizeDocks([dl, dr], [420, 560], Qt.Horizontal)

        # ---------------- menüler
        m = self.menuBar().addMenu('&Dosya')
        for a in (self.act_docx, self.act_xlsx, self.act_dir):
            m.addAction(a)
        m.addSeparator()
        m.addMenu(exp_menu).setText('Dışa aktar')
        m.addSeparator()
        m.addAction('Çalışma durumunu dışa aktar…', self.export_state)
        m.addAction('Çalışma durumunu içe aktar…', self.import_state)
        m.addAction('Çalışma durumu dosyasının yerini göster', self.show_state_path)
        m.addSeparator()
        m.addAction('Çıkış', self.close)
        v = self.menuBar().addMenu('&Görünüm')
        v.addAction(self.act_audit_layout)
        v.addAction(self.act_def_layout)
        v.addSeparator()
        v.addAction(dl.toggleViewAction())
        v.addAction(self.dock_atlas.toggleViewAction())
        v.addAction(dr.toggleViewAction())
        v.addSeparator()
        tm = v.addMenu('Tema')
        self.theme_group = QActionGroup(self)
        for name in list(THEMES) + [CUSTOM]:
            a = QAction(name, self, checkable=True)
            a.triggered.connect(lambda _=False, n=name: self.apply_theme(n))
            self.theme_group.addAction(a)
            tm.addAction(a)
        tm.addSeparator()
        tm.addAction('Özel Temayı Düzenle…', self.edit_custom_theme)
        nxt = QAction('Sıradaki tema', self, shortcut=QKeySequence('Ctrl+T'), triggered=self.next_theme)
        tm.addAction(nxt)
        self.addAction(nxt)
        g = self.menuBar().addMenu('&Git')
        act_goto = QAction('Dipnot numarasına git…', self, shortcut=QKeySequence('Ctrl+G'), triggered=self.goto_number)
        g.addAction(act_goto)
        self.addAction(act_goto)
        self.act_review = QAction('İncelendi olarak işaretle / geri al', self, shortcut=QKeySequence('Ctrl+D'),
                                  triggered=lambda: self.toggle_reviewed(None))
        g.addAction(self.act_review)
        self.addAction(self.act_review)
        g.addAction(self.act_word)
        g.addAction(self.act_word_text)
        h = self.menuBar().addMenu('&Yardım')
        act_manual = QAction('Kullanım Kılavuzu', self, shortcut=QKeySequence('F1'), triggered=self.show_manual)
        h.addAction(act_manual)
        self.addAction(act_manual)
        h.addAction('Kısayollar', self.show_help)
        h.addSeparator()
        h.addAction('Lisans ve Bildirimler', lambda: LicenseDialog(self).exec())
        h.addAction(f'{APP_NAME} Hakkında', lambda: AboutDialog(self).exec())
        self.addAction(QAction(self, shortcut=QKeySequence('Ctrl+F'), triggered=lambda: (self.search.setFocus(), self.search.selectAll())))

        self.status = self.statusBar()
        credit = QLabel(f'{APP_NAME} {__version__} · © {AUTHOR}')
        self.credit_lbl = credit
        credit.setToolTip(f'{APP_NAME}, {AUTHOR} tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmıştır.')
        self.progress_lbl = QLabel('')
        self.status.addPermanentWidget(self.progress_lbl)
        self.status.addPermanentWidget(credit)
        # ---------------- izleme
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)
        self._rescan_timer = QTimer(self, singleShot=True, timeout=self._auto_rescan)

        # ---------------- ayarları geri yükle
        self.docx = self.settings.value('docx', '')
        self.xlsx = self.settings.value('xlsx', '')
        self.folder = self.settings.value('folder', '')
        g = self.settings.value('geometry')
        if g:
            self.restoreGeometry(g)
        s = self.settings.value('state')
        if s:
            self.restoreState(s)
        self.act_watch.setChecked(self.settings.value('watch', 'true') == 'true')
        self.load_state()
        try:
            self.custom_theme = (self.wstate.custom_theme or json.loads(self.settings.value('custom_theme', '') or 'null')
                                 or dict(THEMES[DEFAULT_THEME]))
        except Exception:
            self.custom_theme = dict(THEMES[DEFAULT_THEME])
        self.apply_theme(self.wstate.theme or self.settings.value('theme', DEFAULT_THEME), save=False)
        self.act_audit_layout.setChecked(True)
        self._update_paths()
        self.detail.setHtml(welcome_html())
        if self.docx and self.xlsx and os.path.exists(self.docx) and os.path.exists(self.xlsx):
            QTimer.singleShot(200, self.scan)

    # ------------------------------------------------------------------ dosya seçimi
    def pick_docx(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Tez dosyası', os.path.dirname(self.docx or ''), 'Word (*.docx)')
        if p:
            self.docx = p
            self.settings.setValue('docx', p)
            self.wstate = WorkState()
            self.load_state()
            self._update_paths()
            self.scan()

    def pick_xlsx(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Bilgiler listesi', os.path.dirname(self.xlsx or ''), 'Excel (*.xlsx *.xlsm)')
        if p:
            self.xlsx = p
            self.settings.setValue('xlsx', p)
            guess = os.path.join(os.path.dirname(p), 'Tüm Kaynaklar')
            if not self.folder and os.path.isdir(guess):
                self.folder = guess
                self.settings.setValue('folder', guess)
            self._update_paths()
            self.scan()

    def pick_dir(self):
        p = QFileDialog.getExistingDirectory(self, 'Kaynak klasörü (Tüm Kaynaklar)', self.folder or os.path.dirname(self.xlsx or ''))
        if p:
            self.folder = p
            self.settings.setValue('folder', p)
            self._update_paths()
            self.scan()

    def _update_paths(self):
        def b(p):
            return os.path.basename(p) if p else '—'
        self.paths_lbl.setText(f'Tez: {b(self.docx)}   ·   Liste: {b(self.xlsx)}   ·   Klasör: {b(self.folder)}')

    # ------------------------------------------------------------------ tarama
    def scan(self):
        if not (self.docx and self.xlsx):
            self.status.showMessage('Önce tez (.docx) ve bilgiler listesi (.xlsx) seçin.', 6000)
            return
        if self._thread is not None:
            return
        self.act_scan.setEnabled(False)
        self.status.showMessage('Taranıyor…')
        self._thread = QThread(self)
        self._worker = AuditWorker(self.docx, self.xlsx, self.folder or None)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(lambda m: self.status.showMessage(m))
        self._worker.finished.connect(self._scan_done)
        self._worker.failed.connect(self._scan_failed)
        self._thread.start()

    def _end_thread(self):
        self._thread.quit()
        self._thread.wait()
        self._thread = None
        self.act_scan.setEnabled(True)

    def _scan_failed(self, tb):
        self._end_thread()
        self.status.showMessage('Tarama başarısız', 8000)
        QMessageBox.warning(self, 'Tarama başarısız',
                            'Dosya okunamadı. Tez Word’de açıksa ve yeni kaydedildiyse birkaç saniye sonra tekrar deneyin.\n\n' + tb[-1500:])

    def _scan_done(self, A):
        self._end_thread()
        keys = finding_keys(A)
        diff_msg = ''
        if self.prev_keys is not None:
            new = len(keys - self.prev_keys)
            gone = len(self.prev_keys - keys)
            diff_msg = f' · önceki taramaya göre {new} yeni, {gone} giderilmiş bulgu'
        self.prev_keys = keys
        self.A = A
        self.items = build_items(A)
        if self.state_path:
            self.wstate.load(self.state_path)      # başka bilgisayarda yapılan işaretler
            self.viewer.offsets.update(self.wstate.offsets)
        for it in self.items:
            it.key = item_key(A, it)
            it.fkeys = [finding_key(it.key, f) for f in it.findings] or [it.key]
        cats = sorted({c for it in self.items for c in it.cats})
        cur = self.cat.currentText()
        self.cat.blockSignals(True)
        self.cat.clear()
        self.cat.addItem('Tüm kategoriler')
        self.cat.addItems(cats)
        i = self.cat.findText(cur)
        self.cat.setCurrentIndex(max(0, i))
        self.cat.blockSignals(False)
        prev_key = getattr(self.current, 'key', None) if self.current else self.wstate.last
        self.current = None
        self.refresh_tree()
        self.refresh_atlas()
        self._watch()
        self._restore(prev_key)
        self._update_progress()
        n_h = sum(1 for it in self.items for f in it.findings if f.level == 'hata')
        import time as _t
        try:
            saved = _t.strftime('%H:%M:%S', _t.localtime(os.path.getmtime(self.docx)))
        except OSError:
            saved = '?'
        self.status.showMessage(f'{_t.strftime("%H:%M:%S")} tarandı (tezin son kaydı {saved}) · {len(A.doc.footnotes)} dipnot · '
                                f'{len(A.sources)} kaynak · {n_h} hata · {A.elapsed:.1f} sn{diff_msg}')

    # ------------------------------------------------------------------ ağaç
    def refresh_tree(self):
        if not self.items:
            return
        term = self.search.text().strip().lower()
        levels = {k for k, cb in self.lv.items() if cb.isChecked()}
        cat = self.cat.currentText() if self.cat.currentIndex() > 0 else None
        keep_key = getattr(self.current, 'key', None) if self.current else None
        show_done = self.show_done.isChecked()
        self.tree.blockSignals(True)
        self.tree.clear()
        groups = {}
        reselect = None
        for it in self.items:
            fs = [f for f in it.findings if f.level in levels and (cat is None or f.cat == cat)]
            if not fs and not (it.kind == 'dipnot' and self.clean.isChecked() and not it.findings and cat is None):
                continue
            if term and term not in it.search and term not in it.title.lower():
                continue
            done = self.is_reviewed(it)
            if done and not show_done and getattr(it, 'key', None) != keep_key:
                continue
            g = groups.get(it.group)
            if g is None:
                g = QTreeWidgetItem([it.group])
                f = g.font(0)
                f.setBold(True)
                g.setFont(0, f)
                groups[it.group] = g
            lvl = min(fs, key=lambda f: ['hata', 'uyari', 'oneri', 'bilgi'].index(f.level)).level if fs else 'ok'
            label = it.title
            if it.kind == 'dipnot' and fs:
                label += '  —  ' + ', '.join(sorted({f.cat for f in fs}))
            ch = QTreeWidgetItem([('✓ ' if done else '') + label])
            ch.setIcon(0, self.icons['done'] if done else self.icons[lvl])
            if done:
                ch.setForeground(0, self.palette().color(self.palette().ColorGroup.Disabled, self.palette().ColorRole.Text))
            ch.setData(0, Qt.UserRole, it)
            ch.setToolTip(0, '\n'.join(f'{f.cat}: {f.msg}' for f in fs[:8]))
            g.addChild(ch)
            if keep_key and getattr(it, 'key', None) == keep_key:
                reselect = ch
        for name in GROUP_ORDER:
            if name in groups:
                g = groups[name]
                g.setText(0, f'{name}  ({g.childCount()})')
                self.tree.addTopLevelItem(g)
                g.setExpanded(name in ('Dipnotlar', 'Gövde', 'Dosyalar'))
        self.tree.blockSignals(False)
        if reselect:
            self.tree.setCurrentItem(reselect)

    def _selected(self, cur, prev):
        if cur is None:
            return
        it = cur.data(0, Qt.UserRole)
        if it is None:
            return
        self._show_item(it)

    def _show_item(self, it):
        same = it is getattr(self, '_last_shown', None)
        sb = self.detail.verticalScrollBar().value() if same else 0
        self.current = it
        html_, fixed, style = detail(self.A, it)
        self.current_fixed = fixed
        self.current_style = style
        self.detail.setHtml(html_)
        self.detail.verticalScrollBar().setValue(sb)
        self._last_shown = it
        if getattr(it, 'key', None):
            self.wstate.last = it.key
            self.wstate.touch()
            self._state_timer.start(1500)
        self.review_btn.setEnabled(True)
        self.review_btn.setChecked(self.is_reviewed(it))
        self.copy_btn.setEnabled(fixed is not None)
        self.act_copy.setEnabled(fixed is not None)
        word_ok = it.kind in ('dipnot', 'govde')
        self.word_btn.setEnabled(word_ok)
        self.act_word.setEnabled(word_ok)
        self.word_text_btn.setEnabled(it.kind == 'dipnot')
        self.act_word_text.setEnabled(it.kind == 'dipnot')
        self.copy_lbl.setText('')
        if it.sources and not same:
            self.viewer.show_sources(it.sources, self.A.source_paths)

    # ------------------------------------------------------------------ temalar
    def theme_colors(self, name):
        return self.custom_theme if name == CUSTOM else THEMES.get(name, THEMES[DEFAULT_THEME])

    def apply_theme(self, name, save=True):
        if name not in THEMES and name != CUSTOM:
            name = DEFAULT_THEME
        t = self.theme_colors(name)
        QApplication.instance().setPalette(palette_for(t))
        c = colors_for(t)
        mdl.set_colors(c)
        self.theme_c = c
        self.paths_lbl.setStyleSheet(f'color:{c["mute"]};padding-right:8px')
        self.credit_lbl.setStyleSheet(f'color:{c["mute"]}')
        self.copy_lbl.setStyleSheet(f'color:{c["ok"]}')
        self.viewer.set_colors(c)
        if self.current is None:
            self.detail.setHtml(welcome_html())
        self.theme_name = name
        for a in self.theme_group.actions():
            a.setChecked(a.text() == name)
        if save:
            self.settings.setValue('theme', name)
            self._state_timer.start(800)
        if self.current is not None and self.A is not None:
            self._show_item(self.current)

    def next_theme(self):
        names = list(THEMES) + [CUSTOM]
        cur = getattr(self, 'theme_name', DEFAULT_THEME)
        i = names.index(cur) if cur in names else 0
        self.apply_theme(names[(i + 1) % len(names)])
        self.status.showMessage(f'Tema: {self.theme_name}', 2500)

    def edit_custom_theme(self):
        d = QDialog(self)
        d.setWindowTitle('Özel Tema')
        form = QFormLayout(d)
        work = dict(self.custom_theme)
        btns = {}
        old = dict(self.custom_theme)
        prev_name = getattr(self, 'theme_name', DEFAULT_THEME)

        def paint(k):
            btns[k].setStyleSheet(f'background:{work[k]};min-width:90px;min-height:22px;border:1px solid #888')

        def pick(k):
            c = QColorDialog.getColor(QColor(work[k]), d, 'Renk seç')
            if c.isValid():
                work[k] = c.name()
                paint(k)
                self.custom_theme = dict(work)
                self.apply_theme(CUSTOM, save=False)
        for k, label in EDITABLE_ROLES:
            b = QPushButton('')
            b.clicked.connect(lambda _=False, k=k: pick(k))
            btns[k] = b
            paint(k)
            form.addRow(label, b)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        form.addRow(bb)
        if d.exec() == QDialog.Accepted:
            self.custom_theme = dict(work)
            self.settings.setValue('custom_theme', json.dumps(self.custom_theme))
            self.apply_theme(CUSTOM)
        else:
            self.custom_theme = old
            self.apply_theme(prev_name, save=False)

    # ------------------------------------------------------------------ düzenler
    def set_layout(self, mode):
        if mode == 'savunma':
            self.dock_atlas.show()
            self.dock_atlas.raise_()
            self.dock_source.show()
            self.resizeDocks([self.dock_atlas, self.dock_source], [int(self.width() * .42), int(self.width() * .36)], Qt.Horizontal)
            self.act_def_layout.setChecked(True)
            self.atlas_search.setFocus()
        else:
            self.dock_findings.show()
            self.dock_findings.raise_()
            self.act_audit_layout.setChecked(True)

    # ------------------------------------------------------------------ Dipnot Atlası
    def refresh_atlas(self):
        if self.A is None:
            return
        term = self.atlas_search.text().strip().lower()
        by_num = {it.ref: it for it in self.items if it.kind == 'dipnot'}
        cur = self.atlas.currentItem().data(0, Qt.UserRole) if self.atlas.currentItem() else None
        self.atlas.blockSignals(True)
        self.atlas.setUpdatesEnabled(False)
        self.atlas.clear()
        shown = 0
        reselect = None
        for fn in self.A.doc.footnotes:
            it = by_num.get(fn.num)
            srcs = it.sources if it else []
            src_txt = '; '.join((s.kisa.text or s.kay.text)[:60] for s, loc, form in srcs)
            pages = '; '.join(loc.replace('s. ', '') for s, loc, form in srcs if loc)
            if term:
                if term.isdigit():
                    if not str(fn.num).startswith(term):
                        continue
                elif term not in fn.rt.text.lower() and term not in src_txt.lower() and term not in fn.heading.lower():
                    continue
            row = QTreeWidgetItem([str(fn.num), fn.rt.text.strip(), src_txt, pages, fn.heading])
            row.setData(0, Qt.UserRole, fn.num)
            row.setTextAlignment(0, Qt.AlignRight | Qt.AlignVCenter)
            lvl = it.level if it else 'ok'
            row.setIcon(0, self.icons['done'] if (it and it.findings and self.is_reviewed(it)) else self.icons.get(lvl, self.icons['ok']))
            row.setToolTip(1, fn.rt.text.strip())
            if it and it.findings:
                row.setToolTip(0, '\n'.join(f'{f.cat}: {f.msg}' for f in it.findings[:8]))
            self.atlas.addTopLevelItem(row)
            shown += 1
            if cur == fn.num:
                reselect = row
        self.atlas.setUpdatesEnabled(True)
        self.atlas.blockSignals(False)
        self.atlas_count.setText(f'{shown} / {len(self.A.doc.footnotes)}')
        if reselect:
            self.atlas.setCurrentItem(reselect)

    def _atlas_selected(self, cur, prev):
        if cur is None or self.A is None:
            return
        num = cur.data(0, Qt.UserRole)
        it = next((x for x in self.items if x.kind == 'dipnot' and x.ref == num), None)
        if it:
            self._show_item(it)

    def goto_number(self):
        if self.A is None:
            return
        n, ok = QInputDialog.getInt(self, 'Dipnota git', 'Dipnot numarası:', 1, 1, max(1, len(self.A.doc.footnotes)))
        if ok:
            self.set_layout('savunma')
            self.atlas_search.blockSignals(True)
            self.atlas_search.clear()
            self.atlas_search.blockSignals(False)
            self.refresh_atlas()
            for i in range(self.atlas.topLevelItemCount()):
                r = self.atlas.topLevelItem(i)
                if r.data(0, Qt.UserRole) == n:
                    self.atlas.setCurrentItem(r)
                    self.atlas.scrollToItem(r, QAbstractItemView.PositionAtCenter)
                    break

    # ------------------------------------------------------------------ Word
    def goto_word(self, target='ref'):
        it = self.current
        if it is None or self.A is None or it.kind not in ('dipnot', 'govde'):
            return
        ok, msg = wordlink.available()
        if not ok:
            QMessageBox.information(self, 'Word bağlantısı', msg)
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if it.kind == 'dipnot':
                fn = self.A.doc.footnotes[it.ref - 1]
                adj, phys, note = wordlink.goto_footnote(self.docx, fn.num, fn.rt.text, target)
                what = f'{fn.num}. dipnot' + (' metni' if target == 'text' else '')
            else:
                p = self.A.doc.body[it.ref]
                a0 = min([a for f in it.findings for a, b in f.spans] or [0])
                stops = [pos for pos, n in p.fn_pos if pos > a0] + [len(p.rt.text)]
                snippet = p.rt.text[a0:min(stops)][:80]
                if len(snippet.strip()) < 12:
                    first = [pos for pos, n in p.fn_pos] + [len(p.rt.text)]
                    snippet = p.rt.text[:min(first)][:80]
                adj, phys, note = wordlink.goto_text(self.docx, snippet)
                what = f'Paragraf {it.ref + 1}'
            pg = ''
            if adj:
                pg = f' — Word’de {adj}. sayfa' + (f' (belgenin {phys}. sayfası)' if phys and phys != adj else '')
            self.status.showMessage(f'{what} Word’de seçildi{pg}. {note}', 10000)
        except wordlink.WordLinkError as e:
            QMessageBox.information(self, 'Word bağlantısı', str(e))
        except Exception as e:
            QMessageBox.warning(self, 'Word bağlantısı', f'Word’e ulaşılamadı: {e}')
        finally:
            QApplication.restoreOverrideCursor()

    # ------------------------------------------------------------------ kopyalama
    def copy_fixed(self):
        rt = self.current_fixed
        if rt is None:
            return
        from ..common import curly
        rt = curly(rt)
        font, pt = self.A.styles.get(self.current_style, ('Times New Roman', 12.0))
        body = rt.to_html()
        frag = f'<span style="font-family:\'{font}\';font-size:{pt:g}pt">{body}</span>'
        md = QMimeData()
        md.setHtml(f'<html><body><!--StartFragment-->{frag}<!--EndFragment--></body></html>')
        md.setText(rt.text)
        QApplication.clipboard().setMimeData(md)
        self.copy_lbl.setText(f'Kopyalandı ({font} {pt:g} pt, italikler korunarak) — Word’de Ctrl+V')

    # ------------------------------------------------------------------ izleme
    def _watch_toggled(self, on):
        self.settings.setValue('watch', 'true' if on else 'false')
        self._watch()

    def _watch(self):
        files = self.watcher.files()
        if files:
            self.watcher.removePaths(files)
        if self.act_watch.isChecked():
            for p in (self.docx, self.xlsx):
                if p and os.path.exists(p):
                    self.watcher.addPath(p)

    def _file_changed(self, path):
        # Word/Excel kaydederken dosyayı yeniden oluşturur; izlemeyi tazele
        QTimer.singleShot(500, self._watch)
        self.status.showMessage(f'{os.path.basename(path)} değişti, yeniden taranacak…')
        self._rescan_timer.start(2500)

    def _auto_rescan(self):
        if self._thread is None:
            self.scan()
        else:
            self._rescan_timer.start(2000)

    # ------------------------------------------------------------------ dışa aktarım
    def _need(self):
        if self.A is None:
            QMessageBox.information(self, 'Önce tarayın', 'Dışa aktarmadan önce bir tarama yapın.')
            return False
        return True

    def export_html(self):
        if not self._need():
            return
        p, _ = QFileSystemDialog(self, 'HTML rapor', 'Tez_Denetim_Raporu.html', 'HTML (*.html)')
        if p:
            from ..report import build_report
            meta = f'{os.path.basename(self.docx)} · {os.path.basename(self.xlsx)}'
            build_report(self.A, p, meta, self.A.styles)
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def export_xlsx(self):
        if not self._need():
            return
        p, _ = QFileSystemDialog(self, 'Excel', 'Kaynak_Kutugu.xlsx', 'Excel (*.xlsx)')
        if p:
            from ..export import export_xlsx
            export_xlsx(self.A, p)
            self.status.showMessage(f'Kaydedildi: {p}', 8000)

    def export_bib(self):
        if not self._need():
            return
        p, _ = QFileSystemDialog(self, 'Kaynakça', 'Kaynakca.docx', 'Word (*.docx)')
        if p:
            from ..kaynakca import export_docx
            export_docx(self.A.bibliography, self.docx, p)
            self.status.showMessage(f'Kaydedildi: {p}', 8000)

    # ------------------------------------------------------------------ çalışma durumu
    def is_reviewed(self, it):
        keys = getattr(it, 'fkeys', None)
        return bool(keys) and all(k in self.wstate.reviewed for k in keys)

    def toggle_reviewed(self, checked=None):
        it = self.current
        if it is None or not getattr(it, 'fkeys', None):
            return
        on = not self.is_reviewed(it)
        self.wstate.mark(it.fkeys, on)
        self.save_state()
        self._update_progress()
        if on:
            nxt = self._next_tree_item()
            self.refresh_tree()
            self.refresh_atlas()
            if nxt is not None:
                self._select_key(nxt)
        else:
            self.refresh_tree()
            self.refresh_atlas()
        self.review_btn.setChecked(self.is_reviewed(it) if self.current is it else False)

    def _next_tree_item(self):
        cur = self.tree.currentItem()
        if cur is None:
            return None
        below = self.tree.itemBelow(cur)
        while below is not None and below.data(0, Qt.UserRole) is None:
            below = self.tree.itemBelow(below)
        return getattr(below.data(0, Qt.UserRole), 'key', None) if below is not None else None

    def _select_key(self, key):
        for i in range(self.tree.topLevelItemCount()):
            g = self.tree.topLevelItem(i)
            for j in range(g.childCount()):
                c = g.child(j)
                if getattr(c.data(0, Qt.UserRole), 'key', None) == key:
                    self.tree.setCurrentItem(c)
                    self.tree.scrollToItem(c)
                    return True
        return False

    def _restore(self, key):
        if not key or not self.items:
            return
        if self._select_key(key):
            return
        it = next((x for x in self.items if getattr(x, 'key', None) == key), None)
        if it is not None:
            self._show_item(it)

    def _update_progress(self):
        if not self.items:
            self.progress_lbl.setText('')
            return
        with_f = [it for it in self.items if it.findings]
        done = sum(1 for it in with_f if self.is_reviewed(it))
        self.progress_lbl.setText(f'İncelenen: {done} / {len(with_f)} kayıt   ')

    def load_state(self):
        self.state_path = state_path_for(self.docx)
        if self.state_path and os.path.exists(self.state_path):
            self.wstate.load(self.state_path)
            self.viewer.offsets.update(self.wstate.offsets)
            if self.wstate.custom_theme:
                self.custom_theme = self.wstate.custom_theme

    def save_state(self):
        if not self.state_path:
            return
        self.wstate.offsets.update(self.viewer.offsets)
        self.wstate.theme = getattr(self, 'theme_name', None)
        self.wstate.custom_theme = getattr(self, 'custom_theme', None)
        if not self.wstate.save(self.state_path):
            self.status.showMessage('Çalışma durumu kaydedilemedi (klasör yazılamıyor olabilir).', 6000)

    def export_state(self):
        if not self.state_path:
            QMessageBox.information(self, 'Çalışma durumu', 'Önce tez dosyasını seçin.')
            return
        self.save_state()
        p, _ = QFileDialog.getSaveFileName(self, 'Çalışma durumunu dışa aktar',
                                           os.path.join(os.path.expanduser('~'), os.path.basename(self.state_path)),
                                           'Tez Denetçi durumu (*.tezdenetci.json *.json)')
        if p:
            import shutil
            shutil.copyfile(self.state_path, p)
            self.status.showMessage(f'Dışa aktarıldı: {p}', 8000)

    def import_state(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Çalışma durumunu içe aktar', os.path.expanduser('~'),
                                           'Tez Denetçi durumu (*.tezdenetci.json *.json)')
        if not p:
            return
        d = WorkState.read(p)
        if d is None:
            QMessageBox.warning(self, 'Çalışma durumu', 'Bu dosya bir Tez Denetçi çalışma durumu değil.')
            return
        before = len(self.wstate.reviewed)
        self.wstate.merge(d)
        self.viewer.offsets.update(self.wstate.offsets)
        self.save_state()
        self.refresh_tree()
        self.refresh_atlas()
        self._update_progress()
        self._restore(self.wstate.last)
        self.status.showMessage(f'İçe aktarıldı ({d.get("machine", "?")} bilgisayarından): '
                                f'{len(self.wstate.reviewed) - before} yeni işaret eklendi.', 10000)

    def show_state_path(self):
        QMessageBox.information(self, 'Çalışma durumu dosyası',
                                (self.state_path or '(tez seçilmedi)') +
                                '\n\nTez bir bulut klasöründeyse (Google Drive, OneDrive…) bu dosya da onunla birlikte '
                                'eşitlenir; öbür bilgisayarda kaldığınız yerden devam edersiniz. Elle taşımak için '
                                'Dosya › Çalışma durumunu dışa / içe aktar.')

    def _save_offset(self, key, val):
        self.settings.setValue('offsets', json.dumps(self.viewer.offsets, ensure_ascii=False))
        self._state_timer.start(800)

    def show_manual(self, anchor=None):
        from .manual import ManualDialog
        if getattr(self, '_manual', None) is None:
            self._manual = ManualDialog(self)
        self._manual.show()
        self._manual.raise_()
        if anchor:
            self._manual.go(anchor)

    def show_help(self):
        QMessageBox.information(self, 'Kullanım', HELP)

    def closeEvent(self, e):
        self.save_state()
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('state', self.saveState())
        super().closeEvent(e)


def QFileSystemDialog(parent, title, name, flt):
    start = os.path.join(os.path.dirname(parent.docx or os.path.expanduser('~')), name)
    return QFileDialog.getSaveFileName(parent, title, start, flt)


def welcome_html():
    from .. import APP_NAME, AUTHOR
    return mdl.CSS + f"""<div style="padding:16px">
<h2 style="font-family:Georgia">{APP_NAME}</h2>
<p class="cat"><i>{APP_NAME}, {AUTHOR} tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmıştır.</i></p>
<p>1. <b>Tez (.docx)</b>, <b>Bilgiler Listesi (.xlsx)</b> ve <b>Kaynak klasörü</b>nü seçin.<br>
2. <b>Tara</b> (F5). “Otomatik izle” açıkken Word’de her kaydedişte kendiliğinden yeniden tarar.<br>
3. Soldan bir bulgu seçin: ortada vurgulu metin ve olması gereken; sağda kaynak, atıf yapılan sayfada açılır.<br>
4. <b>Doğrusunu kopyala</b> (Ctrl+Shift+C) → Word’de Ctrl+V. Yazı tipi ve punto tezin kendi biçeminden alınır.<br>
5. <b>Word’de göster</b> (Ctrl+Shift+W) açık Word belgesinde ilgili dipnota gider.<br>
6. İncelediğiniz kaydı <b>Ctrl+D</b> ile işaretleyin; sıradakine geçilir.<br>
7. <b>Dipnot Atlası</b> (F9): bütün dipnotların listesi; tıklayınca kaynak ilgili sayfada açılır.</p>
<p class="cat">Ayrıntılı anlatım: <b>Yardım › Kullanım Kılavuzu</b> (F1). Uygulama metni değiştirmez; düzeltmeyi Word’de siz yaparsınız.</p></div>"""

HELP = '''F5 — Yeniden tara
Ctrl+F — Ara
Ctrl+G — Dipnot numarasına git
Ctrl+Shift+C — Seçili kaydın doğrusunu kopyala
Ctrl+Shift+W — Açık Word belgesinde ilgili dipnota / paragrafa git
F1 — Kullanım kılavuzu
F8 — Bulgular görünümü · F9 — Dipnot Atlası görünümü (bütün dipnotlar)
Ctrl+T — Sıradaki tema
Ctrl+D — İncelendi olarak işaretle ve sıradakine geç (tekrar basınca geri alır)
↑ / ↓ — Listede gezin

Kaynak panelinde “Basılı s.” dipnottaki sayfa numarasıdır. PDF sayfası = basılı sayfa − kayma.
Kayma makalenin sayfa aralığından ya da PDF’teki sayfa numaralarından tahmin edilir. Yanlışsa PDF’te doğru
sayfaya gelin, o sayfanın basılı numarasını “Basılı s.” kutusuna yazıp “Kaymayı buradan hesapla”ya basın;
o kaynak için hatırlanır. “PDF s.” PDF dosyasının kendi sayfa sırasıdır.

Panelleri sürükleyerek yerleştirebilir, başlıklarından çift tıklayıp ayrı pencereye alabilirsiniz.'''
