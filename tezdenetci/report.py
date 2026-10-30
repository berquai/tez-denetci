"""HTML hata raporu: vurgulu metin, önerilen doğru biçim ve italikli kopyalama."""
import html
from collections import Counter, defaultdict
from datetime import datetime
from .rules import LEVELS, LEVEL_TR, _diff_html

E = html.escape


def _marks(findings):
    out = []
    for f in findings:
        if f.level == 'bilgi':
            continue
        for a, b in f.spans:
            out.append((a, b, 'm-' + f.level))
    # ağır olan üstte kalsın
    out.sort(key=lambda x: -LEVELS[x[2][2:]])
    return out


def _badge(level):
    return f'<span class="lv lv-{level}">{LEVEL_TR[level]}</span>'


def _finding_li(f, n=1):
    det = f'<div class="det">{f.detail}</div>' if f.detail else ''
    fix = ''
    if f.fix is not None:
        fix = (f'<div class="fixline"><span class="fixlbl">Eklenecek girdi</span>'
               f'<span class="cite rich">{f.fix.to_html()}</span>'
               f'<button class="copy" type="button">Kopyala</button></div>')
    return (f'<li class="f" data-level="{f.level}" data-cat="{E(f.cat)}">{_badge(f.level)}'
            f'<span class="cat">{E(f.cat)}</span><span class="msg">{E(f.msg)}{f' <span class="cnt">×{n}</span>' if n > 1 else ''}</span>{det}{fix}</li>')


STYLES = {'dipnot': ('Times New Roman', 10.0), 'kaynakca': ('Times New Roman', 11.0), 'govde': ('Times New Roman', 12.0)}


def _card(kind, ref_label, anchor, rt, fixed, findings, extra_head=''):
    font, pt = STYLES.get(kind, ('Times New Roman', 12.0))
    lv = min((LEVELS[f.level] for f in findings), default=9)
    worst = [k for k, v in LEVELS.items() if v == lv]
    worst = worst[0] if worst else 'ok'
    cats = ' '.join(sorted({f.cat for f in findings}))
    levels = ' '.join(sorted({f.level for f in findings}))
    changed = fixed is not None and (fixed.text != rt.text or fixed.ital != rt.ital)
    groups = {}
    for f in sorted(findings, key=lambda f: LEVELS[f.level]):
        key = (f.level, f.cat, f.msg, f.detail)
        groups.setdefault(key, []).append(f)
    items = ''.join(_finding_li(fs[0], len(fs)) for fs in groups.values())
    fix_html = ''
    if changed:
        fix_html = (f'<div class="fixline" data-font="{E(font)}" data-pt="{pt:g}"><span class="fixlbl">Olması gereken</span>'
                    f'<span class="cite rich">{fixed.to_html()}</span>'
                    f'<button class="copy" type="button" title="İtalikleriyle birlikte panoya kopyalar">Kopyala</button></div>')
    return (f'<article class="card w-{worst}" id="{anchor}" data-levels="{levels}" data-cats="{E(cats)}" '
            f'data-search="{E(rt.text.lower())}">'
            f'<header><span class="ref">{ref_label}</span>{extra_head}</header>'
            f'<div class="cite now">{rt.to_html(_marks(findings))}</div>'
            f'{fix_html}<ul class="fl">{items}</ul></article>')


def build_report(A, out_path, meta, styles=None):
    if styles:
        STYLES.update(styles)
    doc = A.doc
    by_fn = defaultdict(list)
    by_bib = defaultdict(list)
    by_body = defaultdict(list)
    general = []
    for f in A.findings:
        if f.where == 'dipnot':
            by_fn[f.ref].append(f)
        elif f.where == 'kaynakca':
            by_bib[f.ref].append(f)
        elif f.where == 'govde':
            if isinstance(f.ref, int) and f.cat not in ('Dipnot konumu',):
                by_body[f.ref].append(f)
            else:
                general.append(f)
        else:
            general.append(f)
    allf = A.findings + A.excel_findings
    cnt_x = Counter(f.level for f in A.excel_findings)

    # ---------------- dipnotlar
    fn_cards = []
    for f in doc.footnotes:
        fs = by_fn.get(f.num, [])
        cits = A.fn_cits.get(f.num, [])
        src = ', '.join(sorted({c.source.sid + (' tam' if c.form == 'tam' else ' kısa') for c in cits}))
        head = (f'<span class="where">{E(f.heading[:70])}</span>'
                f'<span class="src" title="Kaynak Kütüğü kimliği">{E(src)}</span>')
        fixed = A.fixed_footnote(f.num) if A.fn_ops.get(f.num) else None
        fn_cards.append(_card('dipnot', f'Dipnot {f.num}', f'dn{f.num}', f.rt, fixed, fs, head))

    gen_cards = ''.join(f'<article class="card w-{g.level}" data-levels="{g.level}" data-cats="{E(g.cat)}" data-search="{E(g.msg.lower())}">'
                        f'<ul class="fl">{_finding_li(g)}</ul></article>' for g in sorted(general, key=lambda g: LEVELS[g.level]))

    # ---------------- gövde
    body_cards = []
    for i, fs in sorted(by_body.items()):
        p = doc.body[i]
        fixed = A.fixed_body(i) if A.body_ops.get(i) else None
        body_cards.append(_card('govde', f'Paragraf {i + 1}', f'p{i}', p.rt, fixed, fs,
                                f'<span class="where">{E(p.heading[:70])}</span>'))

    # ---------------- kaynakça (kütükten yeniden üretilen)
    from .rules import Finding
    bib_cards = []
    bib_findings = []
    for e in A.bibliography:
        fs = [Finding('oneri', 'Otomatik düzeltme', 'kaynakca', e.source.sid, 'Otomatik: ' + ch) for ch in e.changes]
        fs += [Finding('uyari', 'Kontrol et', 'kaynakca', e.source.sid, fl) for fl in e.flags]
        if not fs:
            continue
        bib_findings += fs
        head = (f'<span class="where">{"İlk 500 satır · gözle kontrol edilmiş bölge" if e.verified else ""}</span>'
                f'<span class="src">{E(e.source.sid)} · Excel {e.first_num}. dipnot</span>')
        bib_cards.append(_card('kaynakca', 'Kaynakça', f'k{e.source.sid}', e.old, e.new, fs, head))
    for b in A.word_only:
        f0 = Finding('uyari', 'Kütükte yok', 'kaynakca', None,
                     'Eski Word kaynakçasında var ama Excel kütüğünde yok. Tezde hâlâ atıf alıyorsa Excel’e eklenmeli; yoksa yeni kaynakçaya girmeyecek.')
        bib_findings.append(f0)
        bib_cards.append(_card('kaynakca', 'Eski kaynakça', 'kw', b.rt, None, [f0], ''))
    full_bib = ''.join(f'<p class="bibp">{e.new.to_html()}</p>' for e in A.bibliography)
    caps_only = []

    # ---------------- excel
    ex_groups = defaultdict(list)
    for f in A.excel_findings:
        ex_groups[f.cat].append(f)
    ex_html = []
    for cat, fs in sorted(ex_groups.items(), key=lambda x: (min(LEVELS[f.level] for f in x[1]), x[0])):
        lv = min(fs, key=lambda f: LEVELS[f.level]).level
        items = ''.join(_finding_li(f) for f in sorted(fs, key=lambda f: LEVELS[f.level]))
        ex_html.append(f'<details class="grp" {"open" if len(fs) <= 12 else ""}><summary>{_badge(lv)}<b>{E(cat)}</b>'
                       f'<span class="n">{len(fs)}</span></summary><ul class="fl">{items}</ul></details>')

    # ---------------- senkron
    sync_rows = ''.join(f'<tr><td class="num"><a href="#dn{n}" data-tab="t-fn">{n}</a></td><td>{_diff_html(e, w)}</td></tr>'
                        for n, w, e in A.sync)

    # ---------------- kurallar
    m = A.maj
    rules_html = f'''
<div class="rules">
<p>Motor bazı ev kurallarını tezin kendi çoğunluk kullanımından çıkarır. Aşağıdakiler bu taramada tespit edilen “doğru” kabulleridir:</p>
<table class="kv">
<tr><th>Dipnot metninin başı</th><td>{'Boşlukla başlar' if m['lead_space'] else 'Boşluksuz başlar'}</td></tr>
<tr><th>Dipnot numarasının yeri</th><td>Noktalamadan {'sonra' if m['ref_pos'] == 'after' else 'önce'} ({m['ref_counts'].get('after', 0)} / {m['ref_counts'].get('before', 0)})</td></tr>
<tr><th>Kesme işareti</th><td>{E(m['apos'])}</td></tr>
<tr><th>“vd.” öncesi</th><td>{'virgüllü: “X, vd.”' if m['vd'] == ',' else 'virgülsüz: “X vd.”'} ({m['vd_counts'].get(',', 0)} / {m['vd_counts'].get(' ', 0)})</td></tr>
<tr><th>Kısa dipnotta iki yazar</th><td>{'virgülle: “Doğan, Yardımcı”' if m['kisa_authors'] == ',' else '“ve” ile'} ({m['kisa_author_counts'].get(',', 0)} / {m['kisa_author_counts'].get('ve', 0)})</td></tr>
<tr><th>Kanun numarası</th><td>“Kanun No{E(m['kanun_no'])}” ({m['kanun_no_counts'].get('.', 0)} / {m['kanun_no_counts'].get(':', 0)})</td></tr>
<tr><th>Sayfa aralığı</th><td>kısa tire (s. 12-15)</td></tr>
</table>
<p>Senin koyduğun kurallar:</p>
<ul class="plain">
<li>İlk kullanımda tam dipnot, sonrakilerde kısa dipnot.</li>
<li>Aynı paragrafta ardışık cümlelerde aynı kaynak → tek dipnot (s. 44-45 / s. 145, 162).</li>
<li>Başlıklarda her kelime büyük harfle; <i>ve, ile, veya, ya da, de/da, ki, mi</i> ve İngilizce bağlaç/edat/tanımlıklar küçük. <i>için, gibi, kadar, göre, dair, içinde</i> serbest bırakıldı.</li>
<li>Kitap, dergi, gazete, rapor adları ve <i>Resmî Gazete / Resmî Ceride</i> italik; makale başlıkları tırnak içinde düz; kanun adları düz.</li>
<li>İtalik adın ardından gelen ek ve noktalama düz; tırnak işaretleri düz. Başlığın parçası olan parantezler serbest.</li>
<li>Gazete manşetleri kaynaktaki gibi kalır (büyük harf ve yazım denetimi yapılmaz).</li>
<li>Tez künyelerinde enstitü, anabilim dalı ve şehir bulunur (danışman isteği).</li>
<li>Şehir adı yok; “izlek” yasak.</li>
</ul>
<p class="note">Başlığın nerede bittiği sezgisel bulunur; bu yüzden kaynakçada yalnızca <b>tamamen düz yazılmış</b> başlıklar otomatik italikleştirilir, senin verdiğin italiklere dokunulmaz.</p>
</div>'''

    n_fn_err = sum(1 for f in doc.footnotes if by_fn.get(f.num))
    allf = allf + bib_findings
    cnt = Counter(f.level for f in A.findings + bib_findings)
    cats_all = sorted({f.cat for f in allf})
    cat_chips = ''.join(f'<button class="chip" data-cat="{E(c)}" type="button">{E(c)}</button>' for c in cats_all)

    def stat(label, n, cls):
        return f'<div class="stat {cls}"><b>{n}</b><span>{label}</span></div>'

    tpl = TEMPLATE
    page = (tpl.replace('%%TITLE%%', 'Tez Denetim Raporu')
            .replace('%%META%%', E(meta))
            .replace('%%DATE%%', datetime.now().strftime('%d.%m.%Y %H:%M'))
            .replace('%%STATS%%', stat('Hata', cnt.get('hata', 0), 's-hata') + stat('Uyarı', cnt.get('uyari', 0), 's-uyari') +
                     stat('Öneri', cnt.get('oneri', 0), 's-oneri') + stat('Bilgi', cnt.get('bilgi', 0), 's-bilgi'))
            .replace('%%SUMMARY%%', SUMMARY_FN(A, n_fn_err, len(caps_only)))
            .replace('%%CHIPS%%', cat_chips)
            .replace('%%FNSTYLE%%', E(f"{STYLES['dipnot'][0]} {STYLES['dipnot'][1]:g} pt"))
            .replace('%%N_FN%%', str(n_fn_err))
            .replace('%%N_BODY%%', str(len(body_cards) + sum(1 for g in general if g.where == 'govde')))
            .replace('%%N_BIB%%', str(len(bib_cards)))
            .replace('%%N_BIBALL%%', str(len(A.bibliography)))
            .replace('%%BIBFULL%%', full_bib)
            .replace('%%BIBFONT%%', E(STYLES['kaynakca'][0])).replace('%%BIBPT%%', f"{STYLES['kaynakca'][1]:g}")
            .replace('%%N_EX%%', str(len(A.excel_findings)))
            .replace('%%N_SYNC%%', str(len(A.sync)))
            .replace('%%FN%%', gen_cards.replace('data-levels', 'data-gen="1" data-levels') + ''.join(fn_cards))
            .replace('%%BODY%%', ''.join(body_cards) + ''.join(
                f'<article class="card w-{g.level}" data-levels="{g.level}" data-cats="{E(g.cat)}" data-search="{E(g.msg.lower())}"><ul class="fl">{_finding_li(g)}</ul></article>'
                for g in general if g.where == 'govde'))
            .replace('%%BIB%%', ''.join(bib_cards))
            .replace('%%BIBCAPS%%', ''.join(caps_only))
            .replace('%%N_BIBCAPS%%', str(len(caps_only)))
            .replace('%%EX%%', ''.join(ex_html))
            .replace('%%EXCNT%%', f'{cnt_x.get("hata", 0)} hata · {cnt_x.get("uyari", 0)} uyarı')
            .replace('%%SYNC%%', sync_rows)
            .replace('%%RULES%%', rules_html))
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(page)


def SUMMARY_FN(A, n_fn_err, n_caps):
    doc = A.doc
    first_err = sum(1 for f in A.findings if f.cat == 'İlk kullanım')
    merge = sum(1 for f in A.findings if f.cat == 'Birleştirme' and f.level == 'hata')
    it_fn = sum(1 for f in A.findings if f.cat == 'İtalik' and f.where == 'dipnot' and f.level == 'hata')
    caps_fn = sum(1 for f in A.findings if f.cat == 'Büyük harf' and f.where == 'dipnot')
    return f'''
<ul class="sum">
<li><b>{len(doc.footnotes)}</b> dipnotun tamamı Kaynak Kütüğü’ndeki <b>{len(A.sources)}</b> kaynaktan biriyle eşleşti; <b>{n_fn_err}</b> dipnotta en az bir bulgu var.</li>
<li>İlk kullanım / kısa dipnot sırası: <b>{'temiz' if not first_err else str(first_err) + ' hata'}</b>.</li>
<li>Danışman birleştirme kuralı: <b>{merge}</b> dipnot çifti birleştirilmeli.</li>
<li>Dipnotlarda <b>{it_fn}</b> italik hatası, <b>{caps_fn}</b> büyük harf hatası.</li>
<li>Kaynakça kütükten yeniden üretildi: <b>{len(A.bibliography)}</b> girdi, <b>{sum(1 for e in A.bibliography if e.changes)}</b> girdide otomatik düzeltme, <b>{sum(1 for e in A.bibliography if e.flags)}</b> girdi kontrol bekliyor; eski Word kaynakçasında olup kütükte bulunmayan <b>{len(A.word_only)}</b> girdi var.</li>
<li>Excel listesi Word’ün <b>{len(A.sync)}</b> dipnotta gerisinde.</li>
</ul>'''


def _group_bib(A):
    g = defaultdict(list)
    for f in A.findings:
        if f.where == 'kaynakca':
            g[f.ref].append(f)
    return g


TEMPLATE = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%%TITLE%%</title>
<style>
:root{
  --bg:#f6f4ef; --panel:#fffdf9; --ink:#1f1d1a; --mute:#6b665e; --line:#e3ddd2; --accent:#7a3b1d;
  --hata:#b42318; --hata-bg:#fde7e4; --uyari:#a15c00; --uyari-bg:#fff1d6; --oneri:#2f5f8a; --oneri-bg:#e3eef8;
  --bilgi:#5b5f66; --bilgi-bg:#eceef0; --ok:#2e6b3f; --fix-bg:#eef6ee; --mark-h:#f9c9c3; --mark-u:#ffe0a3; --mark-o:#cfe2f3; --mark-b:#dfe2e6;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --bg:#171614; --panel:#201f1c; --ink:#ece8e1; --mute:#a59f95; --line:#34312c; --accent:#e0a37f;
  --hata:#ff8a7a; --hata-bg:#3a1f1c; --uyari:#f2b45c; --uyari-bg:#3a2c14; --oneri:#8cbcea; --oneri-bg:#1b2a38;
  --bilgi:#b7bcc4; --bilgi-bg:#2a2d31; --ok:#86c79a; --fix-bg:#1c2a20; --mark-h:#6b2a23; --mark-u:#5e4417; --mark-o:#23405c; --mark-b:#3a3e44;}}
:root[data-theme="dark"]{
  --bg:#171614; --panel:#201f1c; --ink:#ece8e1; --mute:#a59f95; --line:#34312c; --accent:#e0a37f;
  --hata:#ff8a7a; --hata-bg:#3a1f1c; --uyari:#f2b45c; --uyari-bg:#3a2c14; --oneri:#8cbcea; --oneri-bg:#1b2a38;
  --bilgi:#b7bcc4; --bilgi-bg:#2a2d31; --ok:#86c79a; --fix-bg:#1c2a20; --mark-h:#6b2a23; --mark-u:#5e4417; --mark-o:#23405c; --mark-b:#3a3e44;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px 16px 80px}
h1{font:600 26px/1.2 Georgia,"Times New Roman",serif;margin:0 0 4px;letter-spacing:-.01em}
.meta{color:var(--mute);font-size:13px;margin-bottom:18px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;border-top:3px solid}
.stat b{display:block;font-size:24px;font-variant-numeric:tabular-nums}
.stat span{color:var(--mute);font-size:13px}
.s-hata{border-top-color:var(--hata)}.s-uyari{border-top-color:var(--uyari)}.s-oneri{border-top-color:var(--oneri)}.s-bilgi{border-top-color:var(--bilgi)}
.sum{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px 12px 34px;margin:0 0 18px}
.sum li{margin:3px 0}
nav.tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin-bottom:12px;position:sticky;top:0;background:var(--bg);z-index:5;padding-top:6px}
nav.tabs button{border:0;background:none;color:var(--mute);padding:9px 12px;font:inherit;cursor:pointer;border-bottom:2px solid transparent}
nav.tabs button.on{color:var(--ink);border-bottom-color:var(--accent);font-weight:600}
nav.tabs .c{font-size:12px;color:var(--mute);margin-left:4px}
.tools{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0 14px}
.tools input[type=search]{flex:1 1 220px;min-width:0;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--panel);color:var(--ink);font:inherit}
.lvf label{font-size:13px;margin-right:8px;white-space:nowrap}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.chip{border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:999px;padding:3px 10px;font-size:12.5px;cursor:pointer}
.chip.on{background:var(--accent);color:var(--panel);border-color:var(--accent)}
section.tab{display:none}section.tab.on{display:block}
.card{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}
.card.w-hata{border-left-color:var(--hata)}.card.w-uyari{border-left-color:var(--uyari)}.card.w-oneri{border-left-color:var(--oneri)}.card.w-bilgi{border-left-color:var(--bilgi)}
.card header{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;margin-bottom:6px}
.ref{font-weight:700}
.where{color:var(--mute);font-size:13px}
.src{color:var(--mute);font-size:12px;font-family:ui-monospace,Menlo,Consolas,monospace;margin-left:auto}
.cite{font-family:"Times New Roman",Georgia,serif;font-size:16px;line-height:1.55;overflow-wrap:anywhere}
.cite i{font-style:italic}
.now{padding:6px 8px;border-radius:6px;background:color-mix(in srgb,var(--bg) 60%,var(--panel))}
mark{border-radius:3px;padding:0 1px;color:inherit}
mark.m-hata{background:var(--mark-h)}mark.m-uyari{background:var(--mark-u)}mark.m-oneri{background:var(--mark-o)}mark.m-bilgi{background:var(--mark-b)}
.fixline{display:flex;gap:10px;align-items:flex-start;margin-top:8px;padding:8px;border-radius:6px;background:var(--fix-bg)}
.fixlbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--ok);font-weight:700;white-space:nowrap;padding-top:3px}
.fixline .cite{flex:1;min-width:0}
button.copy{border:1px solid var(--ok);background:transparent;color:var(--ok);border-radius:6px;padding:4px 10px;font:600 12.5px system-ui,sans-serif;cursor:pointer;white-space:nowrap}
button.copy.done{background:var(--ok);color:var(--panel)}
ul.fl{list-style:none;margin:8px 0 0;padding:0}
li.f{padding:4px 0;border-top:1px dashed var(--line);display:flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}
li.f:first-child{border-top:0}
.lv{font-size:11px;font-weight:700;border-radius:4px;padding:1px 6px;text-transform:uppercase;letter-spacing:.04em}
.lv-hata{color:var(--hata);background:var(--hata-bg)}.lv-uyari{color:var(--uyari);background:var(--uyari-bg)}.lv-oneri{color:var(--oneri);background:var(--oneri-bg)}.lv-bilgi{color:var(--bilgi);background:var(--bilgi-bg)}
.cat{font-size:12px;color:var(--mute)}
.msg{flex:1 1 300px}
.det{flex-basis:100%;font-size:13px;color:var(--mute);padding:4px 0 2px}
.diff{font-family:"Times New Roman",Georgia,serif;font-size:14.5px;color:var(--ink)}
.diff div{margin:2px 0}
.d-del{background:var(--mark-h);text-decoration:line-through;text-decoration-thickness:1px}
.d-ins{background:var(--mark-o)}
details.grp{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 10px;padding:8px 14px}
details.grp summary{cursor:pointer;display:flex;gap:10px;align-items:center}
details.grp .n{margin-left:auto;color:var(--mute);font-variant-numeric:tabular-nums}
.cnt{color:var(--mute);font-size:12px}
table.sync{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:10px}
table.sync td{border-top:1px solid var(--line);padding:8px 10px;vertical-align:top}
td.num{width:48px;font-weight:700}
a{color:var(--accent)}
.kv{border-collapse:collapse;margin:8px 0 14px}
.bibp{margin:0 0 6px;padding-left:2em;text-indent:-2em}
.kv th{text-align:left;font-weight:600;padding:4px 16px 4px 0;color:var(--mute)}
.kv td{padding:4px 0}
.rules{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 18px}
.note{color:var(--mute);font-size:13.5px}
.hint{color:var(--mute);font-size:13.5px;margin:0 0 12px}
.hide{display:none!important}
.theme{margin-left:auto;border:1px solid var(--line);background:var(--panel);color:var(--ink);border-radius:8px;padding:6px 10px;cursor:pointer;font:inherit;font-size:13px}
@media (max-width:640px){.stats{grid-template-columns:repeat(2,1fr)}.src{margin-left:0}.fixline{display:grid;grid-template-columns:1fr auto;align-items:center}.fixline .cite{grid-column:1/-1;grid-row:2}}
</style>
</head>
<body>
<div class="wrap">
<div style="display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap">
<div><h1>Tez Denetim Raporu</h1><div class="meta">%%META%% · %%DATE%%</div></div>
<button class="theme" type="button" id="theme">Tema</button>
</div>
<div class="stats">%%STATS%%</div>
%%SUMMARY%%
<nav class="tabs" id="tabs">
<button type="button" data-t="t-fn" class="on">Dipnotlar<span class="c">%%N_FN%%</span></button>
<button type="button" data-t="t-body">Gövde<span class="c">%%N_BODY%%</span></button>
<button type="button" data-t="t-bib">Kaynakça<span class="c">%%N_BIB%%</span></button>
<button type="button" data-t="t-ex">Excel (tüm tez)<span class="c">%%N_EX%%</span></button>
<button type="button" data-t="t-sync">Excel ↔ Word<span class="c">%%N_SYNC%%</span></button>
<button type="button" data-t="t-rules">Kurallar</button>
</nav>
<div class="tools">
<input type="search" id="q" placeholder="Ara: yazar, başlık, kelime…">
<span class="lvf">
<label><input type="checkbox" data-lv="hata" checked> Hata</label>
<label><input type="checkbox" data-lv="uyari" checked> Uyarı</label>
<label><input type="checkbox" data-lv="oneri" checked> Öneri</label>
<label><input type="checkbox" data-lv="bilgi"> Bilgi</label>
<label><input type="checkbox" id="clean"> Temiz dipnotları da göster</label>
</span>
</div>
<div class="chips" id="chips">%%CHIPS%%</div>

<section class="tab on" id="t-fn">
<p class="hint">Kırmızı: kesin hata · turuncu: uyarı · mavi: öneri. “Kopyala” düğmesi düzeltilmiş metni italikleriyle ve tezin kendi yazı tipi/puntosuyla (dipnot %%FNSTYLE%%) kopyalar; Word’de doğrudan <b>Ctrl+V</b> yeterli.</p>
%%FN%%
</section>
<section class="tab" id="t-body">%%BODY%%</section>
<section class="tab" id="t-bib">
<p class="hint">Word’deki eski kaynakça yok sayıldı; kaynakça Excel kütüğünün kaynakça sütunundan <b>yeniden üretildi</b> (%%N_BIBALL%% girdi, Türkçe abece, isimsiz gazete haberleri başta, aynı yazarda tek yazarlı eserler önce). Kesin düzeltmeler (görünmez karakter, Resmî Gazete italiği, tamamen düz kalmış dergi/kitap adı, büyük harf) otomatik uygulandı ve aşağıda tek tek listelendi; emin olunamayanlar yalnızca <b>Kontrol et</b> olarak işaretlendi. Gazete manşetlerine dokunulmadı. Tamamı <b>Kaynakca.docx</b> dosyasında tezin kendi “akaynaka” biçemiyle hazır.</p>
%%BIB%%
<details class="grp"><summary><span class="lv lv-bilgi">Tam</span><b>Yeni kaynakçanın tamamı</b><span class="n">%%N_BIBALL%%</span></summary>
<div class="fixline" data-font="%%BIBFONT%%" data-pt="%%BIBPT%%"><span class="fixlbl">Tümü</span><div class="cite rich bibfull">%%BIBFULL%%</div><button class="copy" type="button">Kopyala</button></div>
</details>
</section>
<section class="tab" id="t-ex"><p class="hint">Excel listesinin tamamı (%%EXCNT%%). Bu bulgular tezin bütününe ait; kısaltılmış Word metniyle sınırlı değil.</p>%%EX%%</section>
<section class="tab" id="t-sync"><p class="hint">Aynı numaralı dipnotun Word’deki ve Excel’deki hâli farklı. Excel’in gerisinde kaldığı yerler: <span class="d-del">silinen</span> → <span class="d-ins">Word’deki</span>.</p>
<table class="sync">%%SYNC%%</table></section>
<section class="tab" id="t-rules">%%RULES%%</section>
<footer style="margin-top:28px;padding-top:12px;border-top:1px solid var(--line);color:var(--mute);font-size:12.5px">
Tez Denetçi · Berkay Çelik tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmıştır · AGPL-3.0-or-later</footer>
</div>
<script>
(function(){
  var root=document.documentElement;
  var tbtn=document.getElementById('theme');
  try{var s=localStorage.getItem('tdr-theme'); if(s) root.setAttribute('data-theme',s);}catch(e){}
  tbtn.addEventListener('click',function(){
    var cur=root.getAttribute('data-theme');
    var dark=cur?cur==='dark':matchMedia('(prefers-color-scheme: dark)').matches;
    var nx=dark?'light':'dark'; root.setAttribute('data-theme',nx);
    try{localStorage.setItem('tdr-theme',nx);}catch(e){}
  });
  var tabs=document.querySelectorAll('#tabs button');
  function show(id){tabs.forEach(function(b){b.classList.toggle('on',b.dataset.t===id)});
    document.querySelectorAll('section.tab').forEach(function(s){s.classList.toggle('on',s.id===id)});}
  tabs.forEach(function(b){b.addEventListener('click',function(){show(b.dataset.t)})});
  document.querySelectorAll('a[data-tab]').forEach(function(a){a.addEventListener('click',function(){show(a.dataset.tab)})});
  var q=document.getElementById('q'), clean=document.getElementById('clean');
  var lvs=document.querySelectorAll('[data-lv]'); var cat=null;
  document.querySelectorAll('.chip').forEach(function(c){c.addEventListener('click',function(){
    cat=(cat===c.dataset.cat)?null:c.dataset.cat;
    document.querySelectorAll('.chip').forEach(function(x){x.classList.toggle('on',x.dataset.cat===cat)}); apply();})});
  function apply(){
    var on={}; lvs.forEach(function(l){on[l.dataset.lv]=l.checked});
    var term=(q.value||'').toLocaleLowerCase('tr');
    document.querySelectorAll('li.f').forEach(function(li){
      var ok=on[li.dataset.level] && (!cat||li.dataset.cat===cat);
      li.classList.toggle('hide',!ok);});
    document.querySelectorAll('article.card').forEach(function(card){
      var items=card.querySelectorAll('li.f'); var vis=0;
      items.forEach(function(li){if(!li.classList.contains('hide'))vis++});
      var hit=!term||(card.dataset.search||'').indexOf(term)>=0||card.textContent.toLocaleLowerCase('tr').indexOf(term)>=0;
      var show=hit&&(vis>0||(items.length===0&&clean.checked&&!cat));
      card.classList.toggle('hide',!show);});
    document.querySelectorAll('details.grp li.f').forEach(function(li){
      if(term&&li.textContent.toLocaleLowerCase('tr').indexOf(term)<0) li.classList.add('hide');});
  }
  q.addEventListener('input',apply); lvs.forEach(function(l){l.addEventListener('change',apply)}); clean.addEventListener('change',apply);
  apply();
  function copyRich(node,btn){
    var line=node.closest('[data-pt]');
    var font=line?line.dataset.font:'Times New Roman', pt=line?line.dataset.pt:'10';
    var clone=node.cloneNode(true);
    clone.querySelectorAll('mark').forEach(function(m){m.replaceWith(document.createTextNode(m.textContent))});
    var paras=clone.querySelectorAll('p');
    var inner;
    var sty='font-family:\''+font+'\';font-size:'+pt+'pt';
    if(paras.length){
      inner=[].map.call(paras,function(p){return '<p style="margin:0;'+sty+'">'+p.innerHTML+'</p>'}).join('');
    } else {
      inner='<span style="'+sty+'">'+clone.innerHTML+'</span>';
    }
    var htmlStr='<html><body><!--StartFragment-->'+inner+'<!--EndFragment--></body></html>';
    var text=paras.length?[].map.call(paras,function(p){return p.textContent}).join('\r\n'):clone.textContent;
    function handler(e){e.clipboardData.setData('text/html',htmlStr);e.clipboardData.setData('text/plain',text);e.preventDefault();}
    document.addEventListener('copy',handler);
    var ok=false;
    try{ok=document.execCommand('copy');}catch(err){}
    document.removeEventListener('copy',handler);
    if(!ok&&navigator.clipboard&&window.ClipboardItem){
      navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([htmlStr],{type:'text/html'}),'text/plain':new Blob([text],{type:'text/plain'})})]);
    }
    btn.classList.add('done');btn.textContent='Kopyalandı';setTimeout(function(){btn.classList.remove('done');btn.textContent='Kopyala'},1600);
  }
  document.addEventListener('click',function(e){
    var b=e.target.closest('button.copy'); if(!b) return;
    var node=b.parentNode.querySelector('.rich'); if(node) copyRich(node,b);
  });
})();
</script>
</body>
</html>'''
