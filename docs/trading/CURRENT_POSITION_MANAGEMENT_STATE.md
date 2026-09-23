# QuantDinger Pozisyon Yönetimi — Mevcut Durum ve Kanıtlar

Bu belge yalnızca mevcut çalışma koşullarını, yapılan koşuları, ölçülen sonuçları ve gözlemlenen davranışları içerir. Yönlendirme, öneri, hedef parametre veya uygulanacak sonraki adım içermez.

## 1. İncelenen sistemin kapsamı

İncelenen ana aday, QuantDinger Strategy API V2 ile yazılmış StochBB mean-reversion stratejisidir. Strateji hem LONG hem SHORT yönünde çalışır ve aşağıdaki evreni kullanır:

- BTC/USDT swap
- ETH/USDT swap
- SOL/USDT swap
- BNB/USDT swap
- XRP/USDT swap
- DOGE/USDT swap
- ADA/USDT swap
- AVAX/USDT swap
- LINK/USDT swap
- BCH/USDT swap

Çalışma koşulları:

- Sürücü zaman aralığı: 5 dakika
- Tarih aralığı: 2026-09-01 — 2026-09-20
- Evrende kullanılan sembol sayısı: 10
- Başlangıç sermayesi: 10.000 USDT
- Seçili kaldıraç: 5x
- Komisyon: işlem başına `0.0005`
- Slippage: işlem başına `0.0005`
- Bar politikası: closed-bars-only
- Dolum politikası: next-open / scheduled current-open
- Intrabar politikası: conservative
- Funding: modellenmedi
- Veri sıralaması: OHLCV

## 2. Veri kaynağı ve tekrar üretilebilirlik

İlk koşular QuantDinger public market-data router üzerinden yapıldı. Router önce OKX tarihsel verisini denedi; OKX tarafındaki `50011` rate-limit durumlarında Bitget fallback kullanıldı. Bu nedenle ilk koşular Binance Demo verisiyle birebir aynı veri serisi değildir.

Run 107 sırasında QuantDinger tarafından kaydedilmiş 10 sembollük 5m snapshot daha sonra tekrar kullanıldı. Run 110, run 107 ile aynı sonucu vererek snapshot tekrar üretilebilirliğini doğruladı. Run 110–124 arasındaki ana karşılaştırmalar `persisted_snapshot:run107` kaynağı ile yapılmıştır.

Snapshot aralığı veri sağlayıcı davranışını sabitler; Binance mark price, Binance funding, gerçek spread, kısmi dolum gecikmesi ve gerçek exchange mikro-yapısı yine bu sonuçların içinde değildir.

## 3. Kod ve motor durumunda yapılan değişiklikler

### 3.1 Kaldıraç ve miktar hesabı

Strategy runtime içine seçili kaldıraç `context.leverage` olarak aktarıldı. Backtest ve live target-percent miktar hesabı eşitlendi.

Kontrol örneği:

- Equity: 10.000 USDT
- Fiyat: 100
- Kaldıraç: 5x
- Target percent: `%10`
- Backtest miktarı: `50` birim
- Live miktarı: `50` birim

Ücret ve slippage, pozisyon miktarından ikinci kez düşülmemektedir.

### 3.2 Ortak koruma motoru

Backtest ve live tarafından kullanılan ortak `ProtectionEngine` içinde `trailing_lock_profit_pct` alanı bulunmaktadır.

Long için trailing seviyesi:

```text
max(highest_price × (1 - trailing_distance),
    entry_price × (1 + lock_profit_pct))
```

Short için trailing seviyesi:

```text
min(lowest_price × (1 + trailing_distance),
    entry_price × (1 - lock_profit_pct))
```

Trailing seviyesi pozisyon lehine hareket eder; geriye doğru gevşemez.

### 3.3 Kaydedilen reason alanı

Uzun makine-okunabilir entry ve exit reason değerleri nedeniyle `qd_backtest_trades.reason` alanı `VARCHAR(64)` sınırına takılıyordu. Alan `TEXT` olarak değiştirildi ve mevcut veritabanına uygulandı.

Entry reason içinde şu bilgiler kaydediliyor:

- yön
- reference entry
- stop
- target
- reward/risk
- stop percentage
- StochRSI
- Bollinger band width / ATR
- signal age
- evidence
- market shock ATR
- profit-lock activation
- trailing mesafesi
- lock profit yüzdesi
- position percent

### 3.4 Kaynak adayları

Yerel QuantDinger source library içinde ilgili adaylar:

- `source_id=13`: filtresiz StochBB baseline
- `source_id=14`: EMA regime-exit adayı; duplicate regime-exit emri için `exit_pending` koruması içerir
- `source_id=15`: Stoch reclaim filtresi
- `source_id=16`: asymmetric reclaim filtresi
- `source_id=17`: minimum stop-width filtresi

Source 15, 16 ve 17 Strategy API V2 compile kontrolünden geçti. Source 17’nin kod hash’i:

```text
6cc90fd71925274c1c43c6620e1654c97d0434d9e78c861240f6a815ebf6d350
```

## 4. Temel exit koşuları

Bu koşular aynı StochBB giriş ailesi üzerinde exit davranışını karşılaştırmak için yapıldı.

| Run | Exit koşulu | Sonuç | İşlem | Max DD | PF |
|---:|---|---:|---:|---:|---:|
| 99 | Mid-target 0.5R + 36 bar time-stop | −10.851% | 121 | −11.802% | 0.301 |
| 100 | Fixed 1R + 36 bar time-stop | −15.893% | 240 | −18.542% | 0.496 |
| 101 | Fixed 1.5R + 36 bar time-stop | −14.572% | 236 | −19.206% | 0.598 |
| 102 | ATR stop + 0.5R activation + 0.5R ratchet | −13.269% | 244 | −15.710% | 0.459 |
| 103 | ATR stop + 0.25R early ratchet | −14.033% | 254 | −15.933% | 0.287 |
| 104 | ATR stop + 0.5R activation + 1R trail | −13.543% | 325 | −15.076% | 0.454 |
| 106 | EMA regime-flip exit + 1.5R | −14.369% | 242 | −19.069% | 0.603 |

Bu tabloda hiçbir exit-only koşusu pozitif sonuç vermedi. EMA regime exit koşusunda bazı exit emirlerinin fill beklerken tekrar üretilebildiği görüldü; source 14 içine `exit_pending` koruması eklendi.

## 5. Aynı snapshot üzerindeki giriş filtreleri

Bu bölümde aynı 10 sembollük kaydedilmiş snapshot, aynı kaldıraç, aynı ücret ve aynı ATR ratchet kullanıldı.

| Run | Giriş varyantı | Sonuç | İşlem | Max DD | PF | Pozitif işlem | Negatif işlem |
|---:|---|---:|---:|---:|---:|---:|---:|
| 114 | Reclaim filtresi yok | −13.269% | 244 | −15.710% | 0.459 | 82 | 162 |
| 110 | Stoch reclaim 0.20 | −7.813% | 172 | −10.767% | 0.534 | 64 | 108 |
| 111 | Long 0.20 / Short 0.85 | −8.526% | 191 | −11.267% | 0.542 | 71 | 120 |
| 112 | Long 0.30 / Short 0.80 | −6.413% | 131 | −7.875% | 0.494 | 49 | 82 |
| 113 | Long 0.25 / Short 0.80 | −7.430% | 153 | −9.348% | 0.493 | 55 | 98 |

Asymmetric short 0.85 koşusunda short sayısı arttı; artan kazanç katkısı artan kaybı dengelemedi. Long reclaim değerini 0.30’a çıkarmak toplam kaybı düşürdü; aynı zamanda baseline kazanç katkısının daha büyük bölümünü dışarıda bıraktı.

## 6. Minimum stop-width karşılaştırması

Run 114 filtresiz referans ile karşılaştırıldı.

| Run | Minimum stop width | Sonuç | İşlem | Max DD | PF | Pozitif PnL toplamı | Negatif PnL toplamı |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 114 | Yok | −13.269% | 244 | −15.710% | 0.459 | 1126.27 | −2453.17 |
| 115 | 0.53% | −5.387% | 101 | −8.515% | 0.599 | 805.39 | −1344.13 |
| 118 | 0.60% | −3.912% | 65 | −7.420% | 0.598 | 583.05 | −974.25 |
| 119 | 0.60% + 2R target | −4.486% | 64 | −7.767% | 0.539 | 523.62 | −972.24 |

Run 115’te baseline pozitif PnL katkısının yaklaşık `%71.5`’i, negatif PnL’nin yaklaşık `%54.8`’i korunmuştur. Run 118’de pozitif PnL katkısının yaklaşık `%51.8`’i, negatif PnL’nin yaklaşık `%39.7`’si korunmuştur.

Bu sayıların anlamı:

- 0.60% koşusu toplam kaybı daha fazla azalttı.
- 0.53% koşusu kazanan kârını daha yüksek oranda korudu.
- Her iki koşunun da toplam sonucu negatiftir.

## 7. Walk-forward dönemleri

İki yarı aynı run107 snapshot’ı üzerinde ayrı ayrı çalıştırıldı.

### WF-A: 2026-09-01 — 2026-09-10

| Koşu | Sonuç | İşlem | PF | Pozitif PnL | Negatif PnL |
|---:|---:|---:|---:|---:|---:|
| 122 — baseline | −9.565% | 112 | 0.279 | 365.10 | −1309.51 |
| 116 — minimum stop 0.53% | −4.822% | 46 | 0.283 | 189.87 | −672.04 |
| 120 — minimum stop 0.60% | −2.545% | 26 | 0.373 | 151.11 | −405.65 |

0.53% koşusunda WF-A baseline pozitif PnL’sinin yaklaşık `%52.0`’si, negatif PnL’sinin yaklaşık `%51.3`’ü kaldı. 0.60% koşusunda pozitif PnL korunumu yaklaşık `%41.4`, negatif PnL korunumu yaklaşık `%31.0` oldu.

### WF-B: 2026-09-11 — 2026-09-20

| Koşu | Sonuç | İşlem | PF | Pozitif PnL | Negatif PnL |
|---:|---:|---:|---:|---:|---:|
| 123 — baseline | −4.101% | 127 | 0.667 | 821.74 | −1231.82 |
| 117 — minimum stop 0.53% | −0.612% | 54 | 0.913 | 642.98 | −704.20 |
| 121 — minimum stop 0.60% | −1.395% | 38 | 0.760 | 443.04 | −582.57 |

0.53% koşusunda WF-B baseline pozitif PnL’sinin yaklaşık `%78.2`’si, negatif PnL’sinin yaklaşık `%57.2`’si kaldı. 0.60% koşusunda pozitif PnL korunumu yaklaşık `%53.9`, negatif PnL korunumu yaklaşık `%47.3` oldu.

## 8. Run 115 işlem bazlı kayıp analizi

Run 115’te 101 kapatılmış işlem kaydı bulunuyor. Likidite kaynaklı partial close kayıtları aynı giriş zamanı, sembol ve yön altında birleştirildiğinde 90 benzersiz pozisyon oluşuyor:

- 42 kazanan pozisyon
- 48 kaybeden pozisyon
- 53 kaybeden kapatma segmenti
- 20 partial order ledger olayı
- Exit dağılımı: 34 stop-loss, 54 trailing-stop, 13 take-profit

Kaybeden 48 benzersiz pozisyon için girişten son kapanışa kadar 5m OHLC MFE/MAE hesaplandı:

- 39 pozisyon (%81.2) fiyat hareketi bakımından bir noktada pozitif MFE gördü.
- 35 pozisyon (%72.9) kayıtlı giriş/çıkış ücretleri düşüldükten sonra da teorik net MFE pozitif gördü.
- 31 pozisyon (%64.6) en az `0.25R` MFE gördü.
- 17 pozisyon (%35.4) en az `0.5R` MFE gördü.
- Hiçbir kaybeden benzersiz pozisyon `1R` MFE seviyesine ulaşmadı.

Kaybeden pozisyonların ortalama MFE’si yaklaşık `%0.259`, medyan MFE’si yaklaşık `%0.270`; ortalama MAE’si yaklaşık `%0.731`, medyan MAE’si yaklaşık `%0.631` oldu.

Bu ölçüm gelecekteki MFE’nin canlıda bilindiği anlamına gelmez. MFE, pozisyon kapandıktan sonra görülen maksimum olumlu hareketin teşhis ölçümüdür.

## 9. Run 115 kazananlarında kâr geri verme

Run 115’in motor `grossProfit` değeri `805.39 USDT`’dir. Runtime içindeki bu metrik, pozitif kapatma PnL toplamıdır. İşlem kaydındaki komisyon öncesi pozitif `gross_profit` toplamı yaklaşık `999.96 USDT`’dir.

42 benzersiz kazanan pozisyon için:

- Gerçekleşen net kâr: yaklaşık `804.90 USDT`
- Kapanışa kadar görülen teorik net MFE toplamı: yaklaşık `1455.50 USDT`
- Gerçekleşen kâr ile MFE arasındaki toplam fark: yaklaşık `650.60 USDT`
- 39/42 kazanan işlemde MFE, gerçekleşen net kârdan yüksektir.
- 35/42 kazanan işlemde net geri verilen fırsat `5 USDT` üzerindedir.
- 31/42 kazanan işlemde net geri verilen fırsat `10 USDT` üzerindedir.
- 10/42 kazanan işlemde net geri verilen fırsat `20 USDT` üzerindedir.

Çıkış nedenine göre yaklaşık net kâr/MFE oranı:

| Çıkış nedeni | Kazanan pozisyon | Gerçekleşen net kâr | Teorik net MFE | Yaklaşık yakalama oranı |
|---|---:|---:|---:|---:|
| Take-profit | 13 | 506.56 | 580.60 | %87.2 |
| Trailing-stop | 29 | 298.34 | 874.90 | %34.1 |

MFE hesabı OHLC içindeki en iyi fiyatı kullandığı için hindsight üst sınırıdır; gerçek emir sıralaması, spread, slippage ve intrabar fiyat yolu nedeniyle aynı toplamın canlıda alınabileceği kanıtlanmış değildir.

## 10. Erken trailing aktivasyonu koşusu

Run 124, run 115 ile aynı snapshot, aynı giriş yapısı ve aynı `0.53%` minimum stop-width filtresi üzerinde yalnızca trailing activation değerini `0.5R` yerine `0.25R` yaparak çalıştırıldı.

| Koşu | Sonuç | İşlem | Max DD | PF | Pozitif PnL | Negatif PnL |
|---:|---:|---:|---:|---:|---:|---:|
| 115 — activation 0.5R | −5.387% | 101 | −8.515% | 0.599 | 805.39 | −1344.13 |
| 124 — activation 0.25R | −4.547% | 102 | −6.880% | 0.487 | 431.83 | −886.52 |

Run 124’te toplam zarar ve drawdown daha düşük oldu; pozitif PnL toplamı ve profit factor da daha düşük oldu. Exit dağılımı run124’te 20 stop-loss, 75 trailing-stop ve 7 take-profit olarak kaydedildi.

## 11. Peak-callback için çalıştırılan counterfactual analiz

Bu bölüm QuantDinger’da kalıcı bir Strategy API V2 koşusu değildir. Run115’in giriş kayıtları ve aynı snapshot OHLC verisi kullanılarak, mevcut giriş/hard-stop/hedef üzerine teorik bir peak-callback çıkışı eklenmiş offline karşılaştırmadır.

Varsayım:

- Aktivasyon: `0.5R`
- Hard stop: mevcut run115 stop seviyesi
- Hedef: mevcut run115 hedef seviyesi
- Callback: peak olumlu fiyat hareketinden `%10`, `%20` veya `%30` geri çekilme
- Ücret: entry ve exit komisyonu yaklaşık olarak düşüldü

| Counterfactual | Net toplam | Pozitif pozisyon | Negatif pozisyon | Exit türleri |
|---|---:|---:|---:|---|
| Peak callback %10 | −970.69 | 39 | 51 | 25 stop, 65 callback |
| Peak callback %20 | −974.08 | 39 | 51 | 25 stop, 65 callback |
| Peak callback %30 | −980.55 | 39 | 51 | 25 stop, 65 callback |
| Peak callback %20, activation 0.25R | −1019.86 | 6 | 84 | 15 stop, 75 callback |

Bu offline sonuçlar mevcut engine’in gerçek fill, protection önceliği ve partial liquidity akışının yerine geçmez. Kalıcı backtest run tablosuna strateji koşusu olarak kaydedilmemiştir.

## 12. Minimum stop + reclaim birleşik adayı

Run 115 giriş kayıtlarında yapılan özellik incelemesinde LONG tarafında daha yüksek StochRSI reclaim, SHORT tarafında daha düşük reclaim sınırı ve minimum stop-width aynı adayda birleştirildi. Bu seçim aynı snapshot üzerinde yapıldığı için tam dönem sonucu iki walk-forward yarısında ayrıca çalıştırıldı.

| Run | Parametre | Sonuç | İşlem | Max DD | PF | Pozitif PnL | Negatif PnL |
|---:|---|---:|---:|---:|---:|---:|---:|
| 125 | min stop 0.53%, long reclaim 0.25, short reclaim 0.80 | −0.725% | 56 | −4.020% | 0.882 | 543.84 | −616.30 |
| 126 | Aynı parametreler, WF-A | −1.189% | 23 | −2.471% | 0.494 | 115.98 | −234.86 |
| 127 | Aynı parametreler, WF-B | +0.426% | 32 | −1.981% | 1.110 | 428.47 | −385.91 |

Run 125 tam dönem sonucu negatif kaldı. Run 126 ilk yarıda negatif, run 127 ikinci yarıda pozitif sonuç verdi. Parametreler backtest run kayıtlarında saklandı; ayrı bir kod motoru değişikliği yapılmadı.

Run 125’in işlem bazlı durumu:

- 50 benzersiz pozisyon: 27 kazanan, 23 kaybeden.
- Pozitif PnL toplamı: `543.31–543.84 USDT` aralığı.
- Negatif PnL toplamı: `−616.30 USDT`.
- Run 115’e göre pozitif PnL katkısının yaklaşık `%67.5`’i kaldı.
- Run 115’e göre negatif PnL yaklaşık `%45.8` seviyesine indi.
- 23 kaybeden pozisyonun 15’i (`%65.2`) işlem sırasında ücret sonrası teorik net MFE pozitif gördü.
- Kazananlarda toplam net gerçekleşen kâr yaklaşık `543.31 USDT`, teorik net MFE yaklaşık `971.95 USDT` oldu.
- Kazanan trailing-stop pozisyonlarında gerçekleşen net/MFE oranı yaklaşık `%29.0`; take-profit pozisyonlarında yaklaşık `%91.4` oldu.

## 13. UI ve kalıcılık durumu

Run 99–127 arasındaki kalıcı koşular QuantDinger backtest veritabanında user id `1` ile `success` durumunda bulunuyor. Run 110–127 snapshot kaynaklı koşular olarak sonuç JSON’ında veri provenance bilgisi taşıyor.

QuantDinger Docker servisleri kontrol edildiğinde backend, frontend, PostgreSQL, Redis, celery ve trading/scheduler worker servisleri healthy/up durumundaydı. Backtest sonuçları Backtest Center veri katmanına yazılmıştır.

## 14. Tamamlanan Ağustos dış-dönem koşusu

Aynı strateji ailesinin yeni bir tarih aralığındaki davranışını gözlemlemek için source 13 baseline ve source 17 aday ayrı ayrı çalıştırıldı. Bu dönem, Eylül snapshot’ından farklı bir veri aralığıdır.

- Tarih aralığı: 2026-08-12 — 2026-08-31
- Zaman aralığı: 5 dakika
- Evrensel sembol sayısı: 10
- Başlangıç sermayesi: 10.000 USDT
- Kaldıraç: 5x
- Komisyon: `0.0005`
- Slippage: `0.0005`
- Veri kaynağı: QuantDinger system market-data router; `system_market_data_router:out_of_sample_aug2026`
- Funding: modellenmedi

| Run | Koşul | Sonuç | İşlem kaydı | Max DD | Win rate | PF | Kazanan / kaybeden kayıt |
|---:|---|---:|---:|---:|---:|---:|---:|
| 128 | Source 13 baseline | −22.595% | 329 | −23.184% | 26.444% | 0.272 | 87 / 242 |
| 129 | Source 17; min stop 0.53%, long reclaim 0.25, short reclaim 0.80 | −4.130% | 54 | −4.920% | 51.852% | 0.390 | 28 / 26 |

Run 128’de 271 benzersiz giriş grubu, run 129’da 50 benzersiz giriş grubu oluştu. Giriş zamanı, sembol ve yön ile birleştirilen gruplarda run 128’de 37, run 129’da 3 çoklu-kapanış grubu bulundu.

Run 129’un sembol bazlı kapanış kayıtları:

| Sembol | Kapanış kaydı | Pozitif kayıt | Negatif kayıt | PnL |
|---|---:|---:|---:|---:|
| LINK | 4 | 4 | 0 | +72.46 |
| ADA | 4 | 3 | 1 | +47.29 |
| BCH | 3 | 2 | 1 | +1.02 |
| AVAX | 10 | 4 | 6 | −0.47 |
| ETH | 3 | 1 | 2 | −39.44 |
| BTC | 3 | 1 | 2 | −49.49 |
| XRP | 4 | 2 | 2 | −79.39 |
| BNB | 4 | 2 | 2 | −85.44 |
| DOGE | 5 | 2 | 3 | −107.61 |
| SOL | 14 | 7 | 7 | −171.96 |

Run 129’da 50 benzersiz giriş grubunun 24’ü zarar ile kapandı. Bu zarar grupları long tarafta 13, short tarafta 11 adettir. Zarar gruplarının sembol dağılımında SOL 7, AVAX 4, DOGE 3; BTC, BNB, XRP ve ETH 2’şer; BCH ve ADA 1’er gruptur. LINK’te zarar grubu oluşmadı.

Run 129 çıkış kayıtlarının dağılımı:

- `trailing_stop`: 39 kayıt, toplam kayıt PnL’si yaklaşık `+214.50 USDT`
- `stop_loss`: 14 kayıt, toplam kayıt PnL’si yaklaşık `−668.24 USDT`
- `take_profit`: 1 kayıt, toplam kayıt PnL’si yaklaşık `+40.72 USDT`

Koşu sırasında OKX tarafında `50011 Too Many Requests`, bazı sembollerde gecikmiş tarihsel veri ve ADA için birden fazla sağlayıcı fallback uyarısı görüldü. Sonuçlar bu nedenle Binance-exact değildir; iki run da veritabanında `success` ve `completed_trades` durumunda kalıcı olarak kayıtlıdır.

## 15. Yeni saatlik kanal adayı

Araştırma planındaki saatlik kanal kırılımı adayı Strategy API V2 ile derlendi ve yerel source library’de source `18` olarak kaydedildi. Manifest koşulları: 1h sürücü, 4h tamamlanmış EMA100 rejim filtresi, 10 sembol, `one_way`, maksimum 5x kaldıraç, 2×ATR başlangıç stopu ve karşı 1h kanal kapanışıyla çıkış. Sabit take-profit kullanılmadı.

Eylül dönemi koşuları:

| Run | Kanal | Final totalReturn | Gerçekleşmiş PnL | Dönem sonu açık PnL | Kapanmış PF | Max DD | Kapanmış işlem |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 130 | 24 saat | +18.397% | −1057.95 | +2897.60 | 0.729 | −32.017% | 64 |
| 131 | 48 saat | +1.159% | −2225.49 | +2341.36 | 0.391 | −35.295% | 49 |
| 132 | 96 saat | +0.387% | −1742.76 | +1781.42 | 0.374 | −25.706% | 34 |

Run130–132’de final totalReturn pozitif görünse de kapanmış işlem PnL’si üç koşuda da negatiftir. Pozitif final equity, dönem sonunda açık kalan 8–9 long pozisyonun mark-to-market değerinden gelmiştir. Kapanmış işlem kayıtlarında long/short toplamları sırasıyla run130’da `+10.96 / −1068.91`, run131’de `−1257.76 / −967.73`, run132’de `−1047.71 / −695.05 USDT` olmuştur.

Ağustos dış-dönem koşuları:

| Run | Kanal | Final totalReturn | Gerçekleşmiş PnL | Dönem sonu açık PnL | Kapanmış PF | Max DD | Kapanmış işlem |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 133 | 24 saat | +51.614% | +5255.17 | −93.72 | 1.883 | −40.975% | 68 |
| 134 | 48 saat | +79.320% | +7989.09 | −57.11 | 3.005 | −34.761% | 44 |
| 135 | 96 saat | +112.497% | +11317.33 | −67.67 | 14.827 | −25.710% | 20 |

Run133–135’te kapanmış long PnL’si pozitif, short PnL’si sırasıyla yaklaşık `−873.09`, `−541.81` ve `−234.97 USDT` olmuştur. Her iki 20 günlük dönem arasında sonuç farkı ve yüksek drawdown görülmüştür. Run130–135 sonuçları veritabanında `success` ve `completed_trades` durumundadır; performans değerlendirmesinde final açık PnL ile kapanmış PnL ayrı tutulmuştur.

## 16. Saatlik adayda risk sizing ve yön izolasyonu

Source 19’da giriş/çıkış koşulları değiştirilmeden target-percent, stop mesafesi, 5x kaldıraç ve tahmini `%0.2` tur maliyeti üzerinden `%0.5` equity işlem riski hedefleyecek şekilde hesaplandı.

| Run | Dönem | Kanal | Gerçekleşmiş PnL | Açık PnL | Kapanmış PF | Max DD |
|---:|---|---:|---:|---:|---:|---:|
| 136 | Eylül | 24 saat | −508.15 | +1484.28 | 0.756 | −17.814% |
| 137 | Eylül | 48 saat | −995.47 | +1530.95 | 0.456 | −18.262% |
| 138 | Eylül | 96 saat | −691.84 | +972.23 | 0.456 | −11.428% |
| 139 | Ağustos OOS | 24 saat | +3968.53 | −35.05 | 2.284 | −26.405% |
| 140 | Ağustos OOS | 48 saat | +5458.44 | −21.24 | 3.702 | −23.213% |
| 141 | Ağustos OOS | 96 saat | +7101.62 | −23.50 | 17.737 | −18.608% |

Source 20’de aynı risk/giriş/çıkış koşulları ile yalnızca long yönü açık bırakıldı. Eylül 24 saatlik koşuda gerçekleşmiş PnL `+144.31 USDT`, 48 saatlikte `−474.49 USDT`, 96 saatlikte `−345.41 USDT` oldu. Ağustos OOS’ta long-only gerçekleşmiş PnL’ler 24/48/96 saat için sırasıyla `+4898.47`, `+5899.78`, `+7220.88 USDT` oldu. Short tarafı source19’un altı koşusunun tamamında negatif kapanmış PnL verdi.

Source20 long-only için üçüncü pencere `2026-08-01 — 2026-08-20` de çalıştırıldı. Run148/149/150’nin gerçekleşmiş PnL’leri 24/48/96 saat için sırasıyla `−708.73`, `−428.48`, `−320.41 USDT`; kapanmış PF değerleri `0.251`, `0.343`, `0.363` oldu. Bu üç koşuda final equity pozitif görünse de yaklaşık `+2.34–2.47k USDT` açık PnL taşındı.

## 17. Saatlik adayda MFE/MAE ile kayıp teşhisi

Source20 long-only koşularının işlem kayıtları, `reviewCandles` saatlik OHLC verisiyle giriş barından çıkış barına kadar incelendi. Bu, tick sırasını bilmeyen bar-range teşhisidir; canlıda tepeyi önceden bilme kuralı değildir. Net MFE hesaplanırken kayıtlı komisyon düşüldü.

| Run | Dönem / kanal | Kapanmış | Kazanan / kaybeden | Kaybedenlerde fiyat MFE pozitif | Kaybedenlerde net MFE pozitif | Net MFE ort./medyan |
|---:|---|---:|---:|---:|---:|---:|
| 142 | Eylül / 24h | 38 | 11 / 27 | 23/27 (`%85.2`) | 18/27 (`%66.7`) | `42.88 / 29.33 USDT` |
| 145 | 12–31 Ağustos / 24h | 48 | 10 / 38 | 37/38 (`%97.4`) | 30/38 (`%78.9`) | `52.86 / 34.88 USDT` |
| 148 | 1–20 Ağustos / 24h | 29 | 6 / 23 | 23/23 (`%100`) | 20/23 (`%87.0`) | `36.98 / 25.78 USDT` |

Bu üç pencerede kaybedenlerin çoğu işlem boyunca olumlu hareket gördü; run145’te 38 kaybedenin 30’u ücret sonrası net MFE pozitifti. Dolayısıyla saatlik adayda teşhis “daha az sinyal” değil, pozisyon kârdayken onu koruyacak aktivasyon, kısmi realize ve volatilite uyumlu monoton trailing tasarımının eksik olmasıdır. MFE sonucu yalnızca araştırma metriğidir; geleceği bilen bir canlı kural olarak kullanılmayacaktır.

## 18. Source21 kâr-kilidi adayı

Source20’nin aynı giriş ve risk-sizing davranışı korunarak source21’de pozisyon korumasına kâr aktivasyonu, ATR-oranlı trailing ve minimum kâr kilidi eklendi. İlk varyant `0.5R activation / 0.75R trail / 0.1% lock`; daha temkinli B varyantı `0.75R activation / 1.0R trail / 0.1% lock` kullandı.

| Run | Varyant | Yön | Dönem | Gerçekleşmiş PnL | PF | Max DD | Kapanmış |
|---:|---|---|---|---:|---:|---:|---:|
| 151 | A | long-only | Eylül 1–20 | `+775.22` | `1.573` | `−8.288%` | 85 |
| 152 | A | long-only | Ağustos 12–31 | `+687.15` | `1.355` | `−12.948%` | 101 |
| 153 | A | long-only | Ağustos 1–20 | `+1488.38` | `3.300` | `−2.845%` | 62 |
| 154 | B | long-only | Eylül 1–20 | `+1796.28` | `2.649` | `−6.640%` | 66 |
| 155 | B | long-only | Ağustos 12–31 | `+1526.44` | `1.803` | `−12.487%` | 90 |
| 156 | B | long-only | Ağustos 1–20 | `+1545.43` | `2.838` | `−3.718%` | 57 |
| 157 | B | long+short | Eylül 1–20 | `+1224.93` | `1.640` | `−10.298%` | 96 |
| 158 | B | long+short | Ağustos 12–31 | `+655.94` | `1.245` | `−13.768%` | 113 |

B varyantı üç long-only pencerede pozitif gerçekleşmiş PnL verdi. Long+short toplamı pozitif kalsa da short kolu negatifti: run157’de long `+1727.35`, short `−502.42 USDT`; run158’de long `+1432.30`, short `−776.36 USDT`. Bu nedenle source21 B araştırma adayıdır, Demo-ready değildir.

Source21 B’de kaybeden net MFE pozitif oranı run154/155/156 için sırasıyla `23/32`, `37/47`, `22/26`; kazanan net/MFE yakalama oranı `%61.9 / %57.8 / %57.7` oldu. Kâr kilidi önceki düşük yakalamayı iyileştirdi ancak kayıpların kâr gördükten sonra tersine dönmesi tamamen çözülmedi.

## 19. Çakışmayan holdout doğrulaması

Source20 baseline ve source21 B aynı long-only, 24h kanal, 10 sembol, 20 gün ve 5x koşullarında üç yeni pencereye taşındı:

| Run | Source | Dönem | Gerçekleşmiş PnL | PF | Max DD | Kapanmış |
|---:|---|---|---:|---:|---:|---:|
| 159 | source20 | 1–20 Haziran | `−222.76` | `0.095` | `−4.770%` | 6 |
| 160 | source21 B | 1–20 Haziran | `+26.05` | `1.253` | `−1.617%` | 7 |
| 161 | source20 | 21 Haziran–10 Temmuz | `+84.08` | `1.148` | `−8.560%` | 21 |
| 162 | source21 B | 21 Haziran–10 Temmuz | `−310.38` | `0.639` | `−7.296%` | 41 |
| 163 | source20 | 11–30 Temmuz | `−594.79` | `0.385` | `−7.355%` | 32 |
| 164 | source21 B | 11–30 Temmuz | `−343.83` | `0.541` | `−5.404%` | 39 |

Her koşuda 10/10 sembol kullanıldı, atlanan sembol yoktu ve audit geçti. Source21 B’nin kaybeden net MFE pozitif oranı run160/162/164 için `3/5`, `23/28`, `23/27` idi. Bu sonuç kâr-kilidinin kaybı azaltabildiğini, fakat yeni dönemlerde genellenebilir pozitif edge üretmediğini gösteriyor.

Source21 B long+short run165–167’de `−144.62 / −1003.02 / −491.14 USDT` gerçekleşmiş PnL verdi; short katkısı `−169.91 / −707.27 / −151.38 USDT` idi. Kanal 48h/96h koşulları da run168–173’te tutarlı iyileşme sağlamadı. Önceki Eylül’de daha iyi görünen Peak Continuation source10 holdout run174–176’da `−19.27 / −38.37 / −39.49 USDT` verdi; 5m veri sağlayıcı uyarıları bulunduğu için bu sonuçlar zayıf kanıt olarak etiketlendi.

Source22 ile source21 B’ye tamamlanmış 4h BTC/USDT EMA100 global rejim kapısı eklendi. Aynı long-only, 24h kanal, 10 sembol, 5x ve `%0.5` equity-risk holdout’larında run177–179 gerçekleşmiş PnL olarak `−53.37 / −435.52 / −444.97 USDT`, PF olarak `0.477 / 0.425 / 0.399`, max DD olarak `−1.494% / −7.296% / −5.268%` verdi. Üç koşuda da 10/10 sembol kullanıldı ve audit geçti. Global BTC filtresi source21 B’ye göre iyileşme sağlamadı; source22 eleme/araştırma kaydıdır.

Source23’te breakout sonrası doğrudan giriş yerine en fazla 6 bar içinde ATR toleranslı retest/reclaim teyidi arandı. Source21 B’nin risk sizing ve kâr-kilidi korundu. Long+short run180–185 gerçekleşmiş PnL olarak `+288.10 / −146.41 / −427.68 / −761.94 / −89.40 / +1045.17 USDT` verdi; short katkısı çoğu pencerede negatiftir. Long-only run186–191 `+108.06 / −185.05 / +2.41 / +26.84 / +284.44 / +1086.16 USDT` verdi. Strict 3-bar/0.5-ATR kontrol run192–194’te `0.00 / −155.59 / −10.87 USDT` ve `0 / 12 / 9` işlem üretti. Source23, entry mekanizması açısından anlamlı ama dönemler arası istikrarı kanıtlanmamış araştırma adayıdır.

## 20. Mevcut durumun kısa özeti

- İncelenen StochBB stratejisinin 10 coin, 20 gün ve 5x koşularındaki tüm kalıcı varyantları negatiftir.
- Aynı snapshot karşılaştırmasında en yüksek profit factor run115’te `0.599` civarındadır.
- Run117 ikinci walk-forward yarısında `PF=0.913` ve `%−0.612` sonuç vermiştir; sonuç yine pozitife geçmemiştir.
- Kaybeden benzersiz pozisyonların `%72.9`’u ücretlerden sonra da teorik net kâr seviyesi görmüştür.
- Kazanan pozisyonlarda gerçekleşen kâr, teorik MFE’nin altında kalmıştır; özellikle trailing-stop kapanışlarında fark büyüktür.
- Erken `0.25R` activation koşusunda pozitif PnL katkısı düşmüştür.
- Peak-callback offline denemeleri pozitif toplam sonuç üretmemiştir.
- Minimum stop + reclaim birleşik adayı run125’te tam dönemde negatif, run126’da negatif ve run127’de pozitif sonuç vermiştir.
- Yeni Ağustos dış-döneminde aynı aday run129 ile −%4.130 sonuç verdi; baseline run128 −%22.595 oldu.
- Veri Binance-exact değildir; OKX/Bitget router ve persisted snapshot kullanılmıştır.
- Bu koşulara göre hiçbir varyant Binance Demo execution için pozitif performans kanıtı taşımamaktadır.
- User id `1` için kalıcı backtest kaydı toplamı run194 itibarıyla 193’tür; source21 B, source22 ve source23 araştırma adayları olarak kalmış, Demo-ready doğrulaması geçememiştir.
