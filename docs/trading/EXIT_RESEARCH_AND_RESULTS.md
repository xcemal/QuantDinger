# Çıkış araştırması ve QuantDinger sonuçları

## Ana bulgu

Pozisyonların kâra geçip sonra zarara dönmesi gerçek bir çıkış problemi; ancak bütün zararların sebebi bu değil. 2026-09-01–2026-09-20, 5m, 10 coin, crypto-swap router verisi, 5x koşusunda Peak Continuation net-lock koşusunda 4 zararın 2'si pozitif MFE gördü, 2'si ise hiç lehine gitmeden hard stop oldu. Bu nedenle çıkış yönetimi ve giriş rejimi ayrı ölçülmelidir. Bu veri Binance-exact değildir: QuantDinger public router'ı OKX'i denedi, rate-limit durumunda Bitget'e fallback yaptı.

MFE, işlem sonrasında görülen maksimum lehine hareketi ölçen bir teşhistir; canlı kural olarak gelecekteki MFE kullanılamaz. Çıkış kuralı yalnızca o ana kadar kapanmış barlardan güncellenmelidir.

## Araştırmadan çıkan test sırası

1. Başlangıç hard ATR/structural stop.
2. İşlem en az belirlenmiş bir R eşiğine geldikten sonra yalnızca sıkılaşan ATR/Chandelier ratchet.
3. Ratchet seviyesi için ücret ve slippage sonrasında pozitif kalan net-kâr tabanı.
4. Trend stratejilerinde karşı Donchian/Turtle çıkışı ve teyitli EMA flip karşılaştırması.
5. Favorable excursion oluşmayan işlemler için seçici time-stop.
6. Mean-reversion stratejilerinde önce hedefe dönüş, band/tez bozulması ve kısa time-stop; geniş trend runner'ı ayrı test kolu olarak tutmak.

TradingView'in resmi Chandelier Exit açıklaması long için `highest - ATR × multiplier`, short için `lowest + ATR × multiplier` mantığını tarif eder. Turtle/Donchian topluluk örnekleri karşı kanal kırılımını trend çıkışı olarak kullanır; bunlar mekanik referanstır, performans kanıtı değildir.

Akademik literatür stop-loss etkisinin rejime, seri korelasyona ve işlem maliyetlerine bağlı olduğunu; evrensel bir stop kuralı olmadığını gösterir. Kripto trend-following çalışmalarında işlem maliyetleri ve zaman aralığı sonucu belirgin biçimde etkiler. Mean-reversion çalışmaları da işlem maliyeti ile stop ve hedefin birlikte tasarlanması gerektiğini vurgular.

## Uygulanan teknik değişiklik

`ProtectionSpec` ve ortak `ProtectionEngine` içine `trailing_lock_profit_pct` eklendi.

- Long trailing seviyesi: `max(highest_price × (1 - trail), entry_price × (1 + lock))`
- Short trailing seviyesi: `min(lowest_price × (1 + trail), entry_price × (1 - lock))`
- Seviye yalnızca pozisyon lehine sıkılaşır; geriye açılmaz.
- Backtest ve live aynı ortak ProtectionEngine'i kullanır.
- Varsayılan değer eski davranışı bozmayacak şekilde `0.0`; test koşullarında `0.0015` kullanıldı.

Target-percent miktar hesabı da live ile eşitlendi: 10.000 USDT equity, 5x, `%10` hedef için backtest ve live miktarı artık aynı `50.0` birimdir; ücret/slippage pozisyon boyutundan ikinci kez düşülmez.

## Backtest karşılaştırması

Tüm koşullar 5m, 10 sembol, 2026-09-01–2026-09-20, 5x, komisyon `0.0005`, slippage `0.0005`, conservative intrabar, closed-bars-only, next-open fill ve funding not modeled'dir. Veri, Binance Demo ile birebir değil; kaynak router provenance'ı koşu sonuçlarında saklanır.

| Koşu | Sonuç | İşlem | Max DD | Yorum |
| --- | ---: | ---: | ---: | --- |
| Peak native 1R/1.25ATR | -0.302% | 9 | -0.361% | 3 trailing kârı, 6 hard stop |
| Peak ratchet 0.5R/0.5ATR | -0.090% | 11 | -0.269% | Kâr koruması iyileşti |
| Peak net-lock 0.15% + ratchet | -0.015% | 10 | -0.205% | 7 trailing, 3 hard stop |
| Peak net-lock WF 1–10 | +0.015% | 5 | -0.136% | Küçük örneklem |
| Peak net-lock WF 11–20 | -0.109% | 9 | -0.252% | Rejim bağımlılığı sürüyor |
| Qullamagi baseline | -73.288% | 1570 | -73.288% | Giriş/işlem sıklığı ana problem |
| Qullamagi net-lock | -75.381% | 1523 | -75.431% | Çıkış değişikliği kurtarmadı |
| Triple EMA baseline | -79.455% | 1591 | -79.522% | Giriş/whipsaw ana problem |
| Triple EMA net-lock | -77.715% | 1664 | -77.816% | Küçük iyileşme, hazır değil |
| StochBB baseline risk-sized | -13.382% | 260 | -14.694% | Mean-reversion |
| StochBB net-lock | -14.292% | 258 | -16.463% | Runner yaklaşımı bu stratejiye uymadı |

## Son exit-only varyantları ve MFE/MAE sonucu

StochBB'nin aynı giriş kurallarıyla 5x koşularında ek exit sweep'i yapıldı:

| Koşu | Sonuç | İşlem | Max DD | Çıkış dağılımı / yorum |
| --- | ---: | ---: | ---: | --- |
| MidTarget 0.5R + 36-bar time-stop (run 99) | -10.851% | 121 | -11.802% | 52 stop, 68 TP, 1 time-stop |
| Fixed 1R + 36-bar time-stop (run 100) | -15.893% | 240 | -18.542% | Küçük hedef işlem maliyetiyle yetmedi |
| Fixed 1.5R + 36-bar time-stop (run 101) | -14.572% | 236 | -19.206% | Daha az TP, daha büyük geri dönüş |
| ATR stop + 0.5R activation / 0.5R ratchet (run 102) | -13.269% | 244 | -15.710% | 93 stop, 122 trailing, 28 TP |
| ATR stop + 0.25R early ratchet (run 103) | -14.033% | 254 | -15.933% | Erken trailing ortalama -1.66 PnL |
| ATR stop + 0.5R activation / 1R trail (run 104) | -13.543% | 325 | -15.076% | Geniş trail de pozitif olmadı |
| EMA regime-flip exit, 1.5R (run 106) | -14.369% | 242 | -19.069% | 24 flip exit; exit-only kurtarmadı |

## Aynı snapshot üzerinde kaybeden/kazanan filtresi

Provider fallback farkını ortadan kaldırmak için run 107'nin QuantDinger tarafından kaydedilmiş 10 sembollük OHLCV snapshot'ı kullanıldı. Filtresiz baseline run 114 ile aynı exit profili üzerinde kıyaslandı:

| Koşu | Sonuç | İşlem | Max DD | Gross profit | Gross loss | PF | Yorum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Snapshot baseline, filtre yok (run 114) | -13.269% | 244 | -15.710% | 1126.27 | -2453.17 | 0.459 | Referans |
| Stoch reclaim 0.2 (run 110) | -7.813% | 172 | -10.767% | 896.25 | -1677.58 | 0.534 | Kayıp azalıyor, kazanç %79.6 korunuyor |
| Long reclaim 0.25 / short 0.8 (run 113) | -7.430% | 153 | -9.348% | 722.55 | -1465.51 | 0.493 | Kazanç koruması zayıf; elendi |
| Minimum stop width 0.53% (run 115) | -5.387% | 101 | -8.515% | 805.39 | -1344.13 | 0.599 | Gross profit %71.5, gross loss %54.8 korunuyor |
| Minimum stop width 0.60% (run 118) | -3.912% | 65 | -7.420% | 583.05 | -974.25 | 0.598 | Daha az maliyet, PF aynı; henüz edge değil |
| Stop 0.60% + target 2R (run 119) | -4.486% | 64 | -7.767% | 523.62 | -972.24 | 0.539 | 1.5R'den kötü |

Stop-width 0.53% adayının walk-forward kontrolünde WF-A run 116 `%−4.822`, WF-B run 117 `%−0.612`, PF `0.913` oldu. İkinci yarı başa başa yaklaştı fakat pozitif değil; bu nedenle Demo adayı ilan edilmedi. Run 115'te 90 giriş, 0 duplicate signal key ve stop/trailing/TP dağılımı sırasıyla 34/54/13 idi; kaynakta duplicate exit guard da mevcut.

Kazananı koruma kriterini iki walk-forward yarısında ayrıca karşılaştırmak için filtresiz referanslar run 122 (WF-A) ve run 123 (WF-B), 0.60% filtreli koşular run 120 ve run 121 olarak kaydedildi:

| Dönem | Filtresiz referans | 0.53% filtre | 0.60% filtre | Yorum |
| --- | --- | --- | --- | --- |
| WF-A | run 122: gross `+365.10 / -1309.51`, PF `0.279`, `%−9.565` | run 116: gross `+189.87 / -672.04`, PF `0.283`, `%−4.822`; kâr %52.0, zarar %51.3 korunuyor/azalıyor | run 120: gross `+151.11 / -405.65`, PF `0.373`, `%−2.545`; kâr %41.4, zarar %31.0 | 0.60% toplam kaybı daha çok düşürüyor ama kazananları fazla eliyor |
| WF-B | run 123: gross `+821.74 / -1231.82`, PF `0.667`, `%−4.101` | run 117: gross `+642.98 / -704.20`, PF `0.913`, `%−0.612`; kâr %78.2, zarar %57.2 | run 121: gross `+443.04 / -582.57`, PF `0.760`, `%−1.395`; kâr %53.9, zarar %47.3 | 0.53% hem daha fazla kazanan katkısı bırakıyor hem PF'yi daha çok iyileştiriyor |

Bu nedenle 0.60% adayının tam dönem getirisi daha iyi görünse de, kullanıcı hedefi olan kazananları koruma açısından 0.53% adayını tercih ediyorum. İki aday da hâlâ tam dönem ve WF-A/WF-B bazında pozitif değil; bu bir Demo hazırlık onayı değildir.

## Peak-kâr geri çekilmesi ve literatürden çıkan tasarım

Peak'ten yüzde geri çekilme fikri, klasik trailing/callback stop'un PnL veya fiyat yüksek-su işaretine uygulanmış halidir. Leung ve Zhang trailing stop'u çalışan maksimuma bağlı, path-dependent bir stochastic floor olarak modeller; TradingView ve Bybit dokümantasyonu da aynı fikri aktivasyon seviyesi + en iyi fiyattan geri çekilme mesafesi olarak tanımlar. Chandelier yaklaşımı bunu `highest_high - ATR × multiplier` (long) ve `lowest_low + ATR × multiplier` (short) ile volatiliteye bağlar.

Bu fikirleri doğrudan uygulamadan önce mevcut ProtectionEngine'in `0.25R` aktivasyon varyantı run 124 ile ölçüldü. Run 115'teki `0.53%` minimum stop filtresi ve aynı snapshot korunarak yalnızca activation `0.5R → 0.25R` değiştirildi:

| Koşu | Sonuç | İşlem | Gross profit | Gross loss | PF | Karar |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| run 115: activation 0.5R | -5.387% | 101 | 805.39 | -1344.13 | 0.599 | Referans |
| run 124: activation 0.25R | -4.547% | 102 | 431.83 | -886.52 | 0.487 | Elendi: kazanan kârının yaklaşık yarısı kesildi |

Bu sonuç, peak/callback mekanizmasının yanlış olmadığını; aktivasyonun çok erken ve yalnızca sabit kilit kârla yapılmasının kazanan kuyruğunu budadığını gösterir. İleride test edilecek doğru hipotez şu olmalıdır: önce işlem net maliyetleri aşan bir `R` eşiği, sonra volatiliteye göre monoton trailing; sabit yüzde callback ancak bu aktivasyondan sonra devreye girmeli.

## Run 115 kazananlarında kâr geri verme analizi

Run 115'in `grossProfit=805.39` metriği, motorun kazanan kapamaların komisyon/slippage sonrası pozitif PnL toplamıdır; işlem kayıtlarındaki komisyon öncesi pozitif `gross_profit` toplamı yaklaşık `999.96`'dır. 90 benzersiz pozisyon 42 kazanan ve 48 kaybeden olarak birleştirildi; likidite kaynaklı partial close parçaları tek pozisyon kabul edildi.

Kazanan 42 pozisyonun gerçekleşen net kârı yaklaşık `804.90`, pozisyon kapanana kadar görülen teorik net MFE toplamı yaklaşık `1455.50` oldu. Bu, kusursuz tepe çıkışı yapılabileceği anlamına gelmez; 5m OHLC içindeki en iyi fiyat hindsight üst sınırıdır. Yine de 42 kazananın 39'unda MFE gerçekleşen kârdan yüksekti; 35'inde geri verilen net fırsat `5 USDT` üzerindeydi, 31'inde `10 USDT` üzerindeydi ve 10'unda `20 USDT` üzerindeydi.

Çıkış türüne göre fark daha belirgin: take-profit kazananlarında gerçekleşen net kâr/MFE yaklaşık `%87.2`, trailing-stop kazananlarında yaklaşık `%34.1` idi. Yani daha büyük kâr potansiyeli özellikle trailing ile kapanan kazananlarda bırakılmış görünüyor. Buna rağmen MFE gelecekte bilinemeyeceği için doğrudan tepeyi hedefleyen bir kural kurulamaz; araştırılacak kural, net maliyet sonrası aktivasyon + monoton callback/ATR trail olmalıdır. MFE'nin teşhis metriği olarak kullanılması bu amaçla uyumludur.

Araştırma notları:

- Mean-reversion için hedef, hard stop ve kısa zaman ufku birlikte optimize edilmeli; Leung–Li modeli stop seviyesi ile optimal hedefin birlikte değiştiğini gösterir.
- Trend/runner tarafında ATR/Chandelier veya aktivasyon + callback mantığı daha uygundur; erken sabit callback whipsaw yaratabilir.
- Partial exit + kalan pozisyon için break-even/trailing, TradingView'in çoklu `strategy.exit` modelinde mekanik olarak desteklenen bir yapıdır; ancak her partial emrin kalan stop miktarını rezerve etmesi gerekir.
- Fan ve ortaklarının çalışmasında volatiliteye göre dinamik trailing eşiği sabit eşikten daha iyi risk-ayarlı sonuç verebildi; yeniden giriş her zaman ek değer üretmedi.
- MFE/MAE canlıda geleceği bilmek için değil, aktivasyon ve stop dağılımını kalibre etmek için kullanılmalı.

Kaynaklar: [Leung–Zhang trailing stop](https://arxiv.org/abs/1701.03960), [Leung–Li mean reversion ve stop-loss](https://arxiv.org/abs/1411.5062), [TradingView Chandelier Exit](https://www.tradingview.com/support/solutions/43000773013-chandelier-exit/), [TradingView çoklu partial exit/trailing dokümantasyonu](https://www.tradingview.com/pine-script-docs/concepts/strategies/), [Bybit trailing callback/activation](https://www.bybit.com/en/help-center/article/Trailing-Stop-Order-Perpetual-and-Futures-Trading), [Fan et al. dynamic trailing thresholds](https://onlinelibrary.wiley.com/doi/10.1002/fut.22507), [MFE yaklaşımı](https://traders.com/documentation/feedbk_docs/1999/03/Abstracts_new/Stendahl/Stendahl9903.html).

## Minimum stop + reclaim birleşik adayı

Run 115 giriş kayıtlarında yapılan özellik incelemesinde LONG tarafında daha yüksek StochRSI reclaim, SHORT tarafında daha düşük reclaim sınırı ve minimum stop-width birlikte hipotez olarak seçildi. Bu seçim aynı snapshot üzerinde yapıldığı için tam dönem sonucu ayrıca iki walk-forward yarısında kontrol edildi.

| Run | Parametre | Sonuç | İşlem | Max DD | PF | Pozitif PnL | Negatif PnL |
|---:|---|---:|---:|---:|---:|---:|---:|
| 125 | min stop 0.53%, long reclaim 0.25, short reclaim 0.80 | −0.725% | 56 | −4.020% | 0.882 | 543.84 | −616.30 |
| 126 | Aynı parametreler, WF-A | −1.189% | 23 | −2.471% | 0.494 | 115.98 | −234.86 |
| 127 | Aynı parametreler, WF-B | +0.426% | 32 | −1.981% | 1.110 | 428.47 | −385.91 |

Run 125 tam dönem sonucu negatif kaldı. Run 127 ikinci yarıda pozitif oldu; run 126 ilk yarıda negatif kaldı. Bu koşu source 17 ile, parametreleri backtest run kaydında saklanarak yapıldı; ayrı bir kod motoru değişikliği yapılmadı.

Run 125 işlem bazında 50 benzersiz pozisyona ayrıldı: 27 kazanan ve 23 kaybeden. Pozitif PnL katkısı yaklaşık `543.31–543.84 USDT`, negatif PnL toplamı `−616.30 USDT` oldu. Run 115’e göre pozitif katkının yaklaşık `%67.5`’i korunurken negatif PnL yaklaşık `%45.8` seviyesine indi. Kaybeden 23 pozisyonun 15’i (`%65.2`) ücret sonrası teorik net MFE pozitif gördü. Kazananlarda gerçekleşen net kâr yaklaşık `543.31 USDT`, teorik net MFE yaklaşık `971.95 USDT`; trailing-stop kazananlarında gerçekleşen net/MFE yaklaşık `%29.0`, take-profit kazananlarında yaklaşık `%91.4` oldu.

Önceki minimum stop-width filtresi, düşük volatilitede ATR stop'unun piyasa gürültüsüne göre fazla dar kaldığı işlemleri hedefliyor; cooldown değildir. Minimum stop-width tek başına olan run115/118/119 sonuçları negatiftir. Birleşik reclaim adayı run127’nin ikinci yarısında pozitif olsa da tam dönem ve WF-A sonuçları negatiftir.

Run 99'da 56 kaybın 49'u (%87.5) yaklaşık 15m review-candle penceresinde pozitif MFE gördü; ortalama MFE %0.199, ortalama MAE %0.501. Bu, gözlemi doğrular fakat kârlı bir canlı kuralı tek başına kanıtlamaz. Run 106, EMA flip exit'lerinin çoğunun zaten negatifte gerçekleştiğini ve teyitsiz/erken rejim çıkışının çözüm olmadığını gösterdi.

Yeni aday kaynak `source_id=14` olarak yerel QuantDinger kütüphanesine kaydedildi. `exit_pending` koruması eklenerek fill beklerken aynı regime-exit emrinin çoğalması engellendi; bu sürüm sonuçları olumlu olmadığı için Demo adayı seçilmedi.

## Yeni tarih aralığında dış-dönem kontrolü

Eylül snapshot’ında seçilen baseline ve source 17 birleşik adayı, 2026-08-12–2026-08-31 tarih aralığında ayrı bir router veri akışıyla yeniden çalıştırıldı. Bu koşu, Eylül snapshot’ından farklı bir dönemdir; Binance-exact değildir ve funding modellenmemiştir.

| Koşu | Sonuç | İşlem kaydı | Max DD | Win rate | PF | Gross profit | Gross loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| Run 128 — source 13 baseline | −22.595% | 329 | −23.184% | 26.444% | 0.272 | 846.23 | −3105.70 |
| Run 129 — source 17, min stop 0.53%, long reclaim 0.25, short reclaim 0.80 | −4.130% | 54 | −4.920% | 51.852% | 0.390 | 263.59 | −676.61 |

Run 128’de sembol, yön ve giriş zamanı ile birleştirilmiş 271 benzersiz pozisyon grubu; run 129’da 50 benzersiz pozisyon grubu bulundu. Çoklu kapanış grubu sayısı sırasıyla 37 ve 3 oldu. Run 129’da benzersiz grupların 26’sı pozitif, 24’ü negatif kapandı. Negatif gruplar long tarafta 13, short tarafta 11 adettir.

Run 129’un sembol bazlı kapanış kayıtlarında LINK `+72.46 USDT`, ADA `+47.29 USDT`, BCH `+1.02 USDT` katkı verdi. SOL `−171.96 USDT`, DOGE `−107.61 USDT`, BNB `−85.44 USDT`, XRP `−79.39 USDT`, BTC `−49.49 USDT`, ETH `−39.44 USDT` ve AVAX `−0.47 USDT` ile negatifti. Zarar gruplarının en yüksek sayısı SOL’da 7, AVAX’ta 4 ve DOGE’de 3 oldu; LINK’te zarar grubu oluşmadı.

Run 129 çıkış kayıtları `39 trailing_stop`, `14 stop_loss` ve `1 take_profit` olarak dağıldı. Kayıt PnL toplamları sırasıyla yaklaşık `+214.50`, `−668.24` ve `+40.72 USDT` oldu. Run 129’da aynı adayın tam Eylül dönemi negatif (`−0.725%`), WF-A negatif (`−1.189%`), WF-B pozitif (`+0.426%`) ve Ağustos dış-dönemi yine negatif (`−4.130%`) sonuç verdi. Böylece Eylül’ün ikinci yarısındaki pozitif kesit yeni dış dönemde tekrarlanmadı.

Koşu esnasında OKX `50011 Too Many Requests`, gecikmiş tarihsel veri ve ADA için fallback uyarıları görüldü. Bu veri sağlayıcı davranışı sonuçların Binance Demo piyasa verisiyle birebir eşdeğer olmadığını gösterir; her iki run da QuantDinger veritabanında `success` ve `completed_trades` olarak kalıcıdır.

## Yeni yöntem: saatlik kanal kırılımı

Araştırma planındaki ilk yeni aday Strategy API V2 ile oluşturuldu, compile edildi ve source `18` olarak yerel source library’ye kaydedildi. Kurallar: tamamlanmış 1h kanal kırılımı, tamamlanmış 4h EMA100 rejim filtresi, 2×ATR başlangıç stopu ve karşı 1h kanal kapanışıyla çıkış. Sabit take-profit ve averaging-down yoktur. Kanal varyantları önceden `24/48/96` saat olarak ayrıldı.

Eylül 1–20 koşuları:

| Run | Kanal | Final totalReturn | Gerçekleşmiş PnL | Dönem sonu açık PnL | Kapanmış PF | Max DD | İşlem |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 130 | 24h | +18.397% | −1057.95 | +2897.60 | 0.729 | −32.017% | 64 |
| 131 | 48h | +1.159% | −2225.49 | +2341.36 | 0.391 | −35.295% | 49 |
| 132 | 96h | +0.387% | −1742.76 | +1781.42 | 0.374 | −25.706% | 34 |

Bu üç koşuda final totalReturn pozitif görünse de kapanmış işlem PnL’si negatiftir. Sonuçta açık kalan 8–9 long pozisyonun mark-to-market değeri final equity’yi yükseltmiştir. Bu nedenle run130–132’yi pozitif gerçekleşmiş sonuç olarak sınıflandırmıyorum. Kapanmış PnL’nin long/short toplamları run130’da `+10.96 / −1068.91`, run131’de `−1257.76 / −967.73`, run132’de `−1047.71 / −695.05 USDT` oldu.

Ağustos 12–31 dış-dönem koşuları:

| Run | Kanal | Final totalReturn | Gerçekleşmiş PnL | Dönem sonu açık PnL | Kapanmış PF | Max DD | İşlem |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 133 | 24h | +51.614% | +5255.17 | −93.72 | 1.883 | −40.975% | 68 |
| 134 | 48h | +79.320% | +7989.09 | −57.11 | 3.005 | −34.761% | 44 |
| 135 | 96h | +112.497% | +11317.33 | −67.67 | 14.827 | −25.710% | 20 |

Run133–135’te kapanmış PnL pozitif olsa da short tarafı sırasıyla `−873.09`, `−541.81` ve `−234.97 USDT` oldu. Max DD `%25.7–%41.0` aralığında kaldı. Eylül ve Ağustos sonuçları arasında büyük rejim farkı bulunduğundan, bu adayın iki adet 20 günlük dönemle genel kârlılığı kanıtlanmış sayılmıyor. Sonuçlar yeni yöntemin StochBB ailesinden ayrı bir ekonomik davranış üretebildiğini gösteren araştırma verisidir; Demo hazırlık onayı değildir.

### Risk-sized pozisyon yönetimi ve yön izolasyonu

Saatlik kanal adayında sabit `target_pct=0.10` ile yüksek nominal açık pozisyon birikimi görüldü. Source 19’da giriş ve çıkış aynı bırakılarak target-percent, `%0.5` equity işlem riski, `%0.2` tahmini tur maliyeti ve 5x kaldıraç üzerinden hesaplandı:

| Run | Dönem / kanal | Gerçekleşmiş PnL | Açık PnL | Kapanmış PF | Max DD |
|---:|---|---:|---:|---:|---:|
| 136 | Eylül / 24h | −508.15 | +1484.28 | 0.756 | −17.814% |
| 137 | Eylül / 48h | −995.47 | +1530.95 | 0.456 | −18.262% |
| 138 | Eylül / 96h | −691.84 | +972.23 | 0.456 | −11.428% |
| 139 | Ağustos / 24h | +3968.53 | −35.05 | 2.284 | −26.405% |
| 140 | Ağustos / 48h | +5458.44 | −21.24 | 3.702 | −23.213% |
| 141 | Ağustos / 96h | +7101.62 | −23.50 | 17.737 | −18.608% |

Risk sizing drawdown’ı azalttı, ancak Eylül kapanmış PnL’sini pozitife çevirmedi. Short kapanış PnL’si bu altı koşunun tamamında negatifti.

Source 20’de aynı kurallarla yalnızca long yönü (`allow_long=1`, `allow_short=0`) çalıştırıldı. Eylül 24h/48h/96h gerçekleşmiş PnL’si `+144.31 / −474.49 / −345.41 USDT`; Ağustos OOS gerçekleşmiş PnL’si `+4898.47 / +5899.78 / +7220.88 USDT` oldu. Bu, short kolunun zarar katkısını görünür kılar; ancak long-only 48h ve 96h Eylül kesitleri de negatif olduğu için short’ları kapatmak tek başına doğrulanmış çözüm değildir. Source20 tanısal yön ayrıştırmasıdır.

Source20 için üçüncü kontrol penceresi olan 2026-08-01–2026-08-20’de long-only gerçekleşmiş PnL 24h/48h/96h için `−708.73 / −428.48 / −320.41 USDT`, kapanmış PF ise `0.251 / 0.343 / 0.363` oldu. Final equity’nin pozitif görünmesi bu koşulda da yaklaşık `2.34–2.47k USDT` açık PnL’den kaynaklandı. 12–31 Ağustos’taki güçlü sonuçların dönem-spesifik olabileceği bu kontrolle görünür hale geldi.

## Saatlik adayda kaybeden işlem MFE/MAE teşhisi

Source20 long-only koşularında sonuç JSON’ındaki `reviewCandles` saatlik OHLC barlarıyla işlem bazlı geriye dönük teşhis yapıldı. Giriş barından çıkış barına kadar yüksek/düşük aralığı tarandı; net MFE hesabında kaydın komisyonu düşüldü. Bu tick sırasını bilmeyen bar-range teşhisidir ve canlıda uygulanabilir bir tepe bilgisi değildir.

| Run | Dönem / kanal | Kapanmış | Kazanan / kaybeden | Kaybedenlerde fiyat MFE pozitif | Kaybedenlerde net MFE pozitif | Kaybeden net MFE ort./medyan | Kaybeden MAE ort./medyan |
|---:|---|---:|---:|---:|---:|---:|---:|
| 142 | Eylül / 24h | 38 | 11 / 27 | 23/27 (`%85.2`) | 18/27 (`%66.7`) | `42.88 / 29.33 USDT` | `−1.97% / −1.95%` |
| 145 | 12–31 Ağustos / 24h | 48 | 10 / 38 | 37/38 (`%97.4`) | 30/38 (`%78.9`) | `52.86 / 34.88 USDT` | `−1.85% / −1.62%` |
| 148 | 1–20 Ağustos / 24h | 29 | 6 / 23 | 23/23 (`%100`) | 20/23 (`%87.0`) | `36.98 / 25.78 USDT` | `−1.43% / −1.25%` |

Run145’te 38 kaybedenin 30’u ücret sonrası teorik net pozitif MFE görmesine rağmen zarar ile kapandı. Run142–148 aralığındaki üç ayrı pencerede ortak desen, kayıpların çoğunun hiç olumlu hareket görmeden doğrudan stop olması değil; kâr görüldükten sonra stop veya karşı kanal kapanışına dönmesidir. Bu, cooldown veya sinyal azaltmanın yerine ayrı bir pozisyon yönetimi araştırmasını gerektiren gözlemdir.

Bu bulgu “peak’i canlıda biliyoruz” anlamına gelmez. MFE/MAE yalnızca aktivasyon eşiği, kâr kilidi, kısmi realize ve ATR/Chandelier benzeri monoton trailing kurallarının hangi kayıp/kazanç dağılımını değiştireceğini ölçmek için kullanılmalıdır. Her yeni yöntemde gerçekleşen PnL ile MFE arasındaki fark ve kaybedenlerin net MFE oranı birlikte raporlanacaktır.

## Yeni pozisyon yönetimi adayı: kâr aktivasyonu + ATR-oranlı trailing

Source20’nin aynı tamamlanmış kanal kırılımı, 4h EMA100 rejim filtresi, risk sizing ve 10 sembollük evreni korunarak source21 oluşturuldu. Değişen ana mekanizma pozisyon korumasıdır: başlangıç stopu 2×ATR kalır; trailing belirli bir `R` kârından sonra etkinleşir; trailing mesafesi başlangıç stopuna göre `R` oranıyla ölçülür; girişin üzerinde minimum kâr kilidi vardır. Sabit take-profit eklenmedi.

| Run | Varyant | Yön | Dönem | Gerçekleşmiş PnL | PF | Max DD | Kapanmış |
|---:|---|---|---|---:|---:|---:|---:|
| 151 | `0.5R activation / 0.75R trail / 0.1% lock` | long-only | Eylül 1–20 | `+775.22` | `1.573` | `−8.288%` | 85 |
| 152 | aynı | long-only | Ağustos 12–31 | `+687.15` | `1.355` | `−12.948%` | 101 |
| 153 | aynı | long-only | Ağustos 1–20 | `+1488.38` | `3.300` | `−2.845%` | 62 |
| 154 | `0.75R activation / 1.0R trail / 0.1% lock` | long-only | Eylül 1–20 | `+1796.28` | `2.649` | `−6.640%` | 66 |
| 155 | aynı | long-only | Ağustos 12–31 | `+1526.44` | `1.803` | `−12.487%` | 90 |
| 156 | aynı | long-only | Ağustos 1–20 | `+1545.43` | `2.838` | `−3.718%` | 57 |
| 157 | aynı | long+short | Eylül 1–20 | `+1224.93` | `1.640` | `−10.298%` | 96 |
| 158 | aynı | long+short | Ağustos 12–31 | `+655.94` | `1.245` | `−13.768%` | 113 |

B varyantı üç ayrı long-only pencerede pozitif gerçekleşmiş PnL verdi. Long+short toplamı da pozitif kaldı; ancak yön ayrımı short kolunun negatif olduğunu gösterdi: run157 long `+1727.35`, short `−502.42 USDT`; run158 long `+1432.30`, short `−776.36 USDT`. Bu nedenle toplam performans short düzeldiği için değil, long katkısı short zararını aştığı için pozitiftir.

Source21 B kaybeden MFE teşhisi: run154’te kaybeden `32` işlemin `23`’ü, run155’te `47` işlemin `37`’si, run156’da `26` işlemin `22`’si ücret sonrası teorik net MFE pozitif gördü. Kazanan gerçekleşen net/MFE yakalama oranları sırasıyla `%61.9`, `%57.8`, `%57.7` oldu. Kâr kilidi source20’ye göre yakalamayı iyileştirdi; yine de kaybedenlerin çoğunun önce pozitif hareket görmesi tamamen çözülmedi.

Bu varyant araştırma adayıdır; Binance Demo’ya hazır değildir. Veri Binance-exact değil, funding/mark-price/taker akışı modellenmiyor, short kolu negatiftir ve max DD `%3.7–%13.8` aralığındadır. Sonuçlar, yeni pozisyon yöneticisinin daha fazla tarihsel pencere ve gerçek Binance Demo gözlemiyle doğrulanması gerektiğini gösterir.

## Yeni çakışmayan holdout sonuçları

Source20 baseline ile source21 B aynı 10 sembol, 20 gün, 5x, `%0.5` equity risk, 24h kanal ve long-only koşullarında önceki Ağustos/Eylül aralıklarından ayrılmış üç pencereye taşındı:

| Run | Source | Dönem | Gerçekleşmiş PnL | PF | Max DD | Kapanmış |
|---:|---|---|---:|---:|---:|---:|
| 159 | source20 baseline | 1–20 Haziran | `−222.76` | `0.095` | `−4.770%` | 6 |
| 160 | source21 B | 1–20 Haziran | `+26.05` | `1.253` | `−1.617%` | 7 |
| 161 | source20 baseline | 21 Haziran–10 Temmuz | `+84.08` | `1.148` | `−8.560%` | 21 |
| 162 | source21 B | 21 Haziran–10 Temmuz | `−310.38` | `0.639` | `−7.296%` | 41 |
| 163 | source20 baseline | 11–30 Temmuz | `−594.79` | `0.385` | `−7.355%` | 32 |
| 164 | source21 B | 11–30 Temmuz | `−343.83` | `0.541` | `−5.404%` | 39 |

Her koşuda 10/10 sembol kullanıldı, sembol atlanmadı ve backtest audit geçti. Source21 B kaybedenlerinin net MFE pozitif oranı run160/162/164 için `3/5`, `23/28`, `23/27` oldu. Bu, daha önceki MFE teşhisinin yeni dönemlerde de tekrarlandığını; ancak kâr-kilidinin tek başına sonucu pozitife çevirmediğini gösterir.

Source21 B long+short run165–167’de gerçekleşmiş PnL olarak `−144.62 / −1003.02 / −491.14 USDT` verdi. Short katkıları sırasıyla `−169.91 / −707.27 / −151.38 USDT` idi. Kanalı 48h/96h yapan long-only run168–173 sonuçları da tutarlı edge üretmedi: 48h `+26.05 / −382.73 / −359.54`, 96h `+26.04 / −294.08 / −225.99 USDT`.

Önceki Eylül koşularında daha az zarar veren Peak Continuation strict pullback/structure/volume varyantı source10 ile run174–176’da aynı holdout’larda çalıştırıldı. Sonuçlar `−19.27 / −38.37 / −39.49 USDT`, kapanmış işlem sayıları `6 / 5 / 9` oldu. Bu kaynak 5m alt veri kullandığı için koşul sırasında OKX `50011` ve eksik tarihsel veri/fallback uyarıları görüldü; güçlü performans kanıtı olarak kullanılmadı.

Source22, source21 B’ye tamamlanmış 4h BTC/USDT EMA100 global rejim kapısı ekledi. Aynı long-only, 24h kanal, 10 sembol, 5x ve `%0.5` equity-risk holdout’larında run177–179 gerçekleşmiş PnL olarak `−53.37 / −435.52 / −444.97 USDT`, PF olarak `0.477 / 0.425 / 0.399`, max DD olarak `−1.494% / −7.296% / −5.268%` verdi. Her koşuda 10/10 sembol kullanıldı ve audit geçti. Global BTC filtresi source21 B’ye göre iyileşme sağlamadı; bu varyant eleme/araştırma kaydıdır.

Source23, giriş zamanlamasını değiştiren breakout-retest state-machine adayıdır. Tamamlanmış 1h breakout yalnızca setup kurdu; en fazla 6 bar içinde ATR toleranslı retest/reclaim teyidi gelirse source21 B’nin aynı ATR stopu ve kâr-kilidiyle giriş yapıldı. Long+short run180–185 gerçekleşmiş PnL olarak `+288.10 / −146.41 / −427.68 / −761.94 / −89.40 / +1045.17 USDT` verdi. Long-only run186–191 sonuçları `+108.06 / −185.05 / +2.41 / +26.84 / +284.44 / +1086.16 USDT` oldu; ilk değer tek kapanmış işleme dayanıyor. Strict 3-bar/0.5-ATR kontrol run192–194’te `0.00 / −155.59 / −10.87 USDT` verdi ve ilk pencerede hiç işlem açmadı. Source23 pozisyon yönetimi ve giriş zamanlaması açısından yeni araştırma adayıdır; henüz Demo-ready değildir.

Source23 run180–185’te kaybedenlerin net MFE pozitif oranları `18/24`, `24/26`, `27/33`, `28/35`, `24/28`, `20/25` oldu; kazanan net/MFE yakalama oranları yaklaşık `%43.0 / %46.2 / %44.4 / %51.9 / %61.8 / %58.7` idi. Retest girişi işlem kalitesini değiştirdi, fakat kâr gördükten sonra tersine dönen kayıpları ortadan kaldırmadı. Sembol katkısı da pencereye göre değişti; kalıcı tek-coin avantajı gözlenmedi.

Holdout fazı kararı: source21 B bazı dönemlerde baseline’dan daha az zarar veren ve kâr geri vermeyi azaltan bir araştırma varyantıdır; fakat yeni dönemlerde kârlılık tutarlı değildir. Source22 global BTC filtresi bu açığı kapatmadı. Source23 retest girişi bazı pencerelerde kaybı azalttı, ancak genel istikrar kanıtlanmadı. Kanal süresi, yön veya trailing eşiğini tek başına değiştirerek genellenebilir Demo adayı elde edilmedi.

## Karar

Net-lock + ratchet, Peak Continuation için test edilmeye değer bir pozisyon yöneticisi olarak kaldı; ancak iki walk-forward alt döneminden biri negatif olduğu için Binance Demo'ya otomatik olarak hazır kabul edilmemelidir. Qullamagi ve Triple EMA, yalnızca çıkış değiştirilerek Demo adayı olmadı. StochBB için sıradaki kontrollü aday sabit/orta-band hedefi + kısa tez time-stop + hard stop kombinasyonudur.

Perpetual işlemlerde funding, mark-price tetikleme, spread, kısmi dolum ve gerçek fill gecikmesi bu backtestte eksiktir; Demo öncesi ayrıca doğrulanmalıdır. Tarihsel veri katmanında OKX 50011 rate-limit görüldüğünde QuantDinger Bitget fallback kullandı; koşular tamamlandı ancak sembol/veri sağlayıcısı provenance'ı UI'da kontrol edilmelidir. Agent Gateway backtest işi `AGENT_JOB_EXPIRED` ile terminal oldu ve ücretsizdi; yerel servis koşuları UI'a başarıyla yazıldı.

Backtest audit reason alanı `VARCHAR(64)` olduğu için uzun makine-okunabilir exit reason'larını kaydetmeyi engelliyordu. `qd_backtest_trades.reason` kalıcı migration'da `TEXT` yapıldı ve mevcut veritabanına uygulandı.

## Kaynaklar

- [TradingView resmi Chandelier Exit açıklaması](https://www.tradingview.com/support/solutions/43000773013-chandelier-exit/)
- [TradingView Turtle/Donchian topluluk örneği](https://www.tradingview.com/script/TnkefIeX-Kloom-Turtle-System-with-Trend-Filter/)
- [Kaminski ve Lo: When Do Stop-Loss Rules Stop Losses?](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee)
- [Leung ve Li: mean reversion, transaction costs and stop-loss exit](https://arxiv.org/abs/1411.5062)
- [Monash: trend-following strategies for crypto investors](https://www.monash.edu/__data/assets/pdf_file/0011/3744821/Trend-following-Strategies-for-Crypto-Investors.pdf)
- [MFE/MAE ölçüm yaklaşımı](https://traders.com/documentation/feedbk_docs/1999/03/Abstracts_new/Stendahl/Stendahl9903.html)
