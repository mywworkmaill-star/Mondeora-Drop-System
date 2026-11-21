# Claude-mem / Mondeora

Bu bağlantı yalnız yerel hafıza deposudur; ilan, fiyat, stok veya sipariş değiştirmez.

- Kaynak kod: `C:/Users/Administrator/claude-mem`, sabit sürüm `v15.18.5`.
- Runtime: `C:/Users/Administrator/claude-mem-runtime`.
- Worker: `http://127.0.0.1:37709`; kayıtlar `C:/Users/Administrator/.claude-mem` altında.
- Proje kökü `claude_mem_bridge.py`: `src/jobs.py` kaydını AST olarak okur; engine veya token istemcilerini import etmez.
- Kaynak: kayıtlı işlerin `data/jobs/last_*.json` dosyaları. Yalnız son görülen sonuç aktarılır; iki tarama arasında üzerine yazılan ara koşumlar için tam geçmiş garantisi yoktur.
- Aktarılan: iş adı, izinli status/mode, doğrulanmış zaman, süre ve izinli sayısal sayaçlar. Ham sonuç, hata metni, token, URL, müşteri/sipariş bilgisi aktarılmaz.
- `sourceFingerprint` ile worker tarafında tekrarlara karşı koruma; her yeni kayıt exact ID üzerinden geri okunur. Geri-okuma doğrulanmadan checkpoint yazılmaz.
- `data/claude_mem_checkpoint.json`: yalnız hash ve observation ID. `data/claude_mem_sync.lock`: OS tarafından yönetilen süreç kilidi; normal kullanımda silmeyin.
- Son çalışma: `data/jobs/last_claude_mem_sync.json`.
- Script `mondeora_claude_mem_sync.sh`: worker yoksa başlatır, sonra bridge çalıştırır. `no_agent` zamanlaması ücretli LLM çalıştırmaz.
- Telemetri, observer, Chroma, cloud sync, Notion ve AI dashboard refresh kapalıdır. Observer/Chroma/cloud ayarları açılırsa bridge fail-closed durur.
- Hermes'in global hafıza sağlayıcısı ve MCP ayarları değiştirilmemiştir; bu, sohbetleri otomatik kaydeden bir eklenti kurulumu değildir.

## Manuel çalıştırma

Proje kökünden:

```bash
"C:/Program Files/Python311/python.exe" claude_mem_bridge.py
```

Worker'ın başlatılmasını da denetlemek için:

```bash
bash "C:/Users/Administrator/AppData/Local/hermes/scripts/mondeora_claude_mem_sync.sh"
```

## Yerel hafızada arama

Worker API:

`GET /api/search?query=health_check&type=observations&project=Mondeora-Drop-System&platformSource=hermes&format=json&limit=10`

Kesin kayıt: `GET /api/observation/ID`. Dönen `project`, narrative ve metadata fingerprint ayrıca doğrulanmalıdır.

## Durdurma

Önce Hermes scheduler'da `mondeora-claude-mem-sync` görevini duraklatın. Ardından gerekirse `claude-mem stop` kullanın; görev açıkken worker bir sonraki turda tekrar başlatılır. Hafıza verilerini silmeyin.
