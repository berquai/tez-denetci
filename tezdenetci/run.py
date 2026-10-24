"""Komut satırı: python -m tezdenetci.run TEZ.docx LISTE.xlsx [çıktı klasörü]"""
import os
import sys
from .docx_reader import read_docx, read_styles
from .registry import load_excel, build_registry
from .rules import Auditor
from .report import build_report
from .export import export_xlsx


def main(docx_path, xlsx_path, out_dir='.', sheet='Sayfa1'):
    rows = load_excel(xlsx_path, sheet)
    sources = build_registry(rows)
    doc = read_docx(docx_path)
    A = Auditor(doc, rows, sources).run()
    os.makedirs(out_dir, exist_ok=True)
    rp = os.path.join(out_dir, 'Tez_Denetim_Raporu.html')
    xp = os.path.join(out_dir, 'Kaynak_Kutugu.xlsx')
    meta = (f'{os.path.basename(docx_path)} · {len(doc.footnotes)} dipnot, {len(doc.bib)} kaynakça girdisi · '
            f'{os.path.basename(xlsx_path)} · {len(rows)} satır, {len(sources)} kaynak')
    A.styles = read_styles(docx_path)
    build_report(A, rp, meta, A.styles)
    export_xlsx(A, xp)
    from .kaynakca import export_docx
    kp = os.path.join(out_dir, 'Kaynakca.docx')
    export_docx(A.bibliography, docx_path, kp)
    return A, rp, xp


if __name__ == '__main__':
    a = sys.argv[1:]
    main(*a)
