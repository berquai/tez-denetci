"""Kaynak klasörü denetimi: köprü çözümleme, kırık köprü, atıfsız dosya, sayfa kayması tahmini."""
import os
import re
from urllib.parse import unquote
from rapidfuzz import fuzz, process
from .common import norm
from .rules import Finding

EXTS = ('.pdf', '.docx', '.doc', '.xlsx', '.xls', '.epub', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.txt', '.htm', '.html')


class FileIndex:
    def __init__(self, folder):
        self.folder = folder
        self.files = []
        if folder and os.path.isdir(folder):
            for root, _, names in os.walk(folder):
                for n in names:
                    if n.lower().endswith(EXTS) and not n.startswith('~$'):
                        self.files.append(os.path.join(root, n))
        self.keys = [norm(os.path.splitext(os.path.basename(f))[0]) for f in self.files]
        self.by_key = {}
        for f, k in zip(self.files, self.keys):
            self.by_key.setdefault(k, f)

    def resolve(self, link, dosya, base_dir):
        """(yol, durum) — durum: 'ok' | 'dosya-adiyla' | 'benzer' | 'yok'"""
        if link:
            rel = unquote(link).replace('\\', os.sep).replace('/', os.sep)
            for b in (base_dir, os.path.dirname(self.folder or '') or base_dir):
                if b:
                    p = os.path.normpath(os.path.join(b, rel))
                    if os.path.isfile(p):
                        return p, 'ok'
            if os.path.isabs(rel) and os.path.isfile(rel):
                return rel, 'ok'
            name = os.path.splitext(os.path.basename(rel))[0]
        else:
            name = dosya
        k = norm(name or dosya or '')
        if not k:
            return None, 'yok'
        if k in self.by_key:
            return self.by_key[k], 'dosya-adiyla' if link else 'ok'
        if self.keys:
            r = process.extractOne(k, self.keys, scorer=fuzz.ratio, score_cutoff=88)
            if r:
                return self.files[r[2]], 'benzer'
        return None, 'yok'


def audit_files(A, folder, base_dir):
    """A.sources için dosya yollarını çözer, bulguları A.file_findings içine yazar."""
    idx = FileIndex(folder)
    A.file_index = idx
    A.source_paths = {}
    out = []
    used = set()
    if not idx.files:
        out.append(Finding('uyari', 'Dosya bağlantısı', 'dosya', None,
                           f'Kaynak klasörü bulunamadı ya da boş: {folder or "(seçilmedi)"}'))
        A.file_findings = out
        return out
    for s in A.sources:
        path, st = idx.resolve(s.link, s.dosya, base_dir)
        A.source_paths[s.sid] = path
        if path:
            used.add(os.path.normcase(path))
        first = min([r.num for r in s.rows if isinstance(r.num, int)] or [0])
        if st == 'yok':
            out.append(Finding('hata', 'Kırık köprü', 'dosya', s.sid,
                               f'{s.sid} ({first}. dipnot): kaynağın dosyası klasörde bulunamadı — {s.dosya or s.link}'))
        elif st == 'benzer':
            out.append(Finding('uyari', 'Kırık köprü', 'dosya', s.sid,
                               f'{s.sid} ({first}. dipnot): köprü kırık, en benzer dosya kullanıldı: {os.path.basename(path)}'))
        elif st == 'dosya-adiyla':
            out.append(Finding('uyari', 'Kırık köprü', 'dosya', s.sid,
                               f'{s.sid} ({first}. dipnot): Excel köprüsü açılmıyor ama dosya adı klasörde var: {os.path.basename(path)}'))
    orphans = [f for f in idx.files if os.path.normcase(f) not in used]
    if orphans:
        out.append(Finding('bilgi', 'Atıfsız dosya', 'dosya', None,
                           f'Klasörde {len(orphans)} dosya hiçbir kaynağa bağlı değil (tezde kullanılmıyor olabilir)',
                           detail='<br>'.join(os.path.relpath(f, folder) for f in sorted(orphans)[:400])))
    A.file_findings = out
    return out


def first_page(loc):
    m = re.search(r'(?:s\.|ss\.)\s*(\d+)', loc or '')
    return int(m.group(1)) if m else None


def guess_offset(page_count, page_texts, page_range=None):
    """Basılı sayfa → PDF sayfası kayması (pdf_index = basılı - 1 - kayma ... yerine: pdf_sayfa = basılı - kayma).
    1) Makalenin kaynakça aralığı PDF sayfa sayısına uyuyorsa: kayma = başlangıç - 1.
    2) Sayfaların üst/alt satırlarındaki sayılardan çoğunluk kayması."""
    if page_range and page_count:
        a, b = page_range
        if abs((b - a + 1) - page_count) <= 2:
            return a - 1, 'aralık'
    votes = {}
    for i, txt in enumerate(page_texts or []):
        if not txt:
            continue
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        cand = lines[:3] + lines[-3:]
        for l in cand:
            for m in re.finditer(r'(?<![\d.])(\d{1,4})(?![\d.])', l):
                n = int(m.group(1))
                if 0 < n < 5000 and len(l) < 80:
                    off = n - (i + 1)
                    votes[off] = votes.get(off, 0) + 1
    if votes:
        off, v = max(votes.items(), key=lambda x: x[1])
        if v >= max(2, len(page_texts) // 4):
            return off, 'metin'
    return 0, 'yok'
