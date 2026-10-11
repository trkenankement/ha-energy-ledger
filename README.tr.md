# Energy Ledger — aylık fatura takibi

[English guide](README.md)

Elektrik, doğalgaz ve su faturalarının aylık tüketimini ve tutarını Home Assistant içinde kaydedin; ardından Enerji ekranında tüketim ve maliyet olarak görüntüleyin. Banka/bulut hesabı veya akıllı sayaç gerekmez.

Bu bir **özel entegrasyondur**; resmi Home Assistant entegrasyonu veya Supervisor uygulaması değildir. 0.4.0, tam yedek sonrasında canlı Home Assistant 2026.10.1 sistemine kuruldu ve kabul edildi. Güncelleme ve yeniden başlatma boyunca 36 faturanın, altı özet toplamın ve altı Recorder istatistiğinin tamamı korundu. HACS özel depo kurulumu daha önce 0.2.0 ile doğrulandı; canlı 0.4.0 yükseltmesi elle yapıldı ve 0.4.0 artık HACS özel depoları için yayımlandı.

## 1. Neleri kaydeder?

| Kaynak | Tüketim birimi | Maliyet |
| --- | --- | --- |
| Elektrik | kWh | Seçilen para birimi |
| Doğalgaz | m³ | Seçilen para birimi |
| Su | m³ | Seçilen para birimi |

Her kaynak ve muhasebe ayı için tek kayıt tutulur. Aynı ayı tekrar girmek eski kaydı değiştirir; iki kez toplamaz. Altı özet varlık kaydedilmiş toplamları gösterir; geçmiş tüketim ve maliyet ayrıca Recorder istatistiklerine yazılır.

Faturada birimini doğruladığınız tüketimi girin. kWh olarak faturalanan gaz otomatik olarak m³'e çevrilmez. Eksik fatura, sıfır tüketim demek değildir.

## 2. Kurulum

HA 2026.10 veya üzeri, etkin Recorder ve tam saat UTC ofsetli saat dilimi gerekir. Para birimi ve saat dilimi ilk kurulumda sabitlenir. TRY, EUR, USD ve GBP desteklenir. Entegrasyon ek pip paketi kurmaz; HA'nın sağladığı kütüphaneleri kullanır.

Önce tam HA yedeği alın.

Güncellemede kararlı `energy_ledger.<config-entry-id>` saklama anahtarı korunur. 0.4.0 mevcut defterin tamamını doğrular, Store `1.1` verisini `1.2` biçimine taşır ve ancak bundan sonra atomik olarak yazar. Faturaların yeniden girilmesi gerekmez. Güncelleme için entegrasyonu kaldırıp tekrar eklemeyin: bileşen dosyalarını değiştirin, HA'yı yeniden başlatın, kayıt sayısı ile aylık/yıllık toplamları doğrulayın. Geri dönüş için güncelleme öncesi yedeği saklayın; eski entegrasyon gelecekteki bir saklama şemasını anlayamayabilir.

### Manuel kurulum

1. [ha-energy-ledger](https://github.com/trkenankement/ha-energy-ledger) deposundan kaynak dosyalarını indirin.
2. `custom_components/energy_ledger` klasörünü yapısını koruyarak `/config/custom_components/` içine kopyalayın.
3. HA'yı yeniden başlatın.
4. **Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → Energy Ledger** yolundan para birimini seçin.

### HACS özel deposu

Depo herkese açıktır; HACS'ın varsayılan kataloğunda değildir. Kurulum yolu **HACS → Özel depolar → depo adresi → Integration → indir → yeniden başlat** şeklindedir. Bu yol v0.2.0 ile doğrulandı. Kurulum GitHub'dan kod indirir, faturalarınızı göndermez. Otomatik `git pull` yapılmaz.

## 3. Fatura ekleme ve düzeltme

1. Entegrasyonun **Yapılandır** menüsünden **Fatura ekle / düzelt** seçin.
2. Kaynağı ve muhasebe ayını `YYYY-MM` biçiminde girin: örneğin `2026-01`.
3. Aylık tüketim ve toplam fatura tutarını yazın. Ondalık virgül veya nokta kullanılabilir; binlik ayırıcı kullanmayın. Değerler 0–1.000.000.000 arasında, en fazla altı ondalık basamaklı olmalıdır.
4. Yeni/eski değerleri inceleyip onaylayın. Onaylamadan formu kapatmak kaydetmez.

Ödeme/vade ayını otomatik olarak tüketim ayı kabul etmeyin. İki aya yayılan fatura için muhasebe ayını sizin seçmeniz gerekir; entegrasyon dönem tahmini veya orantılı dağıtım yapmaz. Bu ay ve önceki 119 ay girilebilir.

Düzeltmek için aynı kaynağı ve ayı tekrar girin. Silmek için **Fatura sil** menüsünden kaydı seçip onaylayın. Yalnız Energy Ledger istatistikleri yeniden hesaplanır; diğer entegrasyonların geçmişi değiştirilmez. Eski istatistikleri sıfırlamak için yerelde sıfır değerli silme işareti tutulur. Bu işlem Recorder geçmişi veya yedeklerden güvenli veri imhası değildir.

### Birden fazla faturayı aktarma

Yapılandır menüsünden **Toplu fatura aktar** seçip noktalı virgülle ayrılmış satırları yapıştırın. Başlık tam olarak `kind;month;unit;consumption;cost` olmalıdır. `electricity` için `kWh`, `gas`/`water` için `m3` (veya `m³`) kullanın. Tutarlar kurulumda seçilen para birimindedir. Ondalık virgül kabul edilir.

Onaylamadan önce her satırı inceleyin. Bütün satırlar kayıttan önce doğrulanır; aynı aktarımda tekrarlanan kaynak/ay reddedilir. Mevcut kaynak/ay değiştirilir; aktarımda olmayan aylar korunur. En fazla 360 satır ve 65.536 karakter kabul edilir. Recorder yayını yerel kayıttan sonra yapılır; bu atomik bir veritabanı işlemi değildir ve kesilen yayın açılışta yeniden oluşturulur.

## 4. Enerji ekranına bağlama

Faturayı kaydettikten sonra Recorder kuyruğunun işlenmesini bekleyin. **Ayarlar → Panolar → Enerji** içinde elektrik/gaz/su kaynağını yapılandırırken aşağıdaki istatistikleri seçin:

| Kaynak | Tüketim istatistiği | Maliyet istatistiği |
| --- | --- | --- |
| Elektrik | `energy_ledger:electricity_consumption` | `energy_ledger:electricity_cost` |
| Doğalgaz | `energy_ledger:gas_consumption` | `energy_ledger:gas_cost` |
| Su | `energy_ledger:water_consumption` | `energy_ledger:water_cost` |

Maliyet takibinde ilgili toplam maliyet istatistiğini kullanın. Bunlar dış istatistiklerdir; altı özet sensörden farklıdır. Kaynak için henüz fatura kaydedilmediyse seçim listesinde görünmeyebilir.

**Aylık veya yıllık görünümü kullanın.** Aylık tüketimin/tutarın tamamı seçilen ayın ilk saatine yazılır. Günlük/saatlik grafikte görülen sıçrama gerçek günlük kullanım değil, muhasebe kaydıdır. Hayali günlük dağılım oluşturulmaz.

Elektrik faturası evin şebeke toplamıdır; akıllı prizler cihaz alt kırılımıdır. Aynı tüketimi hem ölçüm hem fatura olarak iki şebeke kaynağına eklemek çift sayım yapar.

## 5. Mahremiyet ve erişim

Entegrasyonda bulut istemcisi, telemetri veya dış ağ bağlantısı kodu yoktur. Kayıtlar HA'nın `.storage` dosyasında, Recorder istatistiklerinde ve yedeklerinde tutulur. Özet sensörler toplamları, fatura sayısını ve son muhasebe ayını gösterir; tam fatura satırlarını artık yayımlamaz. Kurulum/güncelleme araçları ve diğer HA entegrasyonları internete çıkabilir; bu uygulama güvenlik duvarı değildir. Canlı paket yakalama yapılmış olduğu iddia edilmez.

Yerel saklama, yalnız yöneticinin görebildiği veya bu bileşen tarafından şifrelenen saklama anlamına gelmez. Özet durumlarını okuyabilen HA kullanıcıları/istemcileri toplamları, kayıt sayılarını ve son ayları görebilir. 0.2.x ile oluşmuş Recorder geçmişi ve eski yedekler tam fatura özelliklerini hâlâ içerebilir. Yapılandırma formları HA'nın yönetici yetkilerine dayanır. HA erişimini, dosyaları ve yedekleri koruyun; gerçek faturaları, `.storage`, parolaları veya yedek arşivlerini GitHub'a koymayın.

Entegrasyonu kaldırmak kayıtları ve Recorder geçmişini otomatik temizlemez.

## 6. Sınırlar ve sorun giderme

- Tek hane, kaynak başına tek aylık kayıt desteklenir. Çoklu sayaç, tarife hesabı, döviz dönüşümü ve PDF okuma yoktur.
- Para birimi/saat dilimi değişikliği geçmiş kayıtları yeniden değerlemez. Tam saat olmayan saat dilimleri reddedilir.
- İstatistikler başlangıç, her fatura ayı ve son tamamlanan saat için seyrek kümülatif noktalar kullanır. 0.2.x yükseltmesinde yalnız altı Energy Ledger istatistiği temizlenip yeniden kurulur; fatura kayıtları ve diğer istatistikler korunur. Store `1.1` → `1.2` geçişi her kaydı doğrular ve taşınan veriyi atomik yazar. Yükseltmeden önce yedek alın; sonra kayıt sayısını ve aylık/yıllık toplamları yeniden kontrol edin.
- Tek aktarım en fazla 360 satırdır. Kayan 120 aylık giriş penceresinin eski geçerli kayıtları düşürmemesi için kalıcı yerel defterin ayrı 10.000 kayıt güvenlik sınırı vardır.
- Boş kayıt defterindeki sıfır toplam, evin hiç tüketmediğini göstermez.
- İstatistik görünmüyorsa kaydın onaylandığını ve Recorder'ın çalıştığını kontrol edin; HA günlüklerinde `energy_ledger` arayın. Sorun ararken diğer çalışan Enerji kaynaklarını değiştirmeyin.

## 7. Test ve geliştirme

Depo kökünde sentetik birim ve kontrat testleri:

```sh
python -m unittest discover -s tests -v
```

Testler düzeltme, tekrar giriş, silme, bağımsız aylık toplamlar, hatalı girdiler, seyrek uzun geçmiş, tamamlanmamış saat, saat dilimi penceresi, saklanan kayıt bütünlüğü, çeviri yapısı ve import sınırlarını kapsar. İzole gerçek HA'da 10 eşzamanlı düzeltme ve ikinci süreçte kalıcılık geçti. 0.2.x–0.3.0 Recorder istatistik geçişi ile 0.3.x–0.4.0 Store geçişi ayrıca test edilir. 0.4.0 canlı kabulünde yeniden başlatma sonrasında 36 faturanın, altı özet toplamın ve altı sağlıklı Recorder istatistiğinin korunduğu, filtreli Core günlüğünün temiz olduğu doğrulandı. HACS kurulumu daha önce 0.2.0 ile kontrol edildi. Bu kontroller kapsamlı stres testi veya hassfest sertifikasyonu değildir. Kaynak kodundaki ağ sınırı testi paket yakalama değildir. Uygulama HA'nın `async_add_external_statistics` API'sini, kümülatif toplamları ve saat başı UTC zamanlarını kullanır.
