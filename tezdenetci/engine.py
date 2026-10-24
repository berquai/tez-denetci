"""Uygulama ve komut satırı için tek giriş noktası."""
import os
import time
from .docx_reader import read_docx, read_styles
from .registry import load_excel, build_registry
from .rules import Auditor
from .files_audit import audit_files


def run_audit(docx_path, xlsx_path, folder=None, sheet='Sayfa1', progress=None):
    t0 = time.time()

    def step(msg):
        if progress:
            progress(msg)
    step('Excel okunuyor…')
    rows = load_excel(xlsx_path, sheet)
    step('Kaynak Kütüğü kuruluyor…')
    sources = build_registry(rows)
    step('Tez okunuyor…')
    doc = read_docx(docx_path)
    step('Denetleniyor…')
    A = Auditor(doc, rows, sources).run()
    A.styles = read_styles(docx_path)
    A.paths = {'docx': docx_path, 'xlsx': xlsx_path, 'folder': folder}
    A.file_findings = []
    A.source_paths = {}
    if folder:
        step('Kaynak klasörü denetleniyor…')
        audit_files(A, folder, os.path.dirname(os.path.abspath(xlsx_path)))
    A.elapsed = time.time() - t0
    return A


def finding_keys(A):
    """Sürüm farkı için bulguların kimlikleri (konumdan bağımsız)."""
    keys = set()
    for f in A.findings + A.excel_findings + getattr(A, 'file_findings', []):
        keys.add((f.where, f.cat, f.msg))
    for e in A.bibliography:
        for x in e.changes + e.flags:
            keys.add(('kaynakca', e.source.sid, x))
    return keys
