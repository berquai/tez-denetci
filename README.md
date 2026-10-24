# Tez Denetçi

Tezin dipnotlarını, kaynakçasını ve kaynak dosyalarını tutarlılık ve biçim açısından denetleyen bir Windows masaüstü programı.

Berkay Çelik tarafından akademik çalışmalara yardımcı olmak amacıyla tasarlanmış ve geliştirilmiştir.

## Neler yapar?

- **Dipnot denetimi:** İlk atıfta tam künye, sonraki atıflarda kısa biçim sırasını; italikleri, büyük harf kurallarını, sayfa aralıklarını ve tırnak işaretlerini denetler.
- **Birleştirme kuralı:** Aynı paragrafta art arda aynı kaynağa yapılan atıfların tek dipnotta birleştirilmesi gerektiğini bildirir.
- **Sahte dipnot numarası avı:** Word dipnotuna bağlı olmayan üst simge rakamları ve metne yapışık numaraları yakalar.
- **Kaynak Kütüğü:** Excel'deki kaynak listesiyle tezdeki atıfları eşleştirir; kaynakçayı bu listeden yeniden üretir.
- **Kaynak görüntüleyici:** Bir bulguya tıklayınca atıf yapılan kaynak (PDF, Word, Excel) doğru sayfada açılır. Basılı sayfa ile PDF sayfası arasındaki kaymayı kendisi hesaplar.
- **Word bağlantısı:** Açık Word belgesinde ilgili dipnota gider ve kaçıncı sayfada olduğunu söyler.
- **Dipnot Atlası (F9):** Bütün dipnotların aranabilir listesi; tez savunması için.
- **Otomatik izleme:** Word ya da Excel'de her kaydedişte yeniden tarar.
- **Dışa aktarma:** HTML rapor, Excel dipnot listesi ve Word kaynakça.

Program belgelerinizi **yalnızca okur**; hiçbir dosyayı değiştirmez ve internete bağlanmaz.

## İndirme

Hazır programı [Releases](https://github.com/berquai/tez-denetci/releases) sayfasından indirebilirsiniz:

- `TezDenetci_<sürüm>_Kurulum.exe`: Başlat menüsü ve masaüstü kısayollu kurulum (yönetici izni istemez).
- `TezDenetci_<sürüm>_Tasinabilir.zip`: Kurulum gerektirmez, USB bellekte de çalışır.

## Kaynak koddan çalıştırma

1. Python 3.10 veya üstünü kurun ([python.org](https://www.python.org/downloads/)); kurulumda "Add python.exe to PATH" kutusunu işaretleyin.
2. `kurulum.bat` dosyasına çift tıklayın (bir kez; yaklaşık 250 MB kütüphane iner).
3. `baslat.bat` ile programı açın.

Ayrıntılı kullanım için program içinde **F1** tuşuna basın ya da [BENIOKU.txt](BENIOKU.txt) dosyasına bakın.

## Paketleme

- **Kendi bilgisayarınızda:** `paketle.bat` → `cikti` klasöründe taşınabilir zip, kurulum exe'si (Inno Setup 6 kuruluysa) ve kaynak kod arşivi.
- **GitHub'da:** Actions › **Derle** › **Run workflow**. Çıktılar işin "Artifacts" bölümünden indirilir. `v1.3.0` gibi bir etiketle yeni bir sürüm (Release) oluşturulursa çıktılar o sürüme kendiliğinden eklenir.

## Gereksinimler

Windows 10/11 · Python 3.10+ · PySide6, openpyxl, lxml, python-docx, RapidFuzz, pywin32 (bkz. [requirements.txt](requirements.txt)).

## Lisans

Copyright (C) 2026 Berkay Çelik <berkcel@gmail.com>

Tez Denetçi özgür bir yazılımdır. [GNU Affero Genel Kamu Lisansı](LICENSE.txt) sürüm 3 veya sonraki sürümleri (AGPL-3.0-or-later) ve [NOTICE](NOTICE.txt) dosyasındaki ek koşullar kapsamında dağıtılır. Program HİÇBİR GARANTİ OLMAKSIZIN sunulur.

- Programı başkalarına verdiğinizde kaynak kodunu da vermelisiniz.
- Yazar atfı ve telif bildirimleri kaldırılamaz.
- Değiştirilmiş sürümler, değiştirildiklerini ve kimin tarafından değiştirildiğini açıkça belirtmelidir.

Kullanılan üçüncü taraf bileşenler ve lisansları: [tezdenetci/resources/THIRD_PARTY.txt](tezdenetci/resources/THIRD_PARTY.txt).
