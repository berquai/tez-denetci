"""Kullanım kılavuzu: program içinde F1 ile açılır; ayrıca bağımsız HTML dosyası olarak dışa yazılabilir."""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtWidgets import QDialog, QHBoxLayout, QListWidget, QTextBrowser, QSplitter, QVBoxLayout, QLineEdit
from .. import __version__, APP_NAME, AUTHOR

SECTIONS = []   # (kimlik, başlık, html)


def S(key, title, body):
    SECTIONS.append((key, title, body))


S('giris', '1. Tez Denetçi nedir?', f'''
<p><b>{APP_NAME}</b>, bir tezin dipnotlarını, kaynakçasını ve bunlara bağlı kaynak dosyalarını <b>tutarlılık ve biçim</b>
açısından denetleyen bir masaüstü programıdır. {AUTHOR} tarafından akademik çalışmalara yardımcı olmak amacıyla
tasarlanmıştır.</p>
<p>Program tezi (Word .docx), tezin kaynak listesini (Excel “Bilgiler Listesi”) ve kaynak dosyalarının bulunduğu klasörü
birlikte okur; üçünü birbiriyle karşılaştırır ve bulduğu her sorunu:</p>
<ul><li>tezdeki hâliyle, sorunlu kısmı vurgulayarak gösterir,</li>
<li>olması gereken hâlini yazar ve tek tuşla, tezin kendi yazı tipi ve puntosuyla kopyalanabilir kılar,</li>
<li>atıf yapılan kaynağı, atıf yapılan sayfada açar,</li>
<li>açık Word belgesinde ilgili dipnota götürür.</li></ul>
<p><b>Program hiçbir dosyayı değiştirmez.</b> Düzeltmeyi Word’de siz yaparsınız; program yalnızca okur, gösterir ve önerir.
İnternete bağlanmaz.</p>
<p class="not"><b>Neyi denetlemez?</b> Bir atfın kaynakta gerçekten söylenip söylenmediğini, yani içerik doğruluğunu denetlemez;
bunun için kaynak paneli sayfayı önünüze getirir, değerlendirme size aittir. Genel yazım (imla) denetimi yapmaz; Word’ün
yazım denetimi bu işi görür.</p>''')

S('kurulum', '2. Kurulum', '''
<h4>Taşınabilir sürüm (kurulum gerektirmez)</h4>
<p><code>TezDenetci_…_tasinabilir.zip</code> dosyasını istediğiniz bir klasöre (ya da USB belleğe) çıkarın ve
<code>TezDenetci.exe</code>’yi çalıştırın. Ayarlar programın yanındaki <code>ayarlar.ini</code> dosyasına yazılır; bilgisayarda
iz bırakmaz. Klasörü başka bilgisayara taşıdığınızda ayarlar da gelir.</p>
<h4>Kurulum paketi</h4>
<p><code>TezDenetci_…_Kurulum.exe</code>’yi çalıştırın. Yönetici izni istemez; program kullanıcı klasörünüze kurulur, Başlat
menüsüne ve isterseniz masaüstüne kısayol eklenir. Denetim Masası › Programlar’dan kaldırılabilir; kaldırırken ayarlarınızın
silinip silinmeyeceği sorulur.</p>
<h4>Windows “bilgisayarınız korundu” uyarısı</h4>
<p>Program dijital imzalı olmadığı için Windows ilk çalıştırmada uyarabilir: <b>Ek bilgi › Yine de çalıştır</b>.</p>''')

S('dosyalar', '3. İlk açılış: üç dosya', '''
<p>Araç çubuğundaki üç düğmeyle sırayla seçin. Seçimler hatırlanır; sonraki açılışlarda program kendiliğinden tarar.</p>
<h4>Tez (.docx)</h4>
<p>Tezin tamamı tek bir Word dosyası olmalı ve dipnotlar Word’ün kendi dipnot özelliğiyle (Başvurular › Dipnot Ekle)
eklenmiş olmalıdır. Tez Word’de açıkken de seçilebilir ve taranabilir.</p>
<h4>Bilgiler Listesi (.xlsx)</h4>
<p>Tezde kullanılan kaynakların listesidir. İlk sayfanın ilk satırı başlıktır; sütunlar:</p>
<table><tr><th>A</th><td>Dipnot numarası</td></tr>
<tr><th>B</th><td>Tam dipnot (kaynağın ilk geçtiği yer)</td></tr>
<tr><th>C</th><td>Kısa dipnot</td></tr>
<tr><th>D</th><td>Kaynakça girdisi</td></tr>
<tr><th>E</th><td>Kaynak dosyasına köprü (ör. “KAYNAK GÖSTER”)</td></tr>
<tr><th>F</th><td>Dosya adı</td></tr></table>
<p>Bir dipnotta birden çok kaynak varsa, ek kaynaklar numarasız ek satırlara yazılır. Kaynakların kimliği <b>kaynakça
girdisinden</b> belirlenir; aynı PDF’i paylaşan farklı bölümler (ör. bir derleme kitabın bölümleri) ayrı kaynak sayılır.</p>
<h4>Kaynak klasörü</h4>
<p>Kaynak PDF’lerinin (ve Word/Excel/resim kaynakların) bulunduğu klasör, ör. <i>Tüm Kaynaklar</i>. Excel’deki köprüler
bu klasöre göre çözülür. Köprü kırıksa program dosyayı adından bulmaya çalışır ve bunu bildirir.</p>''')

S('ekran', '4. Ekranın bölümleri', '''
<ul>
<li><b>Araç çubuğu:</b> dosya seçimi, Tara (F5), Otomatik izle, Doğrusunu kopyala, Word’de göster, Dışa aktar ve iki görünüm
(Bulgular / Dipnot Atlası).</li>
<li><b>Bulgular paneli (sol):</b> bulgular gruplar hâlinde: Dipnotlar, Gövde, Kaynakça, Excel, Dosyalar. Üstte arama kutusu,
düzey kutuları (Hata/Uyarı/Öneri/Bilgi), kategori seçimi, “Temiz dipnotlar” (bulgusu olmayanları da göster) ve
“İncelenenler” (incelendi olarak işaretlediklerinizi de göster). Her kaydın yanındaki renkli nokta en ağır bulgusunu gösterir.</li>
<li><b>Ayrıntı paneli (orta):</b> seçili kaydın <i>tezdeki hâli</i> (sorunlu kısım renkli vurgulu), <i>olması gereken</i> hâli,
bulgular ve — dipnotlarda — dipnotun <i>metindeki bağlamı</i>. Bağlamdaki <b>▲</b> işareti dipnot numarasının metindeki yerini
gösterir; hata vurgusu değildir. Altta: Doğrusunu kopyala, Word’de göster, Dipnot metnine git, ✓ İncelendi.</li>
<li><b>Kaynak paneli (sağ):</b> atıf yapılan kaynak dosyası. Ayrıntısı 8. bölümde.</li>
<li><b>Dipnot Atlası (sol, sekme):</b> bütün dipnotların listesi. Ayrıntısı 9. bölümde.</li>
<li><b>Durum çubuğu (alt):</b> son taramanın saati ve tezin son kaydedildiği saat, toplam sayılar, önceki taramaya göre
yeni/giderilmiş bulgu sayısı ve sağda “İncelenen: x / y kayıt”.</li></ul>
<p>Paneller başlıklarından sürüklenerek yer değiştirebilir; başlığa çift tıklanınca ayrı pencere olur (örneğin kaynak
panelini ikinci ekrana almak için). Görünüm menüsünden gizlenip açılabilir.</p>''')

S('duzey', '5. Bulgu düzeyleri', '''
<table>
<tr><th class="h">Hata</th><td>Kesin kural ihlali: düzeltilmesi gerekir. Örnek: kaynağın ilk geçtiği yerde kısa dipnot.</td></tr>
<tr><th class="u">Uyarı</th><td>Büyük olasılıkla sorun ya da tutarsızlık; bakıp karar verin. Örnek: aynı kaynağın kısa dipnotunun iki
farklı biçimde yazılması.</td></tr>
<tr><th class="o">Öneri</th><td>Kural ihlali değil, iyileştirme. Örnek: aynı dipnottaki kaynakları virgül yerine noktalı virgülle ayırmak.</td></tr>
<tr><th class="b">Bilgi</th><td>Bilgilendirme; varsayılan olarak gizlidir. Örnek: Word’deki metin Excel’deki biçimden farklı.</td></tr>
</table>''')

S('denetim', '6. Denetimler', '''
<p>Program bazı “ev kurallarını” tezin kendi çoğunluk kullanımından çıkarır (ör. “X, vd.” mi “X vd.” mi); bu kabuller
HTML raporun <i>Kurallar</i> sekmesinde görünür.</p>
<h4>İlk kullanım</h4>
<p>Bir kaynak tezde ilk kez geçtiği dipnotta <b>tam</b>, sonrakilerde <b>kısa</b> dipnotla verilmelidir. Paragraflar yer
değiştirince bu sıra bozulabilir; program sırayı her taramada baştan hesaplar ve doğru biçimi (sayfa numarasını koruyarak) önerir.</p>
<h4>Birleştirme</h4>
<p>Aynı paragrafta <b>art arda iki cümlede</b> aynı kaynağa ayrı dipnot verilmişse <b>Hata</b> (tek dipnotta birleşmeli:
“s. 44-45” ya da “s. 145, 162”); aynı cümlede iki ayrı dipnot varsa <b>Uyarı</b>.</p>
<h4>Kısa dipnot tutarlılığı</h4>
<p>Aynı kaynağın kısa dipnotu tezin farklı yerlerinde farklı yazılmışsa (ör. bir yerde “Kalkınma Politika ve Uygulamaları”,
öbüründe virgülü tırnağın içinde) bildirir.</p>
<h4>İtalik</h4>
<ul><li>Kitap, dergi, gazete, rapor adları ve <i>Resmî Gazete / Resmî Ceride</i> italik; makale başlıkları tırnak içinde düz;
kanun ve karar adları düz.</li>
<li>İtalik adın ardından gelen ek ve noktalama düz yazılır: <i>Ülkü</i>’de, <i>Kadro</i>, …</li>
<li>Başlığın içindeki parantez ve tırnak işaretlerinin italik olup olmaması serbesttir.</li>
<li>Program italiği Word’ün bütün yollarıyla okur: doğrudan verilen italik, “Vurgu” gibi karakter biçemleri ve
alıntı paragrafı gibi paragraf biçemleri.</li></ul>
<h4>Büyük harf</h4>
<p>Başlıklarda her kelime büyük harfle başlar; <i>ve, ile, veya, ya da, de/da, ki, mi</i> ile İngilizce bağlaç, edat ve
tanımlıklar küçük kalır (başlığın ve iki noktadan sonraki ilk kelime hariç). <i>için, gibi, kadar, göre, dair, içinde</i>
serbesttir. <b>Gazete manşetleri muaftır:</b> kaynakta nasıl yazılmışsa öyle kalır.</p>
<h4>Tırnak ve kesme</h4>
<p>Tezde yalnızca eğri tırnak ve kesme kullanılır: “ ” ‘ ’. Düz işaretler (" '), kesme yerine kullanılan ´ ` ′, kelime
içindeki açılış tırnağı (Türkiye‘de) ve yönü ters tırnaklar bildirilir. Web adresleri ve DOI’ler muaftır. Programdan
kopyalanan ya da dışa aktarılan her metin de son anda bu kurala göre düzeltilir.</p>
<h4>Noktalama</h4>
<p>Tırnağın içinde kalan virgül ya da nokta (“…Uygulamaları,”), sayfa numarasından sonra “.,”, “s.” ile sayı arasında
boşluk eksikliği, nokta ile bitmeyen dipnot, tarih ile bağlantı adresi arasında boşluk eksikliği.</p>
<h4>Biçim tutarlılığı</h4>
<p>“X, vd.” / “X vd.”, “Kanun No.” / “Kanun No:”, dipnot metninin başındaki boşluk, sayfa aralığında kısa/uzun tire
gibi kullanımlarda tezin çoğunluğundan ayrılan yerler.</p>
<h4>Künye</h4>
<p>Tez künyelerinde enstitü, anabilim dalı ve şehir bilgisinin bulunması; dergi cilt numarasının yılla aynı olması
(“C. 2005, … 2005” — künyeyi PDF’ten kontrol edin).</p>
<h4>Sayfa</h4>
<p>Dipnottaki sayfa, makalenin kaynakçadaki sayfa aralığının dışındaysa (ör. s. 279-309 aralığındaki bir makaleye s. 312) ya
da aralık ters yazılmışsa (s. 45-41) bildirir.</p>
<h4>Yazım</h4>
<p>İngilizce kelimede Türkçe noktalı İ (<i>İnternational</i>) ve künyedeki bir kelimenin kaynak dosyasının adında bir harf farklı
geçmesi (<i>Sructuralism / structuralism</i>) — hangisinin yanlış olduğunu siz belirlersiniz.</p>
<h4>Sahte dipnot numarası</h4>
<p>Dipnot numarası gibi görünen ama Word’ün dipnot bağlantısı olmayan rakamlar: üst simge biçimli rakam (başka belgeden
kopyalanınca dipnotun kopması), ¹² gibi üst simge karakterleri ve noktaya yapışık rakam (“kuruldu.17 Ardından”).
Gerçek dipnotlar kelimeden, virgülden ya da noktadan sonra gelebilir; bunların yeri denetlenmez.</p>
<h4>Çoklu atıf</h4>
<p>Aynı dipnotta aynı kaynağın iki kez geçmesi (sayfalar birleştirilebilir) ve birden çok kaynağın virgülle ayrılması
(noktalı virgül önerisi).</p>
<h4>Kütük farkı (Bilgi)</h4>
<p>Word’deki dipnot metni Excel’deki kayıttan farklıysa, farkı harf harf gösterir.</p>''')

S('kaynakca', '6a. Kaynakça ve Excel denetimleri', '''
<h4>Kaynakça grubu</h4>
<p>Kaynakça, Word’deki mevcut kaynakçadan değil, Excel listesinin <b>kaynakça sütunundan yeniden üretilir</b>: Türkçe abece
sırasıyla, isimsiz gazete haberleri başta, aynı ilk yazarda tek yazarlı eserler önce. Üretilirken yalnızca kesin düzeltmeler
otomatik uygulanır (görünmez karakter, düz tırnak, <i>Resmî Gazete</i> italiği, tamamen düz kalmış dergi/kitap adı, büyük
harf) ve her biri <b>“Otomatik”</b> diye listelenir. Emin olunamayan durumlar <b>“Kontrol et”</b> olarak işaretlenir (ör. kitap
bölümünde sayfa aralığının eksik olması). Word’deki eski kaynakçada olup Excel’de bulunmayan girdiler <b>“Kütükte yok”</b>
olarak ayrıca gösterilir: tezde hâlâ kullanılıyorlarsa Excel’e eklenmelidir. Yeni kaynakça Dışa aktar › Word ile tezin kendi
kaynakça biçemiyle alınır.</p>
<h4>Excel grubu</h4>
<p>Excel listesinin <b>tamamı</b> için (kısaltılmış bir tez taransa bile) bulgular: hücrede düz kalmış başlıklar, büyük harf,
aynı kaynağın kısa dipnotunun farklı yazılışları, düz tırnaklar, “ve”/“vd.” kullanımı, aynı kaynağın farklı dosya adlarıyla
bağlanması, Excel’de kaynağın ilk kullanımında tam dipnotun boş olması.</p>
<h4>Dosyalar grubu</h4>
<p><b>Kırık köprü:</b> kaynağın dosyası klasörde yok (Hata), köprü açılmıyor ama dosya adından bulundu ya da en benzer dosya
kullanıldı (Uyarı). <b>Atıfsız dosya</b> (Bilgi): klasörde olup hiçbir kaynağa bağlı olmayan dosyalar.</p>''')

S('calisma', '7. Bir bulguyla çalışmak', '''
<ol>
<li>Soldan kaydı seçin (↑/↓ ile gezinebilirsiniz). Ortada sorun vurgulanır; altta bulgular ve açıklamaları.</li>
<li><b>Doğrusunu kopyala</b> (Ctrl+Shift+C) → Word’de ilgili dipnotu seçip <b>Ctrl+V</b>. Metin italikleriyle ve tezin kendi
dipnot (ya da kaynakça/gövde) yazı tipi ve puntosuyla yapışır.</li>
<li><b>Word’de göster</b> (Ctrl+Shift+W): açık Word belgesinde dipnot numarasının metindeki yerini seçer ve durum çubuğunda kaçıncı
sayfada olduğunu yazar. <b>Dipnot metnine git</b> sayfa altındaki dipnot metnini seçer. Word kapalıysa belgeyi açar.
Gövde bulgularında ilgili paragrafı bulur. Tarama sonrası belge değiştiyse doğru dipnotu metninden tanır.</li>
<li><b>✓ İncelendi</b> (Ctrl+D): kayıt işaretlenir, listeden gizlenir ve sıradakine geçilir. Yeniden basınca işaret kalkar.
İşaretler dipnot numarasına değil <b>metnine</b> bağlıdır: araya dipnot girse de yerinde kalır; dipnotu düzelttiğinizde metin
değiştiği için yeniden incelemeye düşer (hata giderildiyse zaten listeden kalkar).</li>
</ol>
<p><b>Arama:</b> Ctrl+F ile kutuya yazar, başlık ya da kelime yazın. Düzey kutuları ve kategori listesiyle daraltın.</p>''')

S('kaynak', '8. Kaynak paneli ve sayfa kayması', '''
<p>Seçili dipnotun kaynağı burada açılır: PDF atıf yapılan sayfada; Word ve Excel kaynaklar önizlemede; resimler resim olarak.
Dipnotta birden çok kaynak varsa üstteki listeden seçilir. ↗ düğmesi dosyayı kendi programında açar.</p>
<h4>Basılı sayfa, PDF sayfası ve kayma</h4>
<p>Dipnottaki “s. 293” kaynağın <b>basılı</b> sayfasıdır; PDF dosyasının kendi sayfa sırası çoğu zaman farklıdır (bir dergi
makalesi 279. sayfadan başlar, bir kitabın önsöz sayfaları vardır). Aradaki farka <b>kayma</b> denir:</p>
<p class="formul">PDF sayfası = basılı sayfa − kayma</p>
<ul><li><b>Basılı s.:</b> gidilecek basılı sayfa (dipnottan otomatik gelir).</li>
<li><b>Kayma:</b> program önce makalenin kaynakçadaki sayfa aralığına, sonra PDF sayfalarının altındaki/üstündeki numaralara
bakarak tahmin eder; nasıl bulduğunu bilgi satırında yazar.</li>
<li><b>PDF s.:</b> PDF dosyasının kendi sayfası; yanında “51 / 72 · basılı ≈ 39” ve PDF’in içinde tanımlıysa sayfa etiketi.</li>
<li><b>Kaymayı buradan hesapla:</b> PDF yanlış sayfada açıldıysa doğru sayfaya gelin, o sayfanın basılı numarasını “Basılı s.”
kutusuna yazın ve bu düğmeye basın. Kayma o kaynak için kalıcı olarak kaydedilir. Taranmış (metin içermeyen) PDF’lerde bu
bir kez gerekir.</li></ul>''')

S('atlas', '9. Dipnot Atlası görünümü', '''
<p><b>Dipnot Atlası</b> (F9), Bulgular’dan farklı olarak hatalı ya da hatasız <b>bütün dipnotları</b> numara sırasıyla listeler:
numara, dipnot metni, kaynak, sayfa ve dipnotun bulunduğu bölüm. Bir satıra tıklayınca ortada dipnot ve metindeki bağlamı,
sağda kaynak atıf yapılan sayfada açılır.</p>
<p><b>Ne işe yarar?</b> Tezin bütün atıf ağına anında erişim sağlar. Örneğin <b>tez savunmasında</b> jüri “85. dipnottaki
bilgiyi nereden aldınız?” diye sorduğunda Ctrl+G ile 85’i yazmanız yeterlidir: kaynak, ilgili sayfasıyla önünüzdedir.
Danışman görüşmelerinde ya da bir bölümü yeniden okurken de aynı biçimde kullanılır.</p>
<p>Arama kutusuna numara (ör. 142), yazar, eser adı ya da kelime yazılabilir. Satır başındaki nokta o dipnotun en ağır
bulgusunu, ✓ incelendiğini gösterir. Bulgular görünümüne F8 ile dönülür.</p>''')

S('izle', '10. Otomatik izleme ve sürüm farkı', '''
<p><b>Otomatik izle</b> açıkken tez ya da Excel her kaydedildiğinde birkaç saniye sonra yeniden taranır. Durum çubuğunda
taramanın saati, tezin son kaydedildiği saat ve önceki taramaya göre <b>kaç yeni, kaç giderilmiş</b> bulgu olduğu yazar.
Böylece Word’de yaptığınız düzeltmenin taramaya girip girmediğini bir bakışta görürsünüz. İstediğiniz an F5 ile de taranır.</p>''')

S('iki', '11. İki bilgisayarda çalışma', '''
<p>Çalışma durumu — incelendi işaretleri, son baktığınız kayıt, PDF kaymaları ve tema — tezin yanında
<code>&lt;tez adı&gt;.tezdenetci.json</code> dosyasında tutulur ve her değişiklikte kaydedilir.</p>
<ul><li><b>Tez bir bulut klasöründeyse</b> (Google Drive, OneDrive…) bu dosya da eşitlenir: öbür bilgisayarda programı açtığınızda
kaldığınız kayıttan devam edersiniz. İki bilgisayarda yapılan işaretler birleştirilir; biri ötekini ezmez, geri aldığınız
işaret geri gelmez.</li>
<li><b>Bulut kullanmıyorsanız:</b> Dosya › Çalışma durumunu dışa aktar → dosyayı taşıyın → öbür bilgisayarda Dosya › Çalışma
durumunu içe aktar.</li>
<li>Yeni bilgisayarda yalnızca tezi, listeyi ve klasörü bir kez seçmeniz yeterlidir. Dosyanın yeri: Dosya › Çalışma durumu
dosyasının yerini göster.</li></ul>''')

S('disari', '12. Dışa aktarımlar', '''
<ul><li><b>HTML rapor:</b> bütün bulgular, her biri doğrusu ve italikli kopyala düğmesiyle; Excel ↔ Word karşılaştırması ve
programın uyguladığı kuralların listesi. Tarayıcıda açılır, paylaşılabilir.</li>
<li><b>Excel:</b> Word’den yeniden üretilmiş dipnot listesi (Bilgiler Listesi düzeninde, hücre içi italikli, köprülü, “olması
gereken” sütunuyla) ve Kaynak Kütüğü.</li>
<li><b>Word — yeni kaynakça:</b> kütükten üretilen kaynakça, tezin kendi kaynakça biçemi ve KAYNAKLAR başlığıyla.</li></ul>''')

S('tema', '13. Temalar', '''
<p>Görünüm › Tema: Kâğıt, Sepya, Bulut, Gece, Gece Mavisi, Orman, Yüksek Kontrast ve renklerini kendinizin seçtiği Özel tema.
Ctrl+T sıradaki temaya geçer. Bütün hazır temalarda yazı/zemin karşıtlığı ekran okunurluk ölçütünü (WCAG: normal metin
en az 4,5:1) karşılar.</p>''')

S('kisayol', '14. Kısayollar', '''
<table>
<tr><th>F1</th><td>Kullanım kılavuzu</td></tr>
<tr><th>F5</th><td>Yeniden tara</td></tr>
<tr><th>F8 / F9</th><td>Bulgular görünümü / Dipnot Atlası görünümü</td></tr>
<tr><th>Ctrl+F</th><td>Ara</td></tr>
<tr><th>Ctrl+G</th><td>Dipnot numarasına git</td></tr>
<tr><th>Ctrl+D</th><td>İncelendi olarak işaretle ve sıradakine geç / geri al</td></tr>
<tr><th>Ctrl+Shift+C</th><td>Doğrusunu kopyala</td></tr>
<tr><th>Ctrl+Shift+W</th><td>Word’de göster</td></tr>
<tr><th>Ctrl+T</th><td>Sıradaki tema</td></tr>
<tr><th>↑ / ↓</th><td>Listede gezin</td></tr></table>''')

S('sss', '15. Sık sorulanlar ve sorun giderme', '''
<h4>Word’de düzelttim ama bulgu duruyor.</h4>
<p>Durum çubuğundaki “tarandı” ve “tezin son kaydı” saatlerine bakın: tez kaydedilmemişse ya da tarama kaydı görmemişse F5’e
basın. Dipnotu düzelttikten sonra Word’de <b>kaydetmeyi</b> unutmayın.</p>
<h4>Bir bulgunun yanlış olduğunu düşünüyorum.</h4>
<p>Kuralların bir kısmı sezgiseldir (ör. bir kitap başlığının nerede bittiği). Kaydı ✓ İncelendi ile işaretleyip geçin; tekrar
eden bir yanlışsa ekran görüntüsüyle program yazarına bildirin.</p>
<h4>PDF yanlış sayfada açılıyor.</h4>
<p>8. bölümdeki “Kaymayı buradan hesapla” adımını bir kez uygulayın.</p>
<h4>“Word’de göster” çalışmıyor.</h4>
<p>Microsoft Word kurulu olmalıdır. Tez başka bir adla kaydedildiyse programda Tez (.docx) ile yeniden seçin.</p>
<h4>Dosyalar grubunda çok sayıda kırık köprü var.</h4>
<p>Kaynak klasörünün doğru seçildiğinden emin olun. Excel köprüleri Excel dosyasının bulunduğu klasöre göre çözülür; klasör
yapısı değiştiyse program dosyaları adlarından bulmaya çalışır ve bunu “Uyarı” olarak bildirir.</p>
<h4>Tarama başarısız oldu.</h4>
<p>Word tezi tam o anda kaydediyor olabilir; birkaç saniye sonra F5’e basın.</p>''')

S('lisans', '16. Gizlilik ve lisans', f'''
<p>Program belgelerinizi yalnızca okur; hiçbir dosyayı değiştirmez ve internete bağlanmaz. “Word’de göster” Word’de
yalnızca imleci taşır, metne dokunmaz.</p>
<p>Copyright © 2026 {AUTHOR}. {APP_NAME}, GNU Affero Genel Kamu Lisansı sürüm 3 ya da sonrası (AGPL-3.0-or-later) ve
NOTICE dosyasındaki ek koşullar kapsamında dağıtılan özgür bir yazılımdır. Yazar atfı ve telif bildirimleri kaldırılamaz;
değiştirilmiş sürümler değiştirildiklerini belirtmelidir. Program başkasına verilirken kaynak kodu da verilmelidir.
Ayrıntılar: Yardım › Lisans ve Bildirimler.</p>''')


CSS = '''
body{font-family:"Segoe UI",sans-serif;font-size:10.5pt;line-height:150%}
h2{font-family:Georgia,serif}
h3{font-family:Georgia,serif;margin-top:22px}
h4{margin-bottom:2px}
table{border-collapse:collapse}
th{text-align:left;padding:3px 12px 3px 0;vertical-align:top;white-space:nowrap}
td{padding:3px 0}

code{font-family:Consolas,monospace}
.not{padding:6px 10px;border-left:3px solid #b49a3a}
.formul{font-family:Georgia,serif;font-size:12pt;font-weight:bold;padding-left:14px}
'''


def full_html(standalone=False):
    head = f'<h2>{APP_NAME} — Kullanım Kılavuzu</h2><p>Sürüm {__version__} · {AUTHOR}</p>'
    toc = '<p>' + '<br>'.join(f'<a href="#{k}">{t}</a>' for k, t, _ in SECTIONS) + '</p>'
    body = ''.join(f'<a name="{k}"></a><h3 id="{k}">{t}</h3>{b}' for k, t, b in SECTIONS)
    if not standalone:
        return f'<html><head><style>{CSS}</style></head><body>{head}{body}</body></html>'
    page_css = CSS + '''
:root{color-scheme:light dark}
body{max-width:860px;margin:0 auto;padding:24px 18px 80px;background:#fffaf0;color:#302e29}
@media (prefers-color-scheme: dark){body{background:#202124;color:#eee5d5}a{color:#d8b867}}
a{color:#7a3b1d}'''
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{APP_NAME} Kullanım Kılavuzu</title><style>{page_css}</style></head><body>{head}'
            f'<h3>İçindekiler</h3>{toc}{body}</body></html>')


class ManualDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{APP_NAME} — Kullanım Kılavuzu')
        self.resize(1000, 720)
        lay = QVBoxLayout(self)
        self.find = QLineEdit()
        self.find.setPlaceholderText('Kılavuzda ara…')
        self.find.returnPressed.connect(self._find)
        lay.addWidget(self.find)
        sp = QSplitter()
        self.toc = QListWidget()
        for k, t, _ in SECTIONS:
            self.toc.addItem(t)
        self.toc.currentRowChanged.connect(lambda r: self.go(SECTIONS[r][0]) if r >= 0 else None)
        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)
        self.view.setHtml(full_html())
        sp.addWidget(self.toc)
        sp.addWidget(self.view)
        sp.setSizes([260, 740])
        lay.addWidget(sp, 1)

    def go(self, key):
        self.view.scrollToAnchor(key)

    def _find(self):
        if not self.view.find(self.find.text()):
            c = self.view.textCursor()
            c.movePosition(c.MoveOperation.Start)
            self.view.setTextCursor(c)
            self.view.find(self.find.text())
