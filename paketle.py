"""Tez Denetçi paketleyicisi.

Kullanım (proje klasöründe):  python paketle.py
Çıktılar 'cikti' klasörüne yazılır:
  TezDenetci_<sürüm>_Tasinabilir.zip   — kurulum gerektirmez; ayarlar programın yanında tutulur
  TezDenetci_<sürüm>_Kurulum.exe       — Inno Setup kuruluysa (https://jrsoftware.org/isdl.php)
  kaynak_kod.zip                        — AGPL gereği programla birlikte verilecek kaynak kod
"""
import os
import shutil
import subprocess
import sys
import zipfile

KOK = os.path.dirname(os.path.abspath(__file__))
os.chdir(KOK)
sys.path.insert(0, KOK)

DISLA = ['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'PySide6.Qt3DCore',
         'PySide6.Qt3DRender', 'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtQuick3D', 'PySide6.QtMultimedia',
         'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtGraphs', 'PySide6.QtLocation',
         'PySide6.QtPositioning', 'PySide6.QtBluetooth', 'PySide6.QtSensors', 'PySide6.QtSerialPort',
         'PySide6.QtDesigner', 'PySide6.QtSql', 'PySide6.QtTest', 'tkinter', 'matplotlib', 'numpy', 'pandas',
         'PIL', 'cv2', 'pymupdf', 'fitz']


def adim(m):
    print(f'\n=== {m}', flush=True)


def surum_bilgisi(ver):
    a, b, c = (ver.split('.') + ['0', '0'])[:3]
    metin = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0), mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041F04B0', [
      StringStruct('CompanyName', 'Berkay Çelik'),
      StringStruct('FileDescription', 'Tez Denetçi — dipnot, kaynakça ve biçim denetimi'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'TezDenetci'),
      StringStruct('LegalCopyright', 'Copyright (C) 2026 Berkay Çelik — AGPL-3.0-or-later'),
      StringStruct('OriginalFilename', 'TezDenetci.exe'),
      StringStruct('ProductName', 'Tez Denetçi'),
      StringStruct('ProductVersion', '{ver}'),
      StringStruct('Comments', 'Berkay Çelik tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmıştır.')])]),
    VarFileInfo([VarStruct('Translation', [0x041F, 1200])])
  ]
)
"""
    with open('version_info.txt', 'w', encoding='utf-8') as fh:
        fh.write(metin)


def zip_klasor(kaynak, hedef, kok_adi):
    with zipfile.ZipFile(hedef, 'w', zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(kaynak):
            for f in files:
                p = os.path.join(root, f)
                z.write(p, os.path.join(kok_adi, os.path.relpath(p, kaynak)))


def kaynak_kod_zip(hedef):
    dahil = ['tezdenetci', 'baslat.py', 'requirements.txt', 'LICENSE.txt', 'NOTICE.txt', 'BENIOKU.txt', 'README.md',
             '.gitignore', 'paketle.py', 'kurulum', '.github', 'kurulum.bat', 'baslat.bat', 'paketle.bat']
    with zipfile.ZipFile(hedef, 'w', zipfile.ZIP_DEFLATED) as z:
        for d in dahil:
            if os.path.isfile(d):
                z.write(d, os.path.join('TezDenetci', d))
            elif os.path.isdir(d):
                for root, dirs, files in os.walk(d):
                    dirs[:] = [x for x in dirs if x != '__pycache__']
                    for f in files:
                        p = os.path.join(root, f)
                        z.write(p, os.path.join('TezDenetci', p))


def iscc_bul():
    adaylar = [os.path.join(os.environ.get(v, ''), 'Inno Setup 6', 'ISCC.exe')
               for v in ('ProgramFiles(x86)', 'ProgramFiles', 'LOCALAPPDATA')]
    adaylar.append(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe'))
    return next((a for a in adaylar if a and os.path.isfile(a)), shutil.which('ISCC') or shutil.which('iscc'))


def main():
    import tezdenetci
    from tezdenetci.app.manual import full_html
    ver = tezdenetci.__version__
    print(f'Tez Denetçi {ver} paketleniyor…')
    for d in ('build', 'dist', 'cikti'):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs('cikti')
    surum_bilgisi(ver)
    with open('Kullanim_Kilavuzu.html', 'w', encoding='utf-8') as fh:
        fh.write(full_html(True))

    adim('1/4 Program derleniyor (PyInstaller)')
    import PyInstaller.__main__ as pyi
    sep = ';' if os.name == 'nt' else ':'
    args = ['--noconfirm', '--windowed', '--name', 'TezDenetci', '--icon', os.path.join('tezdenetci', 'resources', 'tezdenetci.ico'),
            '--add-data', f'{os.path.join("tezdenetci", "resources")}{sep}{os.path.join("tezdenetci", "resources")}',
            '--collect-submodules', 'tezdenetci']
    if os.name == 'nt':
        args += ['--version-file', 'version_info.txt', '--hidden-import', 'win32com.client',
                 '--hidden-import', 'win32gui', '--hidden-import', 'win32con']
    for m in DISLA:
        args += ['--exclude-module', m]
    pyi.run(args + ['baslat.py'])
    prog = os.path.join('dist', 'TezDenetci')
    for f in ('LICENSE.txt', 'NOTICE.txt', 'Kullanim_Kilavuzu.html'):
        shutil.copy(f, prog)

    adim('2/4 Kaynak kod arşivi')
    kaynak_kod_zip(os.path.join('cikti', 'kaynak_kod.zip'))
    shutil.copy(os.path.join('cikti', 'kaynak_kod.zip'), prog)

    adim('3/4 Taşınabilir sürüm')
    tas = os.path.join('build', 'tasinabilir', 'TezDenetci')
    shutil.copytree(prog, tas)
    with open(os.path.join(tas, 'TASINABILIR.txt'), 'w', encoding='utf-8') as fh:
        fh.write('Bu dosya Tez Denetçi’nin taşınabilir kipte çalışmasını sağlar: ayarlar bu klasördeki ayarlar.ini\n'
                 'dosyasına yazılır, bilgisayarda iz bırakılmaz. Silerseniz program ayarlarını Windows’a yazar.\n')
    zip_klasor(tas, os.path.join('cikti', f'TezDenetci_{ver}_Tasinabilir.zip'), 'TezDenetci')

    adim('4/4 Kurulum paketi (Inno Setup)')
    iscc = iscc_bul()
    if iscc:
        subprocess.check_call([iscc, f'/DAppVer={ver}', os.path.join('kurulum', 'TezDenetci.iss')])
    else:
        print('Inno Setup bulunamadı; kurulum paketi atlandı. Kurmak için: https://jrsoftware.org/isdl.php\n'
              '(Taşınabilir sürüm hazır.)')

    print('\nBitti. Çıktılar:')
    for f in sorted(os.listdir('cikti')):
        print('  cikti' + os.sep + f, f'({os.path.getsize(os.path.join("cikti", f)) // 1048576} MB)')


if __name__ == '__main__':
    main()
