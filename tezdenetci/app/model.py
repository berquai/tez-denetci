"""Denetim sonucunu (Auditor) arayüzün göstereceği kayıtlara dönüştürür."""
import html
from collections import defaultdict
from dataclasses import dataclass, field
from ..rules import LEVELS, LEVEL_TR, Finding

E = html.escape


@dataclass
class Item:
    group: str            # 'Dipnotlar' | 'Gövde' | 'Kaynakça' | 'Excel' | 'Dosyalar' | 'Genel'
    title: str
    kind: str             # 'dipnot' | 'govde' | 'kaynakca' | 'excel' | 'dosya' | 'genel'
    ref: object
    findings: list = field(default_factory=list)
    search: str = ''
    sources: list = field(default_factory=list)   # [(Source, loc)]

    @property
    def level(self):
        if not self.findings:
            return 'ok'
        return min(self.findings, key=lambda f: LEVELS[f.level]).level

    @property
    def cats(self):
        return {f.cat for f in self.findings}


def build_items(A):
    items = []
    by_fn = defaultdict(list)
    by_body = defaultdict(list)
    general = []
    for f in A.findings:
        if f.where == 'dipnot':
            by_fn[f.ref].append(f)
        elif f.where == 'govde' and isinstance(f.ref, int) and f.cat != 'Dipnot konumu':
            by_body[f.ref].append(f)
        elif f.where == 'govde' and isinstance(f.ref, list):
            for n in f.ref:
                by_fn[n].append(f)
        elif f.where == 'genel' and isinstance(f.ref, list):
            for n in f.ref:
                by_fn[n].append(f)
        else:
            general.append(f)
    for fn in A.doc.footnotes:
        cits = A.fn_cits.get(fn.num, [])
        it = Item('Dipnotlar', f'Dipnot {fn.num}', 'dipnot', fn.num, by_fn.get(fn.num, []),
                  fn.rt.text.lower(), [(c.source, c.loc, c.form) for c in cits])
        items.append(it)
    for i, fs in sorted(by_body.items()):
        p = A.doc.body[i]
        items.append(Item('Gövde', f'Paragraf {i + 1}', 'govde', i, fs, p.rt.text.lower()))
    for g in general:
        items.append(Item('Genel', g.msg[:60], 'genel', g, [g], g.msg.lower()))
    for e in A.bibliography:
        fs = [Finding('oneri', 'Otomatik düzeltme', 'kaynakca', e.source.sid, 'Otomatik: ' + c) for c in e.changes]
        fs += [Finding('uyari', 'Kontrol et', 'kaynakca', e.source.sid, x) for x in e.flags]
        items.append(Item('Kaynakça', e.new.text[:70], 'kaynakca', e, fs, e.new.text.lower(),
                          [(e.source, '', 'kay')]))
    for b in A.word_only:
        f0 = Finding('uyari', 'Kütükte yok', 'kaynakca', None, 'Eski Word kaynakçasında var, Excel kütüğünde yok')
        items.append(Item('Kaynakça', '(eski) ' + b.rt.text[:62], 'eski', b, [f0], b.rt.text.lower()))
    for f in A.excel_findings:
        items.append(Item('Excel', f.msg[:70], 'excel', f, [f], (f.msg + ' ' + (f.detail or '')).lower()))
    for f in getattr(A, 'file_findings', []):
        src = next((s for s in A.sources if s.sid == f.ref), None)
        items.append(Item('Dosyalar', f.msg[:70], 'dosya', f, [f], f.msg.lower(), [(src, '', 'kay')] if src else []))
    return items


# ------------------------------------------------------------------ ayrıntı HTML

CSS = ''


def set_colors(c):
    """Temaya göre ayrıntı panelinin stilini kurar (themes.colors_for çıktısı)."""
    global CSS
    CSS = f'''
<style>
body{{font-family:"Segoe UI",sans-serif;font-size:10pt;color:{c['text']}}}
h3{{color:{c['text']}}}
.cite{{font-family:"Times New Roman",serif;font-size:13pt;line-height:150%}}
.now{{background:{c['now']};padding:6px}}
.fix{{background:{c['fix']};padding:6px}}
.lbl{{font-size:8pt;color:{c['mute']};font-weight:bold;letter-spacing:1px}}
.h{{background:{c['h']}}}.u{{background:{c['u']}}}.o{{background:{c['o']}}}
.lv-hata{{color:{c['hata']};font-weight:bold}}.lv-uyari{{color:{c['uyari']};font-weight:bold}}.lv-oneri{{color:{c['oneri']};font-weight:bold}}.lv-bilgi{{color:{c['bilgi']};font-weight:bold}}
.cat{{color:{c['mute']}}}
.ctx{{font-family:"Times New Roman",serif;font-size:12pt}}
.ref{{color:{c['ref']};font-weight:bold}}
.d-del{{background:{c['dele']};text-decoration:line-through}}.d-ins{{background:{c['ins']}}}
.mono{{font-family:Consolas,monospace;font-size:9pt;color:{c['mute']}}}
.legend{{font-size:8pt;color:{c['mute']}}}
</style>'''


set_colors(dict(text='#1f1d1a', mute='#6b665e', now='#f4f1ea', fix='#eaf4ea', h='#f9c9c3', u='#ffe0a3', o='#cfe2f3',
                ref='#7a3b1d', hata='#b42318', uyari='#a15c00', oneri='#2f5f8a', bilgi='#5b5f66', dele='#f9c9c3', ins='#cfe2f3'))


def _marks(findings):
    out = []
    cls = {'hata': 'h', 'uyari': 'u', 'oneri': 'o'}
    for f in findings:
        if f.level in cls:
            for a, b in f.spans:
                out.append((a, b, cls[f.level]))
    out.sort(key=lambda x: {'o': 0, 'u': 1, 'h': 2}[x[2]])
    return out


def _flist(findings):
    rows = []
    seen = {}
    for f in sorted(findings, key=lambda f: LEVELS[f.level]):
        k = (f.level, f.cat, f.msg)
        seen[k] = seen.get(k, 0) + 1
    done = set()
    for f in sorted(findings, key=lambda f: LEVELS[f.level]):
        k = (f.level, f.cat, f.msg)
        if k in done:
            continue
        done.add(k)
        n = seen[k]
        det = f'<br><span class="cat">{f.detail}</span>' if f.detail else ''
        rows.append(f'<p><span class="lv-{f.level}">{LEVEL_TR[f.level].upper()}</span> '
                    f'<span class="cat">{E(f.cat)}</span> — {E(f.msg)}{" ×" + str(n) if n > 1 else ""}{det}</p>')
    return ''.join(rows)


def _rt_html(rt, marks=None):
    h = rt.to_html(marks or [])
    return h.replace('<mark class="h">', '<span class="h">').replace('<mark class="u">', '<span class="u">') \
            .replace('<mark class="o">', '<span class="o">').replace('</mark>', '</span>')


def detail(A, item):
    """(html, düzeltilmiş RText ya da None, stil anahtarı)"""
    fixed = None
    style = 'dipnot'
    parts = [CSS]
    from . import model as _m
    parts[0] = _m.CSS
    if item.kind == 'dipnot':
        fn = A.doc.footnotes[item.ref - 1]
        parts.append(f'<h3>Dipnot {fn.num} <span class="cat">{E(fn.heading)}</span></h3>')
        parts.append(f'<p class="lbl">TEZDEKİ HÂLİ</p><div class="cite now">{_rt_html(fn.rt, _marks(item.findings))}</div>')
        if A.fn_ops.get(fn.num):
            fixed = A.fixed_footnote(fn.num)
            if fixed.text != fn.rt.text or fixed.ital != fn.rt.ital:
                parts.append(f'<p class="lbl">OLMASI GEREKEN</p><div class="cite fix">{_rt_html(fixed)}</div>')
            else:
                fixed = None
        parts.append(_flist(item.findings) or '<p>Bu dipnotta bulgu yok.</p>')
        # gövde bağlamı
        if fn.para >= 0:
            p = A.doc.body[fn.para]
            t = p.rt.text
            a = max(0, t.rfind('. ', 0, max(0, fn.pos - 260)) + 2 if fn.pos > 260 else 0)
            b = t.find('. ', fn.pos + 1)
            b = len(t) if b < 0 else min(len(t), b + 1)
            ctx = E(t[a:fn.pos]) + f'<span class="ref"><sup>▲{fn.num}</sup></span>' + E(t[fn.pos:b])
            parts.append(f'<p class="lbl">METİNDEKİ BAĞLAMI</p><p class="ctx">{"…" if a else ""}{ctx}{"…" if b < len(t) else ""}</p>'
                         f'<p class="legend">▲ işareti dipnotun metindeki yerini gösterir; hata vurgusu değildir.</p>')
        for s, loc, form in item.sources:
            first = A.src_first.get(s.sid)
            parts.append(f'<p class="mono">{s.sid} · {s.tip} · {"tam" if form == "tam" else "kısa"} · {E(loc)} · '
                         f'tezde ilk {first}. dipnot · dosya: {E(s.dosya or "—")}</p>')
    elif item.kind == 'govde':
        p = A.doc.body[item.ref]
        style = 'govde'
        parts.append(f'<h3>Paragraf {item.ref + 1} <span class="cat">{E(p.heading)}</span></h3>')
        parts.append(f'<div class="cite now">{_rt_html(p.rt, _marks(item.findings))}</div>')
        if A.body_ops.get(item.ref):
            fixed = A.fixed_body(item.ref)
            parts.append(f'<p class="lbl">OLMASI GEREKEN</p><div class="cite fix">{_rt_html(fixed)}</div>')
        parts.append(_flist(item.findings))
    elif item.kind == 'kaynakca':
        e = item.ref
        style = 'kaynakca'
        parts.append(f'<h3>Kaynakça · {e.source.sid} <span class="cat">Excel {e.first_num}. dipnot'
                     f'{" · ilk 500 satır (gözle kontrol edilmiş)" if e.verified else ""}</span></h3>')
        parts.append(f'<p class="lbl">EXCEL’DEKİ HÂLİ</p><div class="cite now">{_rt_html(e.old)}</div>')
        parts.append(f'<p class="lbl">YENİ KAYNAKÇADAKİ HÂLİ</p><div class="cite fix">{_rt_html(e.new)}</div>')
        fixed = e.new
        parts.append(_flist(item.findings))
    elif item.kind == 'eski':
        style = 'kaynakca'
        parts.append('<h3>Eski Word kaynakçası</h3>')
        parts.append(f'<div class="cite now">{_rt_html(item.ref.rt)}</div>')
        parts.append(_flist(item.findings))
    else:
        f = item.findings[0]
        parts.append(f'<h3>{E(item.group)}</h3>')
        parts.append(_flist([f]))
    return ''.join(parts), fixed, style
