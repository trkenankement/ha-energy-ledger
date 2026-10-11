# Energy Ledger — yerel aylık faturalar

Geliştirme sürümü. İzole Home Assistant 2026.10.1 / Python 3.14 üzerinde
gerçek Recorder, kayıt formları ve yeniden başlatma testleri geçti.
HA 2026.10.1'e yedek sonrası kuruldu; Türkçe giriş formu ve altı varlık
doğrulandı. Gerçek fatura/grafik kabulü bekliyor. HACS'ın varsayılan
kataloğuna dahil değildir; özel depo yöntemi için aşağıdaki adımları kullanın.

Elektrik (kWh), doğalgaz (m³) ve su (m³) faturalarını HA'nın **Yapılandır**
formundan girer. Tüketim ve tutar ayrı geçmiş istatistiklerine aktarılır.
Bulut, telemetri, banka bağlantısı ve ek Python bağımlılığı yoktur.

## Kurulum ve kullanım

GitHub deposu: https://github.com/trkenankement/ha-energy-ledger

HACS üzerinden: önce tam yedek alın. HACS → Özel depolar bölümünde depo
adresini **Integration** türünde ekleyin; Energy Ledger'ı indirin ve HA'yı
yeniden başlatın. Bu işlem GitHub'dan sürüm dosyalarını indirir; faturalarınızı
GitHub'a göndermez. Güncellemeler HACS ile yönetilir, otomatik `git pull` yapılmaz.
Depo özel ise bu HACS yöntemi kullanılamaz; manuel kurulumu kullanın.

Manuel kurulum:

1. `custom_components/energy_ledger` klasörünü HA'nın `/config/custom_components/`
   dizinine kopyalayın. Önce yedek alın; HA'yı yeniden başlatın.
2. Ayarlar → Cihazlar ve hizmetler → Entegrasyon ekle → Energy Ledger.
3. Para birimini seçin; entegrasyonun **Yapılandır** menüsünden kayıt girin.
4. Ay `YYYY-MM`, tüketim ve maliyet sayı olmalıdır. Ondalık virgül kabul edilir;
   binlik ayırıcı kullanmayın. Görünmeyen tüketim birimini tahmin etmeyin.
5. Enerji ayarlarında gaz/su/şebeke tüketim kaynağına `energy_ledger:gas_consumption`,
   `energy_ledger:water_consumption` veya `energy_ledger:electricity_consumption`
   istatistiğini seçin. Maliyet kaynağı ilgili `energy_ledger:*_cost` istatistiğidir.
   Kaynakların listelenmesi Recorder kuyruğunun işlenmesini gerektirir.

## Muhasebe anlamı

**Bu günlük ölçüm değil, aylık fatura muhasebesidir.** Girdiğiniz ayın ilk saatine
ayın tamamı yazılır. Aylık/yıllık görünüm kullanın; günlük grafikler gerçek
tüketim dağılımını göstermez. Ödeme tarihi, tüketim dönemi değildir. Fatura
dönemi bilinmiyorsa seçtiğiniz ayın ödeme/vade ayı olduğunu ayrıca not edin.
Eksik ay, gerçek sıfır tüketim anlamına gelmez.

Her kaynak/ay için tek kayıt vardır. Değiştirmek için aynı ayı yeniden girin;
onay ekranında önceki kayıt gösterilir. Silme ayrı onay ister ve yalnız bu
entegrasyonun ürettiği istatistikleri yeniden hesaplar. Diğer HA istatistikleri
silinmez. Silinen ayın sıfır tombstone kaydı yerelde tutulur.

Elektrik faturasını prizlerin toplamına ayrıca eklemeyin: aynı tüketimi iki
kere sayarsınız. Fatura tüm ev şebeke toplamı, prizler cihaz alt kırılımıdır.

Kayıtlar HA `.storage` altında yereldir ve HA yedeğiyle korunur. Entegrasyon
kaldırılınca geçmişi otomatik silmez. Tek hane / kaynak başına tek sayaç,
son 120 ay, dört para birimi desteklenir. Para birimi ve saat dilimi ilk
kurulumda sabitlenir; farklı birime geçmişi yeniden yorumlama yapılmaz.
Saat dilimi tam saat UTC ofseti kullanmalıdır.

## Geliştirme / yayın

Gerçek faturalar, kimlikler, HA yedekleri ve `.storage` GitHub'a konmaz.
Sürüm geliştirme aşamasındadır: hassfest/HACS ve gerçek enerji grafik kabulü
ayrı kontrol kapılarıdır; kaynak testlerinin geçmesi bu kontrollerin geçtiği
anlamına gelmez. Resmi Home Assistant entegrasyonu veya Supervisor uygulaması
değil, özel entegrasyondur.

Sentetik testler: `python -m unittest discover -s tests -v`.

API referansı: HA Core 2026.10 Recorder `async_add_external_statistics`;
`mean_type`, `unit_class`, saat başı UTC damgası ve kümülatif `sum` kullanılır.
