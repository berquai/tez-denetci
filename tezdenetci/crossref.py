"""Başlık numarasına verilen metin içi atıflar (“bkz. 3.6.1”, “3.6.1’de”, “3.6.1 numaralı başlık”).
Başlık numaraları ekleme/çıkarmada değişir; bu atıflar boşa düşebilir. Her birini bulur, tezdeki başlıklarla
karşılaştırır ve hangi başlığa denk geldiğini gösterir; düzeltmeyi kullanıcı elle yapar."""
import re
from dataclasses import dataclass

NUM = r'\d{1,2}(?:\.\d{1,2}){0,5}'
DOTTED = r'\d{1,2}(?:\.\d{1,2}){1,5}'
_LIST = r'(?:\s*(?:,|ve|ile|-|–)\s*' + NUM + r'(?![\d]))*'
KW = r'(?:[Bb]kz|[Bb]knz|[Bb]k|[Bb]akınız|[Bb]akiniz|[Kk]rş|[Kk]arş|[Kk]arşılaştırınız|[Cc]f|[Ss]ee)\.?'
UNIT = r'(?:alt\s+)?(?:başl[ıi][kğ]\w*|bölüm\w*|kısım\w*|kısm\w*|kesim\w*)'
SUFFIX = r'(?:’|\')(?:[dt][ae](?:ki)?|[dt][ae]n|[ny]?[ae]|[ıiuü]n)\b'
MARKER = r'(?:numaralı|no\.?\s*[’\']?\s*lu|nolu|numarada\w*)'

# 1) bkz. 3.6.1 / bkz. yukarıda 3.6.1 ve 3.7 / bkz. 2. Bölüm / bkz. Bölüm 3
P_KW = re.compile(KW + r',?\s+(?:(?:yukarıda|aşağıda|ayrıca|özellikle|ilgili)\s+)*'
                  r'(?:(?:' + UNIT + r')\s+(?:no\.?\s*)?(' + NUM + r')(?![\d])|(' + DOTTED + r')(?![\d])|(\d{1,2})\.?\s*(?=' + UNIT + r'))' + _LIST)
# 2) 3.6.1’de / 3.6.1. başlıkta / 3.6.1 numaralı başlık / 2. bölümde
P_AFTER = re.compile(r'(?<![\d.,%/])(' + DOTTED + r')(?![\d])\.?(?:' + SUFFIX + r'|\s*' + MARKER + r'|\s+' + UNIT + r')'
                     r'|(?<![\d.,%/])(\d{1,2})\.\s*' + r'(?:alt\s+)?(?:başl[ıi][kğ]\w*|bölüm\w*)')
# 3) (yalnızca gövdede) Bölüm 3 / başlık 3.6.1 — dipnotlarda kitap bölümüyle karışır
P_BEFORE = re.compile(r'\b(?:[Bb]ölüm|[Bb]aşlık|[Kk]ısım)\s+(' + NUM + r')(?![\d]|\.\d)')

ORDINALS = {'birinci': 1, 'ikinci': 2, 'üçüncü': 3, 'dördüncü': 4, 'beşinci': 5, 'altıncı': 6, 'yedinci': 7,
            'sekizinci': 8, 'dokuzuncu': 9, 'onuncu': 10}
UNNUMBERED = {'GİRİŞ', 'SONUÇ', 'ÖNSÖZ', 'ÖZET', 'ABSTRACT', 'ÖZ', 'KISALTMALAR', 'İÇİNDEKİLER', 'KAYNAKÇA',
              'KAYNAKLAR', 'EKLER', 'ÖZGEÇMİŞ', 'TABLOLAR LİSTESİ', 'ŞEKİLLER LİSTESİ', 'TEŞEKKÜR', 'SONUÇ VE ÖNERİLER',
              'DEĞERLENDİRME', 'GENEL DEĞERLENDİRME'}
LEAD_NUM = re.compile(r'^\s*(' + NUM + r')\.?\s+(?=\S)')


def _tr_upper(s):
    return s.replace('i', 'İ').upper()


ORD_UP = {_tr_upper(k): v for k, v in ORDINALS.items()}


@dataclass
class Heading:
    num: str
    title: str
    para: int          # belgedeki ham paragraf sırası (Para.idx ile aynı)
    exact: bool        # numara başlık metninde yazılı mı (değilse düzeylerden tahmin)


def heading_map(doc):
    """{numara: Heading}. Başlıkta yazılı numara varsa o, yoksa biçem düzeyinden (Başlık 1/2/3…) sayılır."""
    out = {}
    counters = [0] * 8
    last_chapter = None
    for i, st, plain in doc.headings:
        m = re.search(r'\d', st)
        level = min(int(m.group()), 8) if m else 1
        up = _tr_upper(plain)
        lm = LEAD_NUM.match(plain)
        w = re.match(r'^(\w+)\s+BÖLÜM\b', up)
        chap = ORD_UP.get(w.group(1)) if w else None
        w = re.match(r'^(?:BÖLÜM\s+(\d{1,2})|(\d{1,2})\.\s*BÖLÜM)\b', up)
        if w:
            chap = int(w.group(1) or w.group(2))
        if chap is not None:
            counters = [chap] + [0] * 7
            title = re.sub(r'^\S+\s+BÖLÜM\s*[:.\-–]?\s*|^BÖLÜM\s+\d+\s*[:.\-–]?\s*|^\d+\.\s*BÖLÜM\s*[:.\-–]?\s*', '', plain, flags=re.I)
            h = Heading(str(chap), title or plain, i, True)
            out.setdefault(h.num, h)
            last_chapter = h if not title else None
            continue
        if last_chapter is not None and level == 1 and not lm:
            # “BİRİNCİ BÖLÜM” satırının altındaki bölüm adı
            last_chapter.title = plain
            last_chapter = None
            continue
        last_chapter = None
        if lm:
            parts = [int(x) for x in lm.group(1).split('.')]
            counters = parts + [0] * (8 - len(parts))
            out.setdefault(lm.group(1), Heading(lm.group(1), plain[lm.end():], i, True))
            continue
        if level == 1 and (up.strip(' .:') in UNNUMBERED):
            continue
        counters[level - 1] += 1
        for k in range(level, 8):
            counters[k] = 0
        num = '.'.join(str(c) for c in counters[:level])
        out.setdefault(num, Heading(num, plain, i, False))
    return out


@dataclass
class CrossRef:
    num: str
    start: int
    end: int
    context: str       # 'yukarıda' | 'aşağıda' | ''


def find_crossrefs(text, body=True):
    """Metindeki başlık numarası atıfları. body=False: dipnot (kitap bölümüyle karışan biçim atlanır)."""
    found = []
    pats = [P_KW, P_AFTER] + ([P_BEFORE] if body else [])
    for pat in pats:
        for m in pat.finditer(text):
            if re.search(r'\b[Ss]aat\s*$', text[max(0, m.start() - 8):m.start()]):
                continue   # saat 14.30’da
            seg = m.group()
            ctx = 'yukarıda' if re.search(r'yukarıda', seg) else 'aşağıda' if re.search(r'aşağıda', seg) else ''
            if not ctx:
                before = text[max(0, m.start() - 25):m.start()]
                ctx = 'yukarıda' if 'yukarıda' in before else 'aşağıda' if 'aşağıda' in before else ''
            nums = [x for x in re.finditer(r'(?<![\d.])' + NUM + r'(?![\d])', seg)]
            for x in nums:
                n = x.group().rstrip('.')
                a, b = m.start() + x.start(), m.start() + x.start() + len(n)
                if any(not (b <= c.start or a >= c.end) for c in found):
                    continue
                found.append(CrossRef(n, a, b, ctx))
    found.sort(key=lambda c: c.start)
    return found


def crossref_findings(text, where, ref, hmap, here_para, body=True):
    """Bulgular: numara tezde yoksa hata (numaralar başlıkta yazılıysa) / uyarı; varsa hangi başlık olduğu."""
    from .rules import Finding, _q
    out = []
    # numaraları başlık metninde yazılı olan düzeyler (ör. yalnızca “BİRİNCİ BÖLÜM” yazılıysa yalnız 1. düzey kesin)
    exact_depths = {h.num.count('.') for h in hmap.values() if h.exact}
    for c in find_crossrefs(text, body):
        h = hmap.get(c.num)
        ctx = text[max(0, c.start - 30):min(len(text), c.end + 20)].strip()
        if h is None:
            if not hmap:
                msg = f'{_q(c.num)} numaralı başlığa atıf var; tezde başlık biçemi bulunamadığı için doğrulanamadı'
                lvl = 'uyari'
            elif c.num.count('.') in exact_depths:
                msg = f'{_q(c.num)} numaralı başlığa atıf var ama tezde bu numarada başlık YOK — numaralar değişmiş olabilir'
                lvl = 'hata'
            else:
                msg = (f'{_q(c.num)} numaralı başlığa atıf var; başlık düzeylerinden hesaplanan numaralarda böyle bir başlık '
                       f'bulunamadı (numaralar tahmini, elle kontrol edin)')
                lvl = 'uyari'
        else:
            lvl = 'uyari'
            msg = (f'{_q(c.num)} numaralı başlığa atıf → {_q(h.title.strip(), 70)}'
                   f'{"" if h.exact else " (numara tahmini)"}. Doğru yere işaret ettiğini kontrol edin; '
                   f'numara yerine başlık adını yazmak kalıcı olur')
            if here_para is not None and here_para >= 0:
                if c.context == 'yukarıda' and h.para > here_para:
                    lvl, msg = 'hata', f'“yukarıda {c.num}” deniyor ama bu başlık metinde AŞAĞIDA: {_q(h.title.strip(), 70)}'
                elif c.context == 'aşağıda' and h.para < here_para:
                    lvl, msg = 'hata', f'“aşağıda {c.num}” deniyor ama bu başlık metinde YUKARIDA: {_q(h.title.strip(), 70)}'
        out.append((Finding(lvl, 'Çapraz atıf', where, ref, msg, [(c.start, c.end)],
                            detail=_ctx_html(text, c)), c, h, ctx))
    return out


def _ctx_html(text, c):
    import html
    a, b = max(0, c.start - 60), min(len(text), c.end + 40)
    return ('…' if a else '') + html.escape(text[a:c.start]) + f'<b>{html.escape(text[c.start:c.end])}</b>' + \
        html.escape(text[c.end:b]) + ('…' if b < len(text) else '')
