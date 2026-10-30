"""Tez .docx dosyasını okur: dipnotlar (sıralı, italikli), gövde paragrafları, kaynakça."""
import re
import zipfile
from dataclasses import dataclass, field
from lxml import etree
from .common import RText, nfc

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


CHAR_ITALIC = {}    # karakter biçemi kimliği -> italik mi (basedOn zinciri çözülmüş)
PARA_ITALIC = {}    # paragraf biçemi kimliği -> italik mi
_OFF = ('0', 'false', 'off', 'none')


def _onoff(el):
    return el is not None and (el.get(W + 'val') or 'true').lower() not in _OFF


def load_style_italics(styles_xml):
    """Biçemlerin italik olup olmadığını basedOn zinciriyle çözer (ör. 'Vurgu' / Emphasis)."""
    CHAR_ITALIC.clear()
    PARA_ITALIC.clear()
    styles = {s.get(W + 'styleId'): s for s in styles_xml.findall(W + 'style')}

    def resolve(sid, seen=()):
        s = styles.get(sid)
        if s is None or sid in seen:
            return False
        rpr = s.find(W + 'rPr')
        if rpr is not None and rpr.find(W + 'i') is not None:
            return _onoff(rpr.find(W + 'i'))
        b = s.find(W + 'basedOn')
        return resolve(b.get(W + 'val'), seen + (sid,)) if b is not None else False
    for sid, s in styles.items():
        val = resolve(sid)
        if s.get(W + 'type') == 'character':
            CHAR_ITALIC[sid] = val
        elif s.get(W + 'type') == 'paragraph':
            PARA_ITALIC[sid] = val


def _run_italic(r, para_italic=False):
    """Word'ün kuralı: doğrudan biçim (w:i) varsa o geçerlidir; yoksa paragraf ve karakter
    biçemlerinin italikliği birbirini tersine çevirir (aç/kapa özelliği)."""
    rpr = r.find(W + 'rPr')
    if rpr is not None:
        i = rpr.find(W + 'i')
        if i is not None:
            return _onoff(i)
        rs = rpr.find(W + 'rStyle')
        if rs is not None:
            return para_italic != CHAR_ITALIC.get(rs.get(W + 'val'), False)
    return para_italic


FNREF_STYLES = set()   # 'footnote reference' karakter biçemi kimlikleri (okuma sırasında doldurulur)


def _run_sup(r):
    """Üst simge mi? (doğrudan biçim ya da dipnot başvurusu karakter biçemi)"""
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return False
    va = rpr.find(W + 'vertAlign')
    if va is not None and va.get(W + 'val') == 'superscript':
        return True
    rs = rpr.find(W + 'rStyle')
    return rs is not None and rs.get(W + 'val') in FNREF_STYLES


def _para_runs(p):
    """Paragraf içindeki metin parçaları ve dipnot referansları, belge sırasıyla.
    Öğeler: (tür, değer, italik, üst simge)"""
    items = []
    ps = p.find(W + 'pPr/' + W + 'pStyle')
    p_it = PARA_ITALIC.get(ps.get(W + 'val'), False) if ps is not None else False
    for r in p.iter(W + 'r'):
        it = _run_italic(r, p_it)
        sup = _run_sup(r)
        for ch in r:
            if ch.tag == W + 't':
                items.append(('t', ch.text or '', it, sup))
            elif ch.tag == W + 'tab':
                items.append(('t', '\t', False, False))
            elif ch.tag in (W + 'br', W + 'cr'):
                items.append(('t', ' ', False, False))
            elif ch.tag == W + 'noBreakHyphen':
                items.append(('t', '-', it, sup))
            elif ch.tag == W + 'footnoteReference':
                items.append(('fn', ch.get(W + 'id'), False, True))
    return items


@dataclass
class Footnote:
    num: int
    wid: str
    rt: RText
    para: int = -1          # gövde paragraf sırası
    sent: int = -1          # paragraf içindeki cümle sırası
    pos: int = -1           # paragraf metnindeki konum
    before: str = ''        # referanstan önceki 3 karakter
    after: str = ''         # referanstan sonraki 3 karakter
    heading: str = ''       # içinde bulunduğu başlık


@dataclass
class Para:
    idx: int
    style: str
    rt: RText
    fn_pos: list = field(default_factory=list)  # [(pos, fn_num)]
    heading: str = ''
    sup: list = field(default_factory=list)     # üst simge biçimli düz metin aralıkları


@dataclass
class Doc:
    footnotes: list
    body: list
    bib: list
    headings: list


HEAD_STYLES_PREFIX = ('aSbebalk', 'Heading', 'Balk')
ABBR = r'(?:vb|vd|bkz|s|ss|C|S|No|Dr|Prof|Doç|Yrd|Çev|Der|Haz|Ed|örn|yy|Bkz|Mad|md|par|St|Mr|Mrs|vs|Ltd|Inc|Co|T\.C|M\.Ö|M\.S|[A-ZÇĞİÖŞÜ])'
SENT_SPLIT = re.compile(r'(?<!\b' + r')(?<!\b'.join(['vb', 'vd', 'bkz', 'ss', 'No', 'Dr', 'Prof', 'Doç', 'Çev', 'Der', 'Haz', 'Ed', 'örn', 'vs', 'Ltd', 'Inc']) + r')(?<!\b[A-ZÇĞİÖŞÜa-z])([.!?…]["”’)]*)(\s+)(?=[A-ZÇĞİÖŞÜ0-9“"(])')


def read_docx(path):
    z = zipfile.ZipFile(path)
    doc = etree.fromstring(z.read('word/document.xml'))
    FNREF_STYLES.clear()
    try:
        st_xml = etree.fromstring(z.read('word/styles.xml'))
        load_style_italics(st_xml)
        for sty in st_xml.findall(W + 'style'):
            nm = sty.find(W + 'name')
            if nm is not None and nm.get(W + 'val', '').lower() in ('footnote reference', 'endnote reference'):
                FNREF_STYLES.add(sty.get(W + 'styleId'))
    except Exception:
        CHAR_ITALIC.clear()
        PARA_ITALIC.clear()
    fxml = etree.fromstring(z.read('word/footnotes.xml')) if 'word/footnotes.xml' in z.namelist() else None
    fn_rt = {}
    if fxml is not None:
        for f in fxml.findall(W + 'footnote'):
            if f.get(W + 'type'):
                continue
            runs = []
            for p_i, p in enumerate(f.findall('.//' + W + 'p')):
                if p_i:
                    runs.append((' ', False))
                for kind, val, it, sup in _para_runs(p):
                    if kind == 't':
                        runs.append((val, it))
            fn_rt[f.get(W + 'id')] = RText.from_runs(runs)

    body_el = doc.find(W + 'body')
    paras = list(body_el.iter(W + 'p'))
    footnotes, body, bib, headings = [], [], [], []
    in_bib = False
    in_body = False
    cur_head = ''
    fn_counter = 0
    for i, p in enumerate(paras):
        st = p.find(W + 'pPr/' + W + 'pStyle')
        st = st.get(W + 'val') if st is not None else ''
        items = _para_runs(p)
        text_runs = []
        fnpos = []
        sups = []
        pos = 0
        for kind, val, it, sup in items:
            if kind == 't':
                v = nfc(val)
                text_runs.append((v, it))
                if sup and v.strip():
                    sups.append((pos, pos + len(v)))
                pos += len(v)
            else:
                fn_counter += 1
                fnpos.append((pos, fn_counter, val))
        rt = RText.from_runs(text_runs)
        plain = rt.text.strip()
        is_head = st.startswith(HEAD_STYLES_PREFIX) or st in ('T1h',)
        if st.startswith('T') and st[1:].isdigit():
            # İçindekiler satırları
            for pos_, n, wid in fnpos:
                footnotes.append(Footnote(n, wid, fn_rt.get(wid, RText())))
            continue
        if plain.upper().replace('İ', 'I') in ('KAYNAKÇA', 'KAYNAKLAR') and not fnpos:
            in_bib, in_body = True, False
            continue
        if st.startswith('aSbebalk1') and not in_bib:
            in_body = True
        if in_bib and st != 'akaynaka' and (is_head or st.startswith(('asbezel', 'fbezel'))
                                             or plain.replace('i', 'İ').upper() in ('ÖZGEÇMİŞ', 'EKLER', 'CV')):
            in_bib = False
            # bu paragraftaki dipnotlar da sayılır; yoksa sonraki numaralar kayar
            for pos_, n, wid in fnpos:
                footnotes.append(Footnote(n, wid, fn_rt.get(wid, RText())))
            continue
        if st == 'akaynaka' or (in_bib and plain and not is_head):
            if plain:
                bib.append(Para(len(bib) + 1, st, rt.strip()))
            for pos_, n, wid in fnpos:
                footnotes.append(Footnote(n, wid, fn_rt.get(wid, RText())))
            continue
        if is_head and plain:
            cur_head = plain
            headings.append((i, st, plain))
        para = Para(i, st, rt, [(p_, n) for p_, n, _ in fnpos], cur_head, sups)
        if in_body or fnpos:
            body.append(para)
        # cümle sıraları
        sent_starts = [0] + [m.end() for m in SENT_SPLIT.finditer(rt.text)]
        for pos_, n, wid in fnpos:
            # referans noktadan hemen sonra geliyorsa önceki cümleye aittir
            s_idx = 0
            for k, s0 in enumerate(sent_starts):
                if s0 <= pos_:
                    s_idx = k
            # bölme noktası tam referans konumundaysa önceki cümle
            if s_idx > 0 and sent_starts[s_idx] == pos_:
                s_idx -= 1
            footnotes.append(Footnote(n, wid, fn_rt.get(wid, RText()), para=len(body) - 1, sent=s_idx,
                                      pos=pos_, before=rt.text[max(0, pos_ - 3):pos_], after=rt.text[pos_:pos_ + 3],
                                      heading=cur_head))
    footnotes.sort(key=lambda f: f.num)
    return Doc(footnotes, body, bib, headings)


def read_styles(path):
    """Dipnot, kaynakça ve gövde biçemlerinin yazı tipi ve puntosu (basedOn zinciri izlenir)."""
    from collections import Counter
    z = zipfile.ZipFile(path)
    st = etree.fromstring(z.read('word/styles.xml'))
    styles = {s.get(W + 'styleId'): s for s in st.findall(W + 'style')}
    dfont, dsz = 'Times New Roman', 12.0
    dd = st.find(W + 'docDefaults/' + W + 'rPrDefault/' + W + 'rPr')
    if dd is not None:
        e = dd.find(W + 'sz')
        if e is not None:
            dsz = int(e.get(W + 'val')) / 2
        e = dd.find(W + 'rFonts')
        if e is not None and e.get(W + 'ascii'):
            dfont = e.get(W + 'ascii')

    def resolve(sid):
        font = size = None
        seen = set()
        while sid and sid in styles and sid not in seen:
            seen.add(sid)
            s = styles[sid]
            rpr = s.find(W + 'rPr')
            if rpr is not None:
                if size is None and rpr.find(W + 'sz') is not None:
                    size = int(rpr.find(W + 'sz').get(W + 'val')) / 2
                if font is None and rpr.find(W + 'rFonts') is not None and rpr.find(W + 'rFonts').get(W + 'ascii'):
                    font = rpr.find(W + 'rFonts').get(W + 'ascii')
            b = s.find(W + 'basedOn')
            sid = b.get(W + 'val') if b is not None else None
        return font or dfont, size or dsz

    fn_style = None
    if 'word/footnotes.xml' in z.namelist():
        fx = etree.fromstring(z.read('word/footnotes.xml'))
        c = Counter()
        for p in fx.iter(W + 'p'):
            ps = p.find(W + 'pPr/' + W + 'pStyle')
            if ps is not None:
                c[ps.get(W + 'val')] += 1
        fn_style = c.most_common(1)[0][0] if c else None
    if not fn_style:
        fn_style = next((k for k, s in styles.items()
                         if s.find(W + 'name') is not None and s.find(W + 'name').get(W + 'val') == 'footnote text'), None)
    return {'dipnot': resolve(fn_style), 'kaynakca': resolve('akaynaka'), 'govde': resolve('aSbemetinTezi')}
