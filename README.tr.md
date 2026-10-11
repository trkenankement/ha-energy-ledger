# Energy Ledger — aylık fatura takibi

[English guide](README.md)

Elektrik, doğalgaz ve su faturalarının aylık tüketimini ve tutarını Home Assistant içinde kaydedin; ardından Enerji ekranında tüketim ve maliyet olarak görüntüleyin. Banka/bulut hesabı veya akıllı sayaç gerekmez.

Bu bir **özel entegrasyondur**; resmi Home Assistant entegrasyonu veya Supervisor uygulaması değildir. 0.2.0 geliştirme sürümüdür. Gerçek HA 2026.10.1, Recorder ve kalıcı saklama ile sentetik testler geçti. Aylık ve yıllık tüketim/maliyet canlı HA Enerji ekranında doğrulandı. HACS özel deposundan kurulum, ardından yeniden başlatma ve kayıtların korunması kontrolü de geçti.

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

Entegrasyonda bulut istemcisi, telemetri veya dış ağ bağlantısı kodu yoktur. Kayıtlar HA'nın `.storage` dosyasında, Recorder istatistiklerinde ve sensör özelliklerinde tutulur. Kurulum/güncelleme araçları ve diğer HA entegrasyonları internete çıkabilir; bu uygulama güvenlik duvarı değildir. Canlı paket yakalama yapılmış olduğu iddia edilmez.

Yerel saklama, yalnız yöneticinin görebildiği veya bu bileşen tarafından şifrelenen saklama anlamına gelmez. Etkin fatura satırları sensör özelliklerine de eklenir; bu durumları okuyabilen HA kullanıcıları/istemcileri erişebilir. HA yedekleri de verileri içerebilir. Yapılandırma formları HA'nın yönetici yetkilerine dayanır. HA erişimini, dosyaları ve yedekleri koruyun; gerçek faturaları, `.storage`, parolaları veya yedek arşivlerini GitHub'a koymayın.

Entegrasyonu kaldırmak kayıtları ve Recorder geçmişini otomatik temizlemez.

## 6. Sınırlar ve sorun giderme

- Tek hane, kaynak başına tek aylık kayıt desteklenir. Çoklu sayaç, tarife hesabı, döviz dönüşümü ve PDF okuma yoktur.
- Para birimi/saat dilimi değişikliği geçmiş kayıtları yeniden değerlemez. Tam saat olmayan saat dilimleri reddedilir.
- Saatlik istatistik üretiminin sınırı 3.660 gündür. Eski kayıtlar otomatik sona ermez; bu yaşa yaklaşan kayıt defteri için taşıma gerekir. Süresiz arşiv desteği olarak düşünmeyin.
- Boş kayıt defterindeki sıfır toplam, evin hiç tüketmediğini göstermez.
- İstatistik görünmüyorsa kaydın onaylandığını ve Recorder'ın çalıştığını kontrol edin; HA günlüklerinde `energy_ledger` arayın. Sorun ararken diğer çalışan Enerji kaynaklarını değiştirmeyin.

## 7. Test ve geliştirme

Depo kökünde sentetik birim ve kontrat testleri:

```sh
python -m unittest discover -s tests -v
```

Testler düzeltme, tekrar giriş, silme, bağımsız aylık toplamlar, hatalı girdiler, tarih sınırları, çeviri yapısı ve import sınırlarını kapsar. İzole gerçek HA'da 10 eşzamanlı düzeltme ve ikinci süreçte kalıcılık geçti. Canlı aylık/yıllık grafikler ve HACS kurulumu ayrı olarak doğrulandı. Bu kontroller kapsamlı stres testi veya hassfest sertifikasyonu değildir. Kaynak kodundaki ağ sınırı testi paket yakalama değildir. Uygulama HA'nın `async_add_external_statistics` API'sini, kümülatif toplamları ve saat başı UTC zamanlarını kullanır.
