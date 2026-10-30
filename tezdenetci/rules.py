"""Denetim kuralları. Her kural Finding üretir; düzeltmeler FixOp olarak birikir."""
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein
from .common import RText, norm, norm_map, tr_lower, tr_upper_char, tr_sort_key, parse_pages
from .registry import split_locator, expected_mask, _punct_rules, _title_end, classify, GAZETTES
from .matcher import Matcher, align_alnum

LEVELS = {'hata': 0, 'uyari': 1, 'oneri': 2, 'bilgi': 3}
LEVEL_TR = {'hata': 'Hata', 'uyari': 'Uyarı', 'oneri': 'Öneri', 'bilgi': 'Bilgi'}

TR_SMALL = {'ve', 'ile', 'veya', 'ya', 'da', 'de', 'ki', 'mi', 'mı', 'mu', 'mü', 'yahut', 'ise', 'hem', 'ne', 'yani'}
TR_LENIENT = {'içinde', 'için', 'gibi', 'kadar', 'göre', 'dair', 'karşı', 'üzerine', 'doğru', 'sonra', 'önce', 'bir'}
EN_SMALL = {'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'so', 'yet', 'as', 'at', 'by', 'in', 'of', 'off', 'on',
            'per', 'to', 'up', 'via', 'vs', 'vs.', 'from', 'into', 'onto', 'over', 'with', 'than', 'upon', 'since',
            'until', 'through', 'between', 'among', 'about', 'after', 'before', 'during', 'without', 'within', 'toward',
            'towards', 'under', 'against', 'across', 'beyond', 'versus', 'de', 'la', 'le', 'les', 'des', 'du', 'und',
            'der', 'die', 'das', 'von', 'zu', 'et', 'en', 'à', 'y', 'del', 'di', 'van', 'den', 'al', 'el', 'e', 'i', 'sur', 'aux', 'dans', 'pour', 'per', 'da', 'do', 'dos', 'das', 'para', 'con'}
SMALL = TR_SMALL | EN_SMALL
EN_HINT = re.compile(r'\b(the|and|of|for|in|on|from|with|to)\b')
INVISIBLE = {'\xa0': 'bölünmez boşluk', '​': 'sıfır genişlikli boşluk', '­': 'yumuşak tire',
             ' ': 'ince boşluk', ' ': 'dar bölünmez boşluk', '﻿': 'BOM karakteri', '\t': 'sekme'}


@dataclass
class Finding:
    level: str
    cat: str
    where: str          # 'dipnot' | 'kaynakca' | 'govde' | 'excel' | 'genel'
    ref: object         # dipnot no / kaynakça sırası / paragraf / excel satırı
    msg: str
    spans: list = field(default_factory=list)
    fix_note: str = ''
    detail: str = ''
    fix: object = None       # tek başına önerilen RText (ör. eksik kaynakça girdisi)


@dataclass
class FixOp:
    kind: str     # 'ital' | 'repl'
    a: int
    b: int
    val: object   # bool | RText


def apply_ops(rt, ops):
    out = rt.copy()
    for op in ops:
        if op.kind == 'ital':
            for k in range(op.a, min(op.b, len(out.ital))):
                out.ital[k] = op.val
    # çakışan değişikliklerde geniş olan kazanır (ör. bütün atfın tam/kısa künyeyle değişmesi,
    # aynı atıf içindeki büyük harf düzeltmesinden önce gelir)
    chosen = []
    for op in sorted([o for o in ops if o.kind == 'repl'], key=lambda o: -(o.b - o.a)):
        if all(not _overlaps(op, c) for c in chosen):
            chosen.append(op)
    # metin değişiklikleri sağdan sola
    for op in sorted(chosen, key=lambda o: (o.a, o.b), reverse=True):
        new = op.val
        if new.ital and len(new.ital) == len(new.text) and op.b - op.a == len(new.text) and all(not x for x in new.ital):
            # yalnızca harf değişikliği: mevcut italikleri koru
            new = RText(new.text, out.ital[op.a:op.b])
        out = out.replace(op.a, op.b, new)
    from .common import curly
    return curly(_tidy_spaces(out))


def _overlaps(x, y):
    """İki değişiklik aynı karakterlere dokunuyor mu? Kenardaki ekleme (a == b) çakışma sayılmaz."""
    if x.a == x.b:
        return y.a < x.a < y.b
    if y.a == y.b:
        return x.a < y.a < x.b
    return x.a < y.b and y.a < x.b


def _tidy_spaces(rt):
    t, it = rt.text, list(rt.ital)
    for k, c in enumerate(t):
        if c == ' ':
            l = it[k - 1] if k > 0 else False
            r = it[k + 1] if k + 1 < len(t) else False
            it[k] = l and r
    return RText(t, it)


# ------------------------------------------------------------------ yardımcılar

def _q(s, n=60):
    s = s.replace('\xa0', '⍽')
    return '‘' + (s if len(s) <= n else s[:n] + '…') + '’'


def title_regions(text, mask, tip):
    """Büyük harf kuralının uygulanacağı başlık bölgeleri."""
    regs = []
    if tip in ('makale', 'web', 'kisa_makale'):
        for m in re.finditer(r'“([^”]+)”', text):
            regs.append((m.start(1), m.end(1)))
    if tip != 'mevzuat' and mask:
        k = 0
        while k < len(mask):
            if mask[k]:
                a = k
                while k < len(mask) and mask[k] is not False:
                    k += 1
                b = k
                while b > a and (mask[b - 1] is None):
                    b -= 1
                if b - a > 2:
                    regs.append((a, b))
            k += 1
    return regs


def caps_issues(text, regions):
    """Başlık bölgelerinde küçük harfle başlayan içerik kelimelerini döndürür: [(a,b,kelime,öneri)]"""
    out = []
    for ra, rb in regions:
        seg = text[ra:rb]
        first = True
        for m in re.finditer(r'\S+', seg):
            w = m.group()
            a = ra + m.start()
            core = w.lstrip('“‘"(«[')
            lead = len(w) - len(core)
            core_cut = re.split(r'[’\'\-–/]', core)[0]
            word = re.sub(r'[^\wçğıöşüâîû]+$', '', core_cut)
            prev_colon = first or bool(re.search(r'[:?!.]\s*$', text[ra:a]))
            if re.fullmatch(r'[a-zçğıöşü]{1,5}\.', core_cut[:len(word) + 1]) or re.fullmatch(r'(s|ss|v|vol|no|parag|c|vd|bkz)', word):
                first = False
                continue
            if word and word[0].isalpha():
                lw = tr_lower(word)
                if word[0].islower():
                    if lw in TR_LENIENT:
                        pass
                    elif lw in SMALL and not prev_colon:
                        pass
                    elif re.fullmatch(r'[a-z]+[A-Z].*', word):   # iPhone, eCommerce
                        pass
                    else:
                        out.append((a + lead, a + lead + len(word), word, tr_upper_char(word[0]) + word[1:]))
            first = False
            if re.search(r'[:?!]$', w):
                first = True
    return out


def map_mask(seg_text, src_text, src_mask):
    """Kaynak kökün beklenen maskesini dipnottaki metne taşır."""
    if src_mask is None or not src_text:
        return None
    mp = align_alnum(seg_text, src_text)
    n = len(seg_text)
    base = [None] * n
    unknown = False
    for k, c in enumerate(seg_text):
        if c.isalnum():
            j = mp.get(k)
            if j is None:
                base[k] = 'gap'
            else:
                base[k] = src_mask[j]
                if src_mask[j] is None and src_text[j].isalnum():
                    unknown = True
    if unknown and all(v is None or v == 'gap' for v in base if v is not False):
        if all((v is None or v == 'gap') for v in base):
            return None
    # boşlukları komşu harflerle doldur
    alnum_idx = [k for k in range(n) if seg_text[k].isalnum()]
    for pos, k in enumerate(alnum_idx):
        if base[k] == 'gap':
            l = next((base[alnum_idx[p]] for p in range(pos - 1, -1, -1) if base[alnum_idx[p]] != 'gap'), None)
            r = next((base[alnum_idx[p]] for p in range(pos + 1, len(alnum_idx)) if base[alnum_idx[p]] != 'gap'), None)
            base[k] = l if l == r else None
    bool_mask = [False] * n
    for k in range(n):
        if seg_text[k].isalnum():
            bool_mask[k] = bool(base[k])
        else:
            l = next((base[j] for j in range(k - 1, -1, -1) if seg_text[j].isalnum()), False)
            r = next((base[j] for j in range(k + 1, n) if seg_text[j].isalnum()), False)
            bool_mask[k] = bool(l) and bool(r)
    pm = _punct_rules(seg_text, bool_mask)
    for k in range(n):
        if seg_text[k].isalnum() and base[k] is None:
            pm[k] = None
    return pm


def italic_findings(rt, a, b, exp, where, ref, label=''):
    """rt[a:b] parçasının italiklerini beklenen maskeyle karşılaştırır."""
    fnd, ops = [], []
    if exp is None:
        return fnd, ops
    seg = rt.text[a:b]
    groups = []   # (start, end, kind)
    k = 0
    while k < len(seg):
        e = exp[k]
        act = rt.ital[a + k]
        if e is not None and e != act:
            kind = ('alnum' if seg[k].isalnum() else 'punct', e)
            st = k
            k += 1
            while k < len(seg):
                e2 = exp[k]
                if e2 is None:
                    k += 1
                    continue
                if e2 is not None and e2 != rt.ital[a + k] and (('alnum' if seg[k].isalnum() else 'punct'), e2) == kind:
                    k += 1
                    continue
                break
            en = k
            while en > st and seg[en - 1].isspace():
                en -= 1
            groups.append((st, en, kind))
        else:
            k += 1
    for st, en, (typ, want) in groups:
        txt = seg[st:en]
        if typ == 'alnum':
            lvl = 'hata'
            if want:
                msg = f'{_q(txt)} italik olmalı'
                # tamamen düz yazılmış başlık mı?
            else:
                msg = f'{_q(txt)} italik olmamalı'
        else:
            lvl = 'uyari'
            what = {'(': 'parantez', ')': 'parantez', '“': 'tırnak', '”': 'tırnak', '’': 'kesme/ek', "'": 'kesme/ek'}.get(txt.strip()[:1], 'noktalama')
            msg = f'{_q(txt)} ({what}) italik olmamalı' if not want else f'{_q(txt)} italik olmalı'
        fnd.append(Finding(lvl, 'İtalik', where, ref, msg + (f' — {label}' if label else ''), [(a + st, a + en)]))
    for k in range(len(seg)):
        if exp[k] is not None:
            ops.append(FixOp('ital', a + k, a + k + 1, exp[k]))
    # ek: kesme + ek italik kalmışsa (beklenen None olsa da) kontrol
    return fnd, ops


def edge_italic_findings(rt, where, ref):
    """Kaynaktan bağımsız: italik bölgenin kenarındaki noktalama, parantez, tırnak, kesme ve ekler."""
    fnd, ops = [], []
    t, it = rt.text, rt.ital
    n = len(t)
    k = 0
    while k < n:
        if it[k]:
            a = k
            while k < n and it[k]:
                k += 1
            b = k
            # sondaki boşluklar önemsiz
            bb = b
            while bb > a and t[bb - 1].isspace():
                bb -= 1
            # son: kesme+ek
            m = re.search(r'[’\'][A-Za-zÇĞİÖŞÜçğıöşüâîû]*$', t[a:bb])
            if m and m.start() > 0 and not (b < n and t[b:b + 1].strip() == '' and b + 1 < n and it[b + 1]):
                s0 = a + m.start()
                fnd.append(Finding('hata', 'İtalik', where, ref,
                                   f'İtalik adın ardındaki ek {_q(t[s0:bb])} düz yazılmalı', [(s0, bb)]))
                ops.append(FixOp('ital', s0, bb, False))
                bb = s0
            # son: noktalama
            j = bb
            while j > a and t[j - 1] in ',.;:' and not (t[j - 1] == '.' and j - 2 >= a and t[j - 2].isupper() and (j - 3 < a or not t[j - 3].isalpha())):
                j -= 1
            if j < bb and t[a:j].strip():
                fnd.append(Finding('uyari', 'İtalik', where, ref,
                                   f'İtalik bölgenin sonundaki {_q(t[j:bb])} düz olmalı', [(j, bb)]))
                ops.append(FixOp('ital', j, bb, False))
            # baş: noktalama / açılış
            j = a
            while j < bb and (t[j] in ',.;:' or t[j].isspace()):
                j += 1
            if j > a and t[a:j].strip() and t[j:bb].strip():
                fnd.append(Finding('uyari', 'İtalik', where, ref,
                                   f'İtalik bölgenin başındaki {_q(t[a:j].strip())} düz olmalı', [(a, j)]))
                ops.append(FixOp('ital', a, j, False))
        else:
            k += 1
    # italik başlığın ardından düz kesme ama italik ek: “Ülkü’*de*”
    for m in re.finditer(r'[’\']([A-Za-zÇĞİÖŞÜçğıöşüâîû]+)', t):
        s0, e0 = m.start(), m.end()
        if s0 > 0 and it[s0 - 1] and not it[s0] and any(it[s0 + 1:e0]) and not (e0 + 1 < n and it[e0 + 1]):
            fnd.append(Finding('hata', 'İtalik', where, ref, f'Ek {_q(t[s0 + 1:e0])} düz yazılmalı', [(s0 + 1, e0)]))
            ops.append(FixOp('ital', s0 + 1, e0, False))
    return fnd, ops


def text_findings(rt, where, ref, majority):
    """Biçimsel denetimler: görünmez karakter, çift boşluk, tırnak içi noktalama vb."""
    fnd, ops = [], []
    t = rt.text
    for ch, name in INVISIBLE.items():
        for m in re.finditer(re.escape(ch), t):
            fnd.append(Finding('uyari', 'Görünmez karakter', where, ref, f'{name} var (görünmez; Word’de satır kırılmasını etkiler)',
                               [(m.start(), m.end())]))
            ops.append(FixOp('repl', m.start(), m.end(), RText.plain('' if ch in '​­﻿' else ' ')))
    for m in re.finditer(r'(?<=\S) {2,}(?=\S)', t):
        fnd.append(Finding('uyari', 'Boşluk', where, ref, 'Çift boşluk', [(m.start(), m.end())]))
        ops.append(FixOp('repl', m.start(), m.end(), RText.plain(' ')))
    for m in re.finditer(r'([,.;])”', t):
        fnd.append(Finding('hata', 'Noktalama', where, ref,
                           f'{_q(m.group(1))} tırnağın içinde; tezdeki kullanıma göre tırnaktan sonra gelmeli',
                           [(m.start(), m.end())], fix_note='”' + m.group(1)))
        ops.append(FixOp('repl', m.start(), m.end(), RText.plain('”' + m.group(1))))
    for m in re.finditer(r'(\d)\.,\s', t):
        fnd.append(Finding('hata', 'Noktalama', where, ref, 'Sayfa numarasından sonra “.,” — fazladan nokta',
                           [(m.start() + 1, m.end() - 1)]))
        # yalnızca fazla nokta silinir; kaynaklar arası ayraç önerisini (;) 'Çoklu atıf' kuralı verir
        ops.append(FixOp('repl', m.start() + 1, m.end() - 1, RText.plain(',')))
    for m in re.finditer(r'(\d{1,2}\.\d{1,2}\.\d{4}|\d{4})\.(https?://)', t):
        fnd.append(Finding('hata', 'Noktalama', where, ref, 'Tarih ile bağlantı arasında boşluk yok',
                           [(m.end(1), m.end(1) + 1)]))
        ops.append(FixOp('repl', m.end(1) + 1, m.end(1) + 1, RText.plain(' ')))
    for m in re.finditer(r'(?<![\w.])s\.(?=\d)', t):
        fnd.append(Finding('hata', 'Noktalama', where, ref, '“s.” ile sayfa numarası arasında boşluk yok', [(m.start(), m.end())]))
        ops.append(FixOp('repl', m.end(), m.end(), RText.plain(' ')))
    fq, oq = quote_findings(rt, where, ref)
    fnd += fq
    ops += oq
    if re.search(r'\bizlek', tr_lower(t)):
        m = re.search(r'(?i)izlek\w*', t)
        fnd.append(Finding('hata', 'Yasaklı kelime', where, ref, '“izlek” kullanılmamalı (konu, başlık, mesele, tema, eksen, odak)',
                           [(m.start(), m.end())]))
    return fnd, ops


URL_RE = re.compile(r'(https?://\S+|www\.\S+|\b10\.\d{4,9}/\S+|DOI:\s*\S+)', re.I)


def quote_findings(rt, where, ref):
    """Tırnak ve kesme işaretleri eğik (“ ” ‘ ’) olmalı; web adresi ve DOI muaf.
    Ayrıca yön hataları: kelime içinde ‘ (’ olmalı), kapanışta “ / açılışta ”."""
    fnd, ops = [], []
    t = rt.text
    skip = set()
    for m in URL_RE.finditer(t):
        skip.update(range(m.start(), m.end()))

    def add(k, msg, rep):
        fnd.append(Finding('hata', 'Tırnak ve kesme', where, ref, msg, [(k, k + 1)], fix_note=rep))
        ops.append(FixOp('repl', k, k + 1, RText.plain(rep)))
    for k, c in enumerate(t):
        if k in skip:
            continue
        prev = t[k - 1] if k > 0 else ' '
        nxt = t[k + 1] if k + 1 < len(t) else ' '
        if c == "'" or c in '´`′':
            name = {"'": 'Düz kesme', '´': 'Aksan işareti (´)', '`': 'Ters tırnak (`)', '′': 'Dakika işareti (′)'}[c]
            if prev.isalnum() or nxt.isalnum():
                add(k, f'{name} kesme yerine kullanılmış → ’', '’')
        elif c == '"':
            opening = prev.isspace() or prev in '([{—–-/' or k == 0
            add(k, 'Düz tırnak (") → ' + ('“' if opening else '”'), '“' if opening else '”')
        elif c == '‘' and prev.isalpha() and nxt.isalpha():
            add(k, 'Kelime içinde açılış tek tırnağı (‘) var; kesme işareti ’ olmalı', '’')
        elif c == '“' and (nxt.isspace() or nxt in ',.;:)') and prev.isalnum():
            add(k, 'Kapanışta açılış tırnağı (“) kullanılmış → ”', '”')
        elif c == '”' and prev.isspace() and nxt.isalnum():
            add(k, 'Açılışta kapanış tırnağı (”) kullanılmış → “', '“')
    return fnd, ops


def english_dotted_i(rt, where, ref):
    fnd, ops = [], []
    t = rt.text
    if not EN_HINT.search(t):
        return fnd, ops
    for m in re.finditer(r'\bİ([a-z]+)\b', t):
        w = m.group(1)
        if re.search(r'[çğıöşü]', w):
            continue
        if not (re.search(r'(tion|ional|ism|ment|ance|ence|ship|ness|th|ph|wh|ck|ous|ive|ity|ing|ly|ry|ct)$', w) or
                re.search(r'(tion|th|wh|ph|ck|ee|oo|ou)', w) or w in ('n', 's', 't', 'f', 'nto', 'ts', 'mpact', 'ndia')):
            continue
        ctx = t[max(0, m.start() - 60): m.end() + 60]
        if len(EN_HINT.findall(ctx)) >= 1:
            fnd.append(Finding('hata', 'Yazım', where, ref,
                               f'İngilizce kelimede Türkçe noktalı İ: {_q(m.group())} → {_q("I" + m.group(1))}',
                               [(m.start(), m.start() + 1)]))
            ops.append(FixOp('repl', m.start(), m.start() + 1, RText.plain('I')))
    return fnd, ops


def typo_vs_filename(src):
    """Başlık kelimelerini dosya adıyla karşılaştırır (ör. Sructuralism / structuralism)."""
    out = []
    if not src.dosya:
        return out
    fw = set(re.findall(r'[a-zçğıöşüâîû]{6,}', tr_lower(src.dosya)))
    tw = re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşüâîû]{6,}', src.tam.text + ' ' + src.kay.text)
    seen = set()
    for w in tw:
        lw = tr_lower(w)
        if lw in fw or lw in seen:
            continue
        for f in fw:
            fold = str.maketrans('âîû', 'aiu')
            if lw.translate(fold) == f.translate(fold) or lw.startswith(f) or f.startswith(lw):
                continue
            if abs(len(f) - len(lw)) <= 1 and Levenshtein.distance(f, lw) == 1 and lw[0] == f[0]:
                seen.add(lw)
                out.append((w, f))
    return out


# ------------------------------------------------------------------ çoğunluk (ev kuralı) tespiti

def detect_majority(doc, rows):
    maj = {}
    texts = [f.rt.text for f in doc.footnotes]
    lead = Counter(t[:1] == ' ' for t in texts if t)
    maj['lead_space'] = lead.most_common(1)[0][0] if lead else True
    ap = Counter()
    for t in texts + [b.rt.text for b in doc.bib]:
        ap['’'] += len(re.findall(r'(?<=\w)’(?=\w)', t))
        ap["'"] += len(re.findall(r"(?<=\w)'(?=\w)", t))
    maj['apos'] = ap.most_common(1)[0][0] if ap else '’'
    vd = Counter()
    for r in rows:
        for t in (r.kisa.text, r.tam.text):
            vd[','] += len(re.findall(r',\s+vd\.', t))
            vd[' '] += len(re.findall(r'[^,\s]\s+vd\.', t))
    for t in texts:
        vd[','] += len(re.findall(r',\s+vd\.', t))
        vd[' '] += len(re.findall(r'[^,\s]\s+vd\.', t))
    maj['vd'] = vd.most_common(1)[0][0] if vd else ','
    maj['vd_counts'] = dict(vd)
    ve = Counter()
    for r in rows:
        stem = split_locator(r.kisa)[0].text if r.kisa.text else ''
        if _two_authors_ve(stem):
            ve['ve'] += 1
        elif re.match(r'^[^,“\s]+, [A-ZÇĞİÖŞÜ][^,“\s]+, (“|[A-ZÇĞİÖŞÜ])', stem):
            ve[','] += 1
    maj['kisa_authors'] = ve.most_common(1)[0][0] if ve else ','
    maj['kisa_author_counts'] = dict(ve)
    no = Counter()
    for t in texts + [r.tam.text for r in rows] + [r.kay.text for r in rows]:
        no['.'] += len(re.findall(r'Kanun No\.', t))
        no[':'] += len(re.findall(r'Kanun No:', t))
    maj['kanun_no'] = no.most_common(1)[0][0] if no else '.'
    maj['kanun_no_counts'] = dict(no)
    dash = Counter()
    for t in texts:
        dash['-'] += len(re.findall(r's\.\s*\d+-\d+', t))
        dash['–'] += len(re.findall(r's\.\s*\d+–\d+', t))
    maj['page_dash'] = dash.most_common(1)[0][0] if dash else '-'
    ref = Counter()
    for f in doc.footnotes:
        if f.para < 0:
            continue
        if f.before[-1:] in '.,;:' and f.before[-1:]:
            ref['after'] += 1
        elif f.after[:1] in '.,;:' and f.after[:1]:
            ref['before'] += 1
    maj['ref_pos'] = ref.most_common(1)[0][0] if ref else 'after'
    maj['ref_counts'] = dict(ref)
    return maj


# ------------------------------------------------------------------ ana denetim

class Auditor:
    def __init__(self, doc, rows, sources):
        self.doc, self.rows, self.sources = doc, rows, sources
        self.matcher = Matcher(sources)
        self.findings = []
        self.fn_ops = defaultdict(list)
        self.bib_ops = defaultdict(list)
        self.body_ops = defaultdict(list)
        self.fn_cits = {}
        self.maj = detect_majority(doc, rows)
        self.src_first = {}
        self.bib_match = {}
        self.src_bib = {}

    def add(self, fnd, ops=None, store=None, key=None):
        self.findings.extend(fnd)
        if ops and store is not None:
            store[key].extend(ops)

    # --------------------------------------------------- dipnotlar
    def audit_footnotes(self):
        doc = self.doc
        uses = defaultdict(list)
        for f in doc.footnotes:
            cits = self.matcher.match(f.rt.text)
            self.fn_cits[f.num] = cits
            if not cits and f.rt.text.strip():
                self.add([Finding('uyari', 'Eşleşme', 'dipnot', f.num,
                                  'Bu dipnot Kaynak Kütüğü’ndeki hiçbir kaynakla eşleşmedi (yeni kaynak mı? Excel’de yok mu?)')])
            for c in cits:
                uses[c.source.sid].append((f.num, c))
        # sıra: ilk kullanım tam, sonrakiler kısa
        for sid, lst in uses.items():
            lst.sort(key=lambda x: (x[0], x[1].start))
            for k, (num, c) in enumerate(lst):
                s = c.source
                f = doc.footnotes[num - 1]
                if k == 0:
                    self.src_first[sid] = num
                    if c.form == 'kisa':
                        new = s.tam.copy()
                        new_m = s.tam_mask
                        newrt = RText(new.text, [bool(x) for x in (new_m or [False] * len(new.text))])
                        self.add([Finding('hata', 'İlk kullanım', 'dipnot', num,
                                          'Bu kaynak tezde ilk kez burada geçiyor ama KISA dipnot yazılmış. Tam dipnot olmalı.',
                                          [(c.start, c.end)])],
                                 [FixOp('repl', c.start, c.end, newrt)], self.fn_ops, num)
                else:
                    if c.form == 'tam':
                        first = lst[0][0]
                        newrt = RText(s.kisa.text, [bool(x) for x in (s.kisa_mask or [False] * len(s.kisa.text))])
                        self.add([Finding('hata', 'İlk kullanım', 'dipnot', num,
                                          f'Bu kaynak ilk kez {first}. dipnotta geçti; burada KISA dipnot olmalı.',
                                          [(c.start, c.end)])],
                                 [FixOp('repl', c.start, c.end, newrt)], self.fn_ops, num)
        # her dipnotun iç denetimi
        lead = self.maj['lead_space']
        for f in doc.footnotes:
            rt = f.rt
            cits = self.fn_cits[f.num]
            t = rt.text
            # baştaki boşluk
            if t and (t[:1] == ' ') != lead:
                self.add([Finding('uyari', 'Biçim tutarlılığı', 'dipnot', f.num,
                                  'Dipnot metni ' + ('boşlukla başlamıyor' if lead else 'boşlukla başlıyor') +
                                  ' (diğer dipnotlarla tutarsız)', [(0, 1)])],
                         [FixOp('repl', 0, 0, RText.plain(' ')) if lead else FixOp('repl', 0, 1, RText.plain(''))],
                         self.fn_ops, f.num)
            # son nokta
            st = t.rstrip()
            if st and not st.endswith('.'):
                ends_url = bool(re.search(r'https?://\S+$', st))
                self.add([Finding('hata' if not ends_url else 'uyari', 'Noktalama', 'dipnot', f.num,
                                  'Dipnot nokta ile bitmiyor' + (' (bağlantı ile bitiyor)' if ends_url else ''),
                                  [(len(st) - 1, len(st))])],
                         [FixOp('repl', len(st), len(st), RText.plain('.'))], self.fn_ops, f.num)
            fnd, ops = text_findings(rt, 'dipnot', f.num, self.maj)
            self.add(fnd, ops, self.fn_ops, f.num)
            fnd, ops = english_dotted_i(rt, 'dipnot', f.num)
            self.add(fnd, ops, self.fn_ops, f.num)
            covered = set()
            for i, c in enumerate(cits):
                s = c.source
                seg_t = t[c.start:c.end]
                src_rt = s.tam if c.form == 'tam' else s.kisa
                src_mask = s.tam_mask if c.form == 'tam' else s.kisa_mask
                exp = map_mask(seg_t, src_rt.text, src_mask)
                fnd, ops = italic_findings(rt, c.start, c.end, exp, 'dipnot', f.num)
                self.add(fnd, ops, self.fn_ops, f.num)
                covered.update(range(c.start, c.end))
                # büyük harf
                tip = s.tip if not (s.tip == 'makale' and c.form == 'kisa') else 'kisa_makale'
                regs = title_regions(seg_t, exp, tip)
                if s.gazete:   # gazete manşeti kaynaktaki gibi kalır
                    regs = [(a, b) for a, b in regs if seg_t[a - 1:a] != '“']
                # tez künyesi: enstitü / anabilim dalı / şehir (danışman isteği)
                if c.form == 'tam' and s.tez and re.search(r'Tezi', seg_t) and not re.search(r'Enstitü', seg_t):
                    self.add([Finding('hata', 'Künye', 'dipnot', f.num,
                                      'Tez künyesinde enstitü, anabilim dalı ve şehir bilgisi eksik', [(c.start, c.end)])])
                for a, b, w, sug in caps_issues(seg_t, regs):
                    self.add([Finding('hata', 'Büyük harf', 'dipnot', f.num,
                                      f'Başlıkta {_q(w)} büyük harfle başlamalı → {_q(sug)}',
                                      [(c.start + a, c.start + b)])],
                             [FixOp('repl', c.start + a, c.start + b, RText.plain(sug))], self.fn_ops, f.num)
                # kütükle karşılaştırma
                kstem = src_rt.text.replace('\xa0', ' ')
                wstem = seg_t.replace('\xa0', ' ')
                if re.sub(r'\s+', ' ', kstem).strip(' .,') != re.sub(r'\s+', ' ', wstem).strip(' .,') and c.form:
                    self.add([Finding('bilgi', 'Kütük farkı', 'dipnot', f.num,
                                      'Word’deki metin Excel kütüğündeki ' + ('tam' if c.form == 'tam' else 'kısa') +
                                      ' biçimden farklı', [(c.start, c.end)],
                                      detail=_diff_html(kstem, wstem))])
                # sayfa
                pages = parse_pages(c.loc) if c.loc.startswith(('s.', 'ss.')) else []
                for p1, p2 in pages:
                    if p2 < p1:
                        self.add([Finding('hata', 'Sayfa', 'dipnot', f.num, f'Sayfa aralığı ters: {c.loc}',
                                          [(c.loc_start, c.loc_end)])])
                    if s.page_range and (p1 < s.page_range[0] or p2 > s.page_range[1]):
                        self.add([Finding('hata', 'Sayfa', 'dipnot', f.num,
                                          f'Sayfa {p1}{"-" + str(p2) if p2 != p1 else ""}, makalenin aralığı '
                                          f'(s. {s.page_range[0]}-{s.page_range[1]}) dışında', [(c.loc_start, c.loc_end)])])
                if c.loc and self.maj['page_dash'] == '-' and '–' in c.loc:
                    k0 = c.loc_start + c.loc.index('–')
                    self.add([Finding('uyari', 'Biçim tutarlılığı', 'dipnot', f.num, 'Sayfa aralığında uzun tire (–); tezde kısa tire (-) kullanılıyor',
                                      [(k0, k0 + 1)])], [FixOp('repl', k0, k0 + 1, RText.plain('-'))], self.fn_ops, f.num)
                if not c.loc and s.tip in ('makale', 'kitap') and c.form == 'tam':
                    if not re.search(r'\bs\.\s*\d', t[c.end:cits[i + 1].start if i + 1 < len(cits) else len(t)]):
                        self.add([Finding('bilgi', 'Sayfa', 'dipnot', f.num, 'Atıfta sayfa numarası yok', [(c.start, c.end)])])
                # cilt = yıl
                m = re.search(r'C\.\s*(\d{4}),\s*S\.\s*\d+,\s*(\d{4})', seg_t)
                if m and m.group(1) == m.group(2):
                    self.add([Finding('uyari', 'Künye', 'dipnot', f.num,
                                      f'Cilt numarası yılla aynı (C. {m.group(1)}); derginin künyesini PDF’ten kontrol edin',
                                      [(c.start + m.start(), c.start + m.end(1))])])
                # vd. virgülü
                for m in re.finditer(r'(,?)\s+vd\.', seg_t):
                    has_comma = bool(m.group(1))
                    want_comma = self.maj['vd'] == ','
                    if has_comma != want_comma:
                        a0 = c.start + m.start()
                        self.add([Finding('uyari', 'Biçim tutarlılığı', 'dipnot', f.num,
                                          ('“vd.” öncesinde virgül olmalı' if want_comma else '“vd.” öncesinde virgül olmamalı') +
                                          f' (Excel’de {self.maj["vd_counts"].get(",", 0)} yerde “, vd.”, {self.maj["vd_counts"].get(" ", 0)} yerde “ vd.”)',
                                          [(a0, c.start + m.end())])],
                                 [FixOp('repl', a0, c.start + m.end(), RText.plain(', vd.' if want_comma else ' vd.'))],
                                 self.fn_ops, f.num)
                # Kanun No biçimi
                for m in re.finditer(r'Kanun No([.:])', seg_t):
                    if m.group(1) != self.maj['kanun_no']:
                        a0 = c.start + m.start(1)
                        self.add([Finding('uyari', 'Biçim tutarlılığı', 'dipnot', f.num,
                                          f'“Kanun No{m.group(1)}” — tezde çoğunlukla “Kanun No{self.maj["kanun_no"]}” kullanılıyor',
                                          [(a0, a0 + 1)])], [FixOp('repl', a0, a0 + 1, RText.plain(self.maj['kanun_no']))],
                                 self.fn_ops, f.num)
                # ayraç: birden çok kaynak
                if i + 1 < len(cits):
                    gap_a = c.loc_end if c.loc_end > 0 else c.end
                    gap = t[gap_a:cits[i + 1].start]
                    if re.fullmatch(r'\.?,\s*', gap):
                        self.add([Finding('oneri', 'Çoklu atıf', 'dipnot', f.num,
                                          'Aynı dipnottaki kaynaklar virgülle ayrılmış; noktalı virgül (;) daha açık olur',
                                          [(gap_a, cits[i + 1].start)])],
                                 [FixOp('repl', gap_a, cits[i + 1].start, RText.plain('; '))], self.fn_ops, f.num)
            for c in cits:
                for w, f_ in typo_vs_filename(c.source):
                    if w in t[c.start:c.end]:
                        k0 = c.start + t[c.start:c.end].index(w)
                        self.add([Finding('uyari', 'Yazım', 'dipnot', f.num,
                                          f'Künyedeki {_q(w)} ile dosya adındaki {_q(f_)} arasında 1 harf fark var — hangisi doğru? (dosya adı da hatalı olabilir)',
                                          [(k0, k0 + len(w))])])
            # aynı kaynak aynı dipnotta iki kez
            cnt = Counter(c.source.sid for c in cits)
            for sid, n in cnt.items():
                if n > 1:
                    cs = [c for c in cits if c.source.sid == sid]
                    self.add([Finding('uyari', 'Çoklu atıf', 'dipnot', f.num,
                                      f'Aynı kaynak bu dipnotta {n} kez geçiyor; sayfalar tek atıfta birleştirilebilir ' +
                                      '(' + ', '.join(c.loc for c in cs if c.loc) + ')', [(c.start, c.end) for c in cs])])
            # kaynak dışı metindeki kenar italikleri
            fnd, ops = edge_italic_findings(rt, 'dipnot', f.num)
            # atıf içindeki kenar sorunlarını yukarıdaki maske zaten yakaladı; tekrarı önle
            fnd = [x for x in fnd if not any(a in covered for a, b in x.spans)]
            ops = [o for o in ops if o.a not in covered]
            self.add(fnd, ops, self.fn_ops, f.num)
        # kısa biçim tutarlılığı (Word içinde)
        variants = defaultdict(set)
        for num, cits in self.fn_cits.items():
            for c in cits:
                if c.form == 'kisa':
                    variants[c.source.sid].add(re.sub(r'\s+', ' ', self.doc.footnotes[num - 1].rt.text[c.start:c.end]).strip(' ,.'))
        for sid, vs in variants.items():
            if len(vs) > 1:
                nums = [n for n, cs in self.fn_cits.items() if any(c.source.sid == sid and c.form == 'kisa' for c in cs)]
                self.add([Finding('uyari', 'Kısa dipnot tutarlılığı', 'genel', nums,
                                  f'Aynı kaynağın kısa dipnotu {len(vs)} farklı biçimde yazılmış (dipnot {", ".join(map(str, nums))})',
                                  detail='<br>'.join(_esc(v) for v in sorted(vs)))])

    # --------------------------------------------------- gövde
    def audit_body(self):
        doc = self.doc
        # dipnot referans konumu
        for f in doc.footnotes:
            if f.para < 0:
                continue
            if f.before.endswith(' '):
                self.add([Finding('hata', 'Dipnot konumu', 'govde', f.num,
                                  f'{f.num}. dipnot numarasından önce boşluk var', [])])
        # sahte dipnot numaraları: dipnot gibi görünen ama Word dipnotuna bağlı olmayan rakamlar
        SUPMAP = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹', '0123456789')
        for p_i, p in enumerate(doc.body):
            t = p.rt.text
            for a, b in p.sup:
                seg = t[a:b]
                if re.search(r'\d', seg):
                    self.add([Finding('hata', 'Sahte dipnot', 'govde', p_i,
                                      f'Üst simge {_q(seg.strip())} dipnot numarası gibi görünüyor ama Word’ün dipnot bağlantısı değil '
                                      '(kopyala-yapıştırla gelmiş olabilir). Gerçek dipnot ekleyin ya da silin.', [(a, b)])])
            for m in re.finditer(r'[⁰¹²³⁴⁵⁶⁷⁸⁹]+', t):
                if m.start() > 0 and t[m.start() - 1] in 'mM' and m.group() in ('²', '³'):
                    continue   # m², km³ gibi birimler
                self.add([Finding('hata', 'Sahte dipnot', 'govde', p_i,
                                  f'Üst simge karakter {_q(m.group())} ({m.group().translate(SUPMAP)}) dipnot numarası gibi duruyor ama gerçek dipnot değil',
                                  [(m.start(), m.end())])])
            supset = {k for a, b in p.sup for k in range(a, b)}
            for m in re.finditer(r'(?<=[A-Za-zÇĞİÖŞÜçğıöşüâîû”’)][.,;:])(\d{1,4})(?=\s+[A-ZÇĞİÖŞÜ“(]|\s*$)', t):
                if m.start(1) in supset:
                    continue
                self.add([Finding('uyari', 'Sahte dipnot', 'govde', p_i,
                                  f'Noktalamaya yapışık {_q(m.group(1))} sayısı dipnot numarası kalıntısı olabilir (gerçek dipnot değil)',
                                  [(m.start(1), m.end(1))])])
        # birleştirme kuralı: aynı paragraf, ardışık cümle, aynı tek kaynak
        fns = doc.footnotes
        for a, b in zip(fns, fns[1:]):
            if a.para < 0 or a.para != b.para:
                continue
            ca, cb = self.fn_cits.get(a.num, []), self.fn_cits.get(b.num, [])
            if len(ca) == 1 and len(cb) == 1 and ca[0].source.sid == cb[0].source.sid:
                if b.sent - a.sent == 1:
                    self.add([Finding('hata', 'Birleştirme', 'govde', [a.num, b.num],
                                      f'{a.num} ve {b.num}. dipnotlar aynı paragrafta ardışık cümlelerde aynı kaynağa '
                                      f'({ca[0].loc or "?"} / {cb[0].loc or "?"}) atıf yapıyor; danışman kuralına göre tek dipnotta birleştirilmeli')])
                elif b.sent == a.sent:
                    self.add([Finding('uyari', 'Birleştirme', 'govde', [a.num, b.num],
                                      f'{a.num} ve {b.num}. dipnotlar aynı cümlede aynı kaynağa atıf yapıyor; birleştirilebilir')])
        # italik kenar kuralları ve bilinen başlıklar
        titles = []
        for s in self.sources:
            for txt, mask in ((s.tam.text, s.tam_mask),):
                if not mask:
                    continue
                k = 0
                while k < len(mask):
                    if mask[k]:
                        a0 = k
                        while k < len(mask) and mask[k] is not False:
                            k += 1
                        t0 = txt[a0:k].strip(' :,')
                        if len(t0) >= 18 and len(t0.split()) >= 3:
                            titles.append(t0)
                    k += 1
            if s.title_short and len(s.title_short) >= 18 and len(s.title_short.split()) >= 3:
                titles.append(s.title_short)
        tkeys = sorted({norm(x): x for x in titles}.items(), key=lambda x: -len(x[0]))

        def caps_sig(x):
            return [w[0] for w in re.findall(r'[A-Za-zÇĞİÖŞÜçğıöşüâîû]+', x) if w[0].isupper()]
        for p_i, p in enumerate(doc.body):
            fnd, ops = edge_italic_findings(p.rt, 'govde', p_i)
            self.add(fnd, ops, self.body_ops, p_i)
            fnd, ops = text_findings(p.rt, 'govde', p_i, self.maj)
            keep = [x for x in fnd if x.cat in ('Yasaklı kelime', 'Boşluk', 'Tırnak ve kesme')]
            spans_keep = {sp for x in keep for sp in x.spans}
            fnd = keep
            ops = [o for o in ops if o.kind == 'repl' and ((o.a, o.b) in spans_keep or (p.rt.text[o.a:o.b].strip() == '' and o.b - o.a > 1))]
            self.add(fnd, ops, self.body_ops, p_i)
            nt, idx = norm_map(p.rt.text)
            used = set()
            for key, orig in tkeys:
                k = nt.find(key)
                while k >= 0:
                    e = k + len(key)
                    if (k == 0 or nt[k - 1] == ' ') and (e == len(nt) or nt[e] == ' ') and not (used & set(range(k, e))):
                        a0, b0 = idx[k], idx[e - 1] + 1
                        used.update(range(k, e))
                        inside_quote = p.rt.text[:a0].count('“') > p.rt.text[:a0].count('”')
                        if caps_sig(p.rt.text[a0:b0]) != caps_sig(orig) or p.style.startswith(('aSbebalk', 'Heading')):
                            k = nt.find(key, k + 1)
                            continue
                        letters = [p.rt.ital[j] for j in range(a0, b0) if p.rt.text[j].isalnum()]
                        if letters and sum(letters) / len(letters) < 0.5 and not inside_quote:
                            self.add([Finding('uyari', 'İtalik', 'govde', p_i,
                                              f'Metinde eser/dergi adı geçiyor ama italik değil: {_q(p.rt.text[a0:b0])}', [(a0, b0)])],
                                     [FixOp('ital', j, j + 1, True) for j in range(a0, b0) if p.rt.text[j].isalnum() or p.rt.text[j] in ' :-'],
                                     self.body_ops, p_i)
                    k = nt.find(key, k + 1)

    # --------------------------------------------------- başlık numarasına atıflar (bkz. 3.6.1)
    def audit_crossrefs(self):
        from .crossref import heading_map, crossref_findings
        doc = self.doc
        self.heading_map = hmap = heading_map(doc)
        rows = []
        for p_i, p in enumerate(doc.body):
            if p.style.startswith(('aSbebalk', 'Heading', 'Balk')):
                continue
            for fnd, c, h, ctx in crossref_findings(p.rt.text, 'govde', p_i, hmap, p.idx, body=True):
                self.add([fnd])
                rows.append((f'Paragraf {p_i + 1}', fnd, c, h, ctx))
        for f in doc.footnotes:
            here = doc.body[f.para].idx if f.para >= 0 else None
            for fnd, c, h, ctx in crossref_findings(f.rt.text, 'dipnot', f.num, hmap, here, body=False):
                self.add([fnd])
                rows.append((f'Dipnot {f.num}', fnd, c, h, ctx))
        self.crossrefs = rows
        if rows:
            n_bad = sum(1 for r in rows if r[3] is None or r[1].level == 'hata')
            lines = [f'{_esc(w)}: …{_esc(ctx)}… → ' + (_esc(h.title.strip()[:70]) if h else '<b>başlık bulunamadı</b>')
                     for w, fnd, c, h, ctx in rows]
            self.add([Finding('uyari', 'Çapraz atıf', 'genel', None,
                              f'Tezde başlık numarasına verilmiş {len(rows)} atıf var (bkz. 3.6.1 gibi)' +
                              (f'; {n_bad} tanesi bulunamayan ya da ters yönlü başlığa işaret ediyor' if n_bad else '') +
                              '. Numaralar ekleme/çıkarmada değişir; başlık adıyla atıf daha güvenlidir.',
                              detail='<br>'.join(lines[:400]))])

    # --------------------------------------------------- kaynakça
    def audit_bib(self):
        bib = self.doc.bib
        bnorms = [norm(b.rt.text) for b in bib]
        # alıntılanan kaynaklar kaynakçada mı?
        cited = []
        for num in sorted(self.fn_cits):
            for c in self.fn_cits[num]:
                if c.source.sid not in [x.sid for x in cited]:
                    cited.append(c.source)
        for s in cited:
            kn = norm(s.kay.text)
            hit = None
            if kn in bnorms:
                hit = bnorms.index(kn)
            else:
                r = process.extractOne(kn, bnorms, scorer=fuzz.ratio, score_cutoff=90)
                if r:
                    hit = r[2]
                else:
                    # yazar + başlık ile ara
                    title = s.title_short
                    if not title:
                        m = re.search(r'“([^”]+)”', s.kay.text)
                        title = m.group(1) if m else ''
                    tn = norm(title)
                    first = norm(s.kay.text.split(',')[0])
                    cands = [i for i, b in enumerate(bnorms) if tn and len(tn) >= 6 and tn in b and (first in b or not first)]
                    if len(cands) == 1:
                        hit = cands[0]
                    elif len(cands) > 1:
                        hit = max(cands, key=lambda i: fuzz.ratio(kn, bnorms[i]))
            if hit is None:
                kr = RText(s.kay.text, [bool(x) for x in (s.kay_mask or [False] * len(s.kay.text))])
                pos = self._bib_position(s.kay.text)
                self.add([Finding('hata', 'Kaynakça', 'genel', self.src_first.get(s.sid),
                                  f'{self.src_first.get(s.sid)}. dipnotta atıf yapılan kaynak kaynakçada yok' +
                                  (f' (alfabetik olarak “{_short(bib[pos - 1].rt.text)}” girdisinden sonra gelmeli)' if pos else ''),
                                  fix=kr)])
            else:
                self.src_bib[s.sid] = hit
                self.bib_match[hit] = s
                bt = bib[hit].rt.text
                if tr_lower(norm(bt)) != tr_lower(kn):
                    a_ = re.sub(r'\s+', ' ', s.kay.text.replace('\xa0', ' '))
                    b_ = re.sub(r'\s+', ' ', bt.replace('\xa0', ' '))
                    only_case = tr_lower(a_) == tr_lower(b_)
                    if not only_case:
                        self.add([Finding('uyari', 'Kaynakça farkı', 'kaynakca', hit,
                                          f'{self.src_first.get(s.sid)}. dipnottaki kaynağın kaynakça girdisi Excel kütüğündekinden farklı (büyük-küçük harf dışında)',
                                          detail=_diff_html(a_, b_))])
        # kaynakça girdisi denetimi
        lower_title_entries = 0
        for i, b in enumerate(bib):
            rt = b.rt
            t = rt.text
            fnd, ops = text_findings(rt, 'kaynakca', i, self.maj)
            self.add(fnd, ops, self.bib_ops, i)
            if t and not t.rstrip().endswith('.'):
                self.add([Finding('hata', 'Noktalama', 'kaynakca', i, 'Kaynakça girdisi nokta ile bitmiyor',
                                  [(len(t) - 1, len(t))])], [FixOp('repl', len(t), len(t), RText.plain('.'))], self.bib_ops, i)
            s = self.bib_match.get(i)
            if s is not None:
                exp = map_mask(t, s.kay.text, s.kay_mask)
                tip = s.tip
            else:
                tip = classify(t)
                exp = self._bib_mask(t, tip)
            fnd, ops = italic_findings(rt, 0, len(t), exp, 'kaynakca', i)
            if s is None and exp is not None:
                # kütükte karşılığı yok: yalnızca tamamen düz yazılmış başlığı bildir
                want = [k for k in range(len(t)) if exp[k] and t[k].isalnum()]
                if want and not any(rt.ital[k] for k in want):
                    a0, b0 = want[0], want[-1] + 1
                    fnd = [Finding('hata', 'İtalik', 'kaynakca', i, f'{_q(t[a0:b0])} italik olmalı (tamamen düz yazılmış)', [(a0, b0)])]
                    ops = [o for o in ops if o.val]
                else:
                    fnd = [x for x in fnd if x.level != 'hata']
                    ops = [o for o in ops if not o.val]
            self.add(fnd, ops, self.bib_ops, i)
            fnd, ops = edge_italic_findings(rt, 'kaynakca', i)
            fnd = [x for x in fnd if exp is None]
            ops = [o for o in ops if exp is None]
            self.add(fnd, ops, self.bib_ops, i)
            regs = title_regions(t, exp, tip) if exp else [(m.start(1), m.end(1)) for m in re.finditer(r'“([^”]+)”', t)]
            iss = caps_issues(t, regs)
            if iss:
                lower_title_entries += 1
                for a, b2, w, sug in iss:
                    self.bib_ops[i].append(FixOp('repl', a, b2, RText.plain(sug)))
                self.add([Finding('hata', 'Büyük harf', 'kaynakca', i,
                                  f'Başlıkta {len(iss)} kelime küçük harfle başlıyor: ' + ', '.join(_q(w, 20) for _, _, w, _ in iss[:6]) +
                                  ('…' if len(iss) > 6 else ''), [(a, b2) for a, b2, _, _ in iss])])
        self.bib_caps_count = lower_title_entries
        # sıralama
        keys = [self._bib_key(b.rt.text.split(', ')[0]) for b in bib]
        for i in range(1, len(bib)):
            if keys[i] < keys[i - 1] and keys[i][0] == keys[i - 1][0]:
                self.add([Finding('uyari', 'Sıralama', 'kaynakca', i,
                                  f'Alfabetik sıra bozuk: “{_short(bib[i - 1].rt.text)}” girdisinden sonra geliyor')])
        # mükerrer
        seen = {}
        for i, n in enumerate(bnorms):
            if n in seen:
                self.add([Finding('hata', 'Kaynakça', 'kaynakca', i, f'Mükerrer girdi (aynısı {seen[n] + 1}. sırada)')])
            else:
                seen[n] = i

    def _bib_key(self, t):
        t2 = t.lstrip('“"‘')
        return (0 if t[:1] in '“"‘' else 1, tr_sort_key(t2))

    def _bib_position(self, t):
        k = self._bib_key(t)
        pos = 0
        for i, b in enumerate(self.doc.bib):
            if self._bib_key(b.rt.text) <= k:
                pos = i + 1
        return pos

    def _bib_mask(self, t, tip):
        if tip in ('makale', 'mevzuat'):
            return expected_mask(t, tip)
        if tip != 'kitap':
            return None
        m = re.match(r'^((?:[^,“”()]+?, (?:[A-ZÇĞİÖŞÜ][a-zçğıöşü]?\.\s?(?:[A-ZÇĞİÖŞÜ]\.\s?)*)(?:,\s*(?:ve\s+)?|\s+ve\s+))+)', t)
        if not m:
            return None
        a = m.end()
        b = _title_end(t, a, a)
        if b <= a:
            return None
        mask = [False] * len(t)
        for k in range(a, b):
            mask[k] = True
        return _punct_rules(t, mask)

    # --------------------------------------------------- Excel (tüm tez)
    def audit_excel(self):
        rows = self.rows
        ex = []
        # ilk kullanım (Excel numara sırasıyla)
        by_src = defaultdict(list)
        last = 0
        eff = {}
        for r in sorted(rows, key=lambda r: r.row):
            if isinstance(r.num, int):
                last = r.num
            eff[r.row] = last
            if r.source is not None:
                by_src[r.source.sid].append(r)
        def rkey(r):
            return (eff[r.row], r.row)
        for sid, lst in by_src.items():
            lst.sort(key=rkey)
            first = lst[0]
            if not first.tam.text.strip():
                ex.append(Finding('hata', 'İlk kullanım', 'excel', first.row,
                                  f'Excel {eff[first.row]}. dipnot: kaynağın ilk kullanımı ama tam dipnot sütunu boş (kısa: {_q(first.kisa.text, 70)})'))
            for r in lst[1:]:
                if r.tam.text.strip():
                    ex.append(Finding('hata', 'İlk kullanım', 'excel', r.row,
                                      f'Excel {eff[r.row]}. dipnot: kaynak ilk kez {eff[first.row]}. dipnotta geçti; burada yeniden TAM künye yazılmış',
                                      detail=_esc(r.tam.text[:300])))
            names = Counter(r.dosya for r in lst if r.dosya)
            if len(names) > 1:
                ex.append(Finding('uyari', 'Dosya bağlantısı', 'excel', first.row,
                                  f'{sid}: aynı kaynak {len(names)} farklı dosya adıyla bağlanmış — biri kırık köprü olabilir',
                                  detail='<br>'.join(f'{_esc(k)} <span class="cnt">×{v}</span> (dipnot ' +
                                                     ', '.join(str(eff[r.row]) for r in lst if r.dosya == k)[:80] + ')'
                                                     for k, v in names.most_common())))
        # kısa biçim varyantları
        for s in self.sources:
            stems = Counter()
            for r in by_src.get(s.sid, []):
                if r.kisa.text:
                    stems[split_locator(r.kisa)[0].text.replace('\xa0', ' ')] += 1
            if len(stems) > 1:
                ex.append(Finding('uyari', 'Kısa dipnot tutarlılığı', 'excel', s.rows[0].row,
                                  f'{s.sid}: kısa dipnot {len(stems)} farklı biçimde yazılmış',
                                  detail='<br>'.join(f'{_esc(k)} <span class="cnt">×{v}</span>' for k, v in stems.most_common())))
        # italik ve büyük harf (Excel hücreleri)
        for s in self.sources:
            for lbl, rt, mask, tip in (('tam', s.tam, s.tam_mask, s.tip), ('kaynakça', s.kay, s.kay_mask, s.tip),
                                       ('kısa', s.kisa, s.kisa_mask, 'kisa_makale' if s.tip == 'makale' else s.tip)):
                if not rt.text or mask is None:
                    continue
                for a0, b0 in _true_regions(mask, rt.text):
                    if not any(rt.ital[k] for k in range(a0, b0) if rt.text[k].isalnum()):
                        sure = any(g in rt.text[a0:b0] for g in GAZETTES) or s.tip == 'makale' or (s.title_short and norm(s.title_short) in norm(rt.text[a0:b0]))
                        ex.append(Finding('hata' if sure else 'uyari', 'İtalik', 'excel', s.rows[0].row,
                                          f'{s.sid} ({lbl}): {_q(rt.text[a0:b0])} italik olmalı (hücrede düz)',
                                          detail=RText(rt.text, rt.ital).to_html([(a0, b0, 'm-err')])))
                regs_x = title_regions(rt.text, mask, tip)
                if s.gazete:
                    regs_x = [(a, b) for a, b in regs_x if rt.text[a - 1:a] != '“']
                iss = caps_issues(rt.text, regs_x)
                if iss:
                    ex.append(Finding('hata', 'Büyük harf', 'excel', s.rows[0].row,
                                      f'{s.sid} ({lbl}): ' + ', '.join(_q(w, 25) for _, _, w, _ in iss[:6])))
            for w, f_ in typo_vs_filename(s):
                ex.append(Finding('uyari', 'Yazım', 'excel', s.rows[0].row,
                                  f'{s.sid}: künyedeki {_q(w)} ile dosya adındaki {_q(f_)} arasında 1 harf fark var — biri yazım hatası olabilir'))
        # tırnak / kesme (tüm Excel)
        qrows = []
        for r in rows:
            for lbl, rt in (('tam', r.tam), ('kısa', r.kisa), ('kaynakça', r.kay)):
                fq, _ = quote_findings(rt, 'excel', r.row)
                for x in fq:
                    a0 = x.spans[0][0]
                    qrows.append(f'{eff[r.row]}. dipnot ({lbl}): …{_esc(rt.text[max(0, a0 - 25):a0])}<mark class="m-hata">{_esc(rt.text[a0])}</mark>{_esc(rt.text[a0 + 1:a0 + 25])}… → {_esc(x.fix_note)}')
        if qrows:
            ex.append(Finding('hata', 'Tırnak ve kesme', 'excel', None,
                              f'{len(qrows)} yerde düz ya da ters yönlü tırnak/kesme var (web adresi ve DOI hariç)',
                              detail='<br>'.join(qrows[:300])))
        # görünmez karakter
        nb = Counter()
        for r in rows:
            for lbl, rt in (('tam', r.tam), ('kısa', r.kisa), ('kaynakça', r.kay)):
                if '\xa0' in rt.text:
                    nb[lbl] += 1
        if nb:
            ex.append(Finding('uyari', 'Görünmez karakter', 'excel', None,
                              'Bölünmez boşluk (NBSP) içeren hücreler: ' + ', '.join(f'{k} {v}' for k, v in nb.items()) +
                              '. Word’e yapıştırınca satır sonu davranışı değişir.'))
        # kısa dipnotta yazar bağlacı
        ve = self.maj['kisa_author_counts']
        if ve.get('ve') and ve.get(','):
            minority = 've' if self.maj['kisa_authors'] == ',' else ','
            lst = []
            for r in rows:
                stem = split_locator(r.kisa)[0].text if r.kisa.text else ''
                if minority == 've' and _two_authors_ve(stem):
                    lst.append(f'{r.num}: {_esc(stem[:80])}')
            ex.append(Finding('uyari', 'Biçim tutarlılığı', 'excel', None,
                              f'Kısa dipnotta iki yazar {ve.get(",", 0)} yerde virgülle (Doğan, Yardımcı), {ve.get("ve", 0)} yerde “ve” ile bağlanmış',
                              detail='<br>'.join(lst[:60])))
        vd = self.maj['vd_counts']
        if vd.get(',') and vd.get(' '):
            ex.append(Finding('uyari', 'Biçim tutarlılığı', 'excel', None,
                              f'“vd.” kullanımı tutarsız: {vd.get(",", 0)} yerde “, vd.”, {vd.get(" ", 0)} yerde virgülsüz “ vd.”'))
        no = self.maj['kanun_no_counts']
        if no.get('.') and no.get(':'):
            ex.append(Finding('uyari', 'Biçim tutarlılığı', 'excel', None,
                              f'“Kanun No.” {no.get(".", 0)} yerde, “Kanun No:” {no.get(":", 0)} yerde'))
        # köprü / dosya
        nolink = [r for r in rows if r.kay.text and not r.link]
        if nolink:
            ex.append(Finding('uyari', 'Dosya bağlantısı', 'excel', None,
                              f'{len(nolink)} kaynak satırında dosya köprüsü yok',
                              detail='<br>'.join(f'{r.num}: {_esc(r.kay.text[:90])}' for r in nolink[:40])))
        self.excel_findings = ex
        # Excel ↔ Word eşzamanlılık
        sync = []
        exmap = {}
        for r in rows:
            if isinstance(r.num, int) and r.num not in exmap:
                exmap[r.num] = r
        for f in self.doc.footnotes:
            r = exmap.get(f.num)
            w = re.sub(r'\s+', ' ', f.rt.text.replace('\xa0', ' ')).strip()
            e = re.sub(r'\s+', ' ', ((r.tam.text or r.kisa.text) if r else '').replace('\xa0', ' ')).strip()
            if w != e:
                sync.append((f.num, w, e))
        self.sync = sync

    def run(self):
        from .kaynakca import build_bibliography, word_only_entries
        self.audit_footnotes()
        self.audit_body()
        self.audit_crossrefs()
        self.audit_excel()
        # Word'deki kaynakça eski: kaynakça kütükten yeniden üretilir
        self.bibliography = build_bibliography(self)
        self.word_only = word_only_entries(self, self.bibliography)
        return self

    def fixed_footnote(self, num):
        f = self.doc.footnotes[num - 1]
        return apply_ops(f.rt, self.fn_ops.get(num, []))

    def fixed_bib(self, i):
        return apply_ops(self.doc.bib[i].rt, self.bib_ops.get(i, []))

    def fixed_body(self, i):
        return apply_ops(self.doc.body[i].rt, self.body_ops.get(i, []))


def _two_authors_ve(stem):
    from .registry import PUB_HINT
    m = re.match(r'^([A-ZÇĞİÖŞÜ][^\s,“]+(?: [A-ZÇĞİÖŞÜ][^\s,“]+)?) ve ([A-ZÇĞİÖŞÜ][^\s,“]+(?: [A-ZÇĞİÖŞÜ][^\s,“]+)?), ', stem)
    return bool(m) and not PUB_HINT.search(m.group(0)) and 'Birliği' not in m.group(0)


def _true_regions(mask, text):
    out, k = [], 0
    while k < len(mask):
        if mask[k]:
            a = k
            while k < len(mask) and mask[k] is not False:
                k += 1
            b = k
            while b > a and not text[b - 1].isalnum():
                b -= 1
            if b > a:
                out.append((a, b))
        k += 1
    return out


def _esc(s):
    import html
    return html.escape(s)


def _short(t, n=45):
    t = t.strip()
    return t if len(t) <= n else t[:n] + '…'


def _diff_html(a, b):
    """a: kütük, b: Word — karakter farkları vurgulu."""
    import html
    from difflib import SequenceMatcher
    sm = SequenceMatcher(None, a, b, autojunk=False)
    ea, eb = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == 'equal':
            ea.append(html.escape(a[i1:i2]))
            eb.append(html.escape(b[j1:j2]))
        else:
            if i2 > i1:
                ea.append(f'<span class="d-del">{html.escape(a[i1:i2])}</span>')
            if j2 > j1:
                eb.append(f'<span class="d-ins">{html.escape(b[j1:j2])}</span>')
    return f'<div class="diff"><div><b>Excel:</b> {"".join(ea)}</div><div><b>Word:</b> {"".join(eb)}</div></div>'
