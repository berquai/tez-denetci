"""Kaynak görüntüleyici: PDF (atıf sayfasında), Word, Excel, resim ve metin."""
import os
import html
from PySide6.QtCore import Qt, QPointF, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QToolButton, QComboBox,
                               QStackedWidget, QTextBrowser, QTableWidget, QTableWidgetItem, QScrollArea, QSizePolicy)
from PySide6.QtPdf import QPdfDocument, QPdfSearchModel
from PySide6.QtPdfWidgets import QPdfView
from ..files_audit import first_page, guess_offset


class SourceViewer(QWidget):
    offsetChanged = Signal(str, int)   # dosya yolu, kayma

    def __init__(self, parent=None):
        super().__init__(parent)
        self.offsets = {}
        self._path = None
        self._src = None
        self._page_text_cache = {}
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel('Bir dipnot ya da kaynak seçin')
        self.title.setWordWrap(True)
        self.title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.title)
        bar = QHBoxLayout()
        self.cits = QComboBox()
        self.cits.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.cits.setMinimumContentsLength(18)
        self.cits.currentIndexChanged.connect(self._cit_changed)
        self.cits.setVisible(False)
        bar.addWidget(self.cits, 1)
        bar.addWidget(QLabel('Basılı s.'))
        self.page = QSpinBox()
        self.page.setRange(-5000, 99999)
        self.page.setToolTip('Kaynağın basılı sayfa numarası (dipnottaki s. değeri)')
        self.page.editingFinished.connect(self._goto)
        bar.addWidget(self.page)
        bar.addWidget(QLabel('Kayma'))
        self.offset = QSpinBox()
        self.offset.setRange(-5000, 5000)
        self.offset.setToolTip('PDF sayfası = basılı sayfa − kayma. Doğru sayfayı bulunca bu kaynak için hatırlanır.')
        self.offset.editingFinished.connect(self._offset_edited)
        bar.addWidget(self.offset)
        for txt, tip, fn in (('−', 'Uzaklaş', lambda: self._zoom(1 / 1.2)), ('+', 'Yakınlaş', lambda: self._zoom(1.2)),
                             ('↔', 'Sayfa genişliğine sığdır', self._fitw), ('↗', 'Dosyayı kendi programında aç', self._external)):
            b = QToolButton()
            b.setText(txt)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            bar.addWidget(b)
        lay.addLayout(bar)
        bar2 = QHBoxLayout()
        bar2.addWidget(QLabel('PDF s.'))
        self.pdfpage = QSpinBox()
        self.pdfpage.setRange(1, 99999)
        self.pdfpage.setToolTip('PDF dosyasının kendi sayfa sırası')
        self.pdfpage.editingFinished.connect(self._goto_pdf)
        bar2.addWidget(self.pdfpage)
        self.pdfinfo = QLabel('')
        self.pdfinfo.setStyleSheet('font-weight:bold')
        bar2.addWidget(self.pdfinfo)
        bar2.addStretch(1)
        self.calib = QToolButton()
        self.calib.setText('Kaymayı buradan hesapla')
        self.calib.setToolTip('Şu an görünen PDF sayfasının basılı numarasını “Basılı s.” kutusuna yazıp tıklayın;\n'
                              'kayma hesaplanır ve bu kaynak için kaydedilir.')
        self.calib.clicked.connect(self._calibrate)
        bar2.addWidget(self.calib)
        lay.addLayout(bar2)
        self.info = QLabel('')

        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self.stack = QStackedWidget()
        self.pdf = QPdfDocument(self)
        self.pdfview = QPdfView()
        self.pdfview.setDocument(self.pdf)
        self.pdfview.setPageMode(QPdfView.PageMode.MultiPage)
        self.pdfview.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdfview.pageNavigator().currentPageChanged.connect(self._page_changed)
        self.search = QPdfSearchModel(self)
        self.search.setDocument(self.pdf)
        self.pdfview.setSearchModel(self.search)
        self.text = QTextBrowser()
        self.table = QTableWidget()
        self.img = QLabel()
        self.img.setAlignment(Qt.AlignCenter)
        sc = QScrollArea()
        sc.setWidget(self.img)
        sc.setWidgetResizable(True)
        self.msg = QLabel('')
        self.msg.setAlignment(Qt.AlignCenter)
        self.msg.setWordWrap(True)
        for w in (self.pdfview, self.text, self.table, sc, self.msg):
            self.stack.addWidget(w)
        self._img_scroll = sc
        lay.addWidget(self.stack, 1)
        self.stack.setCurrentWidget(self.msg)

    # ------------------------------------------------------------------
    def show_sources(self, entries, paths):
        """entries: [(Source, loc, form)], paths: {sid: dosya yolu}"""
        self._entries = entries
        self._paths = paths
        self.cits.blockSignals(True)
        self.cits.clear()
        for s, loc, form in entries:
            self.cits.addItem(f'{s.sid} · {(s.kisa.text or s.kay.text)[:60]}' + (f' · {loc}' if loc else ''))
        self.cits.blockSignals(False)
        self.cits.setVisible(len(entries) > 1)
        if entries:
            self._cit_changed(0)
        else:
            self._message('Bu kayıtta görüntülenecek kaynak yok.')

    def _cit_changed(self, i):
        if i < 0 or i >= len(getattr(self, '_entries', [])):
            return
        s, loc, form = self._entries[i]
        self._src = s
        path = self._paths.get(s.sid)
        self.title.setText(f'<b>{html.escape(s.kisa.text or s.kay.text)}</b>')
        if not path:
            self._path = None
            self._message('Dosya bulunamadı.\n\nKaynak klasörünü seçtiğinizden emin olun; '
                          'köprü kırıksa “Dosyalar” grubunda listelenir.\n\n' + (s.dosya or ''))
            self.info.setText('')
            return
        self.open_path(path, first_page(loc), s.page_range)

    def open_path(self, path, printed=None, page_range=None):
        ext = os.path.splitext(path)[1].lower()
        self.info.setText(os.path.basename(path))
        self._pdf_controls(ext == '.pdf')
        if ext == '.pdf':
            if path != self._path:
                self.pdf.close()
                self.pdf.load(path)
            self._path = path
            self.stack.setCurrentWidget(self.pdfview)
            off = self.offsets.get(self._key(path))
            how = 'kayıtlı'
            if off is None:
                texts = self._texts(path)
                off, how = guess_offset(self.pdf.pageCount(), texts, page_range)
            self.offset.setValue(off)
            self.page.setValue(printed if printed else 1 + off)
            note = {'kayıtlı': 'kayma bu kaynak için kaydedilmiş', 'aralık': 'kayma makalenin sayfa aralığından tahmin edildi',
                    'metin': 'kayma sayfa numaralarından tahmin edildi', 'yok': 'kayma tahmin edilemedi (taranmış PDF olabilir) — doğru sayfayı bulup “Kayma”yı düzeltin'}[how]
            self.info.setText(f'{os.path.basename(path)} · {self.pdf.pageCount()} sayfa · {note}')
            self._goto()
            self._page_changed(self.pdfview.pageNavigator().currentPage())
        elif ext == '.docx':
            self._path = path
            self.text.setHtml(_docx_html(path))
            self.stack.setCurrentWidget(self.text)
        elif ext in ('.xlsx', '.xlsm'):
            self._path = path
            _fill_table(self.table, path)
            self.stack.setCurrentWidget(self.table)
        elif ext in ('.jpg', '.jpeg', '.png', '.tif', '.tiff'):
            self._path = path
            self.img.setPixmap(QPixmap(path))
            self.stack.setCurrentWidget(self._img_scroll)
        elif ext in ('.txt', '.htm', '.html'):
            self._path = path
            with open(path, encoding='utf-8', errors='replace') as fh:
                data = fh.read()
            (self.text.setHtml if ext != '.txt' else self.text.setPlainText)(data)
            self.stack.setCurrentWidget(self.text)
        else:
            self._path = path
            self._message(f'{os.path.basename(path)}\n\nBu dosya türü burada önizlenemiyor; ↗ düğmesiyle açın.')

    def _texts(self, path):
        if path in self._page_text_cache:
            return self._page_text_cache[path]
        texts = []
        n = min(self.pdf.pageCount(), 40)
        for i in range(n):
            try:
                texts.append(self.pdf.getAllText(i).text())
            except Exception:
                texts.append('')
        self._page_text_cache[path] = texts
        return texts

    def _goto(self):
        if self.stack.currentWidget() is not self.pdfview or self.pdf.pageCount() == 0:
            return
        idx = self.page.value() - self.offset.value() - 1
        idx = max(0, min(self.pdf.pageCount() - 1, idx))
        self.pdfview.pageNavigator().jump(idx, QPointF(0, 0), self.pdfview.zoomFactor())

    def _page_changed(self, idx):
        n = self.pdf.pageCount()
        if n <= 0:
            self.pdfinfo.setText('')
            return
        label = ''
        try:
            label = self.pdf.pageLabel(idx)
        except Exception:
            pass
        printed = idx + 1 + self.offset.value()
        txt = f'{idx + 1} / {n}   ·   basılı ≈ {printed}'
        if label and label != str(idx + 1):
            txt += f'   ·   PDF etiketi: {label}'
        self.pdfinfo.setText(txt)
        self.pdfpage.blockSignals(True)
        self.pdfpage.setMaximum(max(1, n))
        self.pdfpage.setValue(idx + 1)
        self.pdfpage.blockSignals(False)

    def _goto_pdf(self):
        if self.pdf.pageCount() == 0:
            return
        idx = max(0, min(self.pdf.pageCount() - 1, self.pdfpage.value() - 1))
        self.pdfview.pageNavigator().jump(idx, QPointF(0, 0), self.pdfview.zoomFactor())

    def _calibrate(self):
        if self.pdf.pageCount() == 0 or not self._path:
            return
        cur = self.pdfview.pageNavigator().currentPage() + 1
        self.offset.setValue(self.page.value() - cur)
        self._offset_edited()
        self.info.setText(f'{os.path.basename(self._path)} · kayma {self.offset.value()} olarak kaydedildi '
                          f'(PDF s. {cur} = basılı s. {self.page.value()})')

    def _offset_edited(self):
        if self._path:
            self.offsets[self._key(self._path)] = self.offset.value()
            self.offsetChanged.emit(self._key(self._path), self.offset.value())
        self._goto()

    @staticmethod
    def _key(path):
        return os.path.basename(path).lower()

    def _zoom(self, f):
        self.pdfview.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdfview.setZoomFactor(self.pdfview.zoomFactor() * f)

    def _fitw(self):
        self.pdfview.setZoomMode(QPdfView.ZoomMode.FitToWidth)

    def _external(self):
        if self._path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))

    def set_colors(self, c):
        self.info.setStyleSheet(f'color:{c["mute"]}')

    def _pdf_controls(self, on):
        for w in (self.page, self.offset, self.pdfpage, self.calib, self.pdfinfo):
            w.setEnabled(on)
        if not on:
            self.pdfinfo.setText('')

    def _message(self, text):
        self._pdf_controls(False)
        self.msg.setText(text)
        self.stack.setCurrentWidget(self.msg)

    def find_text(self, text):
        if self.stack.currentWidget() is self.pdfview:
            self.search.setSearchString(text)


def _docx_html(path):
    try:
        from docx import Document
        d = Document(path)
        out = ['<div style="font-family:Times New Roman;font-size:12pt">']
        for p in d.paragraphs[:3000]:
            runs = ''.join(f'<i>{html.escape(r.text)}</i>' if r.italic else html.escape(r.text) for r in p.runs)
            out.append(f'<p>{runs}</p>')
        out.append('</div>')
        return ''.join(out)
    except Exception as e:
        return f'<p>Açılamadı: {html.escape(str(e))}</p>'


def _fill_table(table, path):
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = list(ws.iter_rows(max_row=1000, values_only=True))
    except Exception as e:
        rows = [(f'Açılamadı: {e}',)]
    ncol = max((len(r) for r in rows), default=1)
    table.clear()
    table.setRowCount(len(rows))
    table.setColumnCount(ncol)
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            if v is not None:
                table.setItem(i, j, QTableWidgetItem(str(v)))
