# AliExpress API kapsam denetimi

- İncelenen: 18 bölüm / 200 benzersiz API.
- Seçilen: 24 (token yenileme dahil).
- Kod/yerel test tamam: 23; yalnız hazırlık: 1.
- Mevcut test: 193 çalıştı, 0 başarısız, 0 hata, 1 atlandı.
- Bu kapsam, canlı satış veya API yetkisi onayı değildir. Afterpay canlı ödeme eksiktir.
- Yeni yardımcı okumalar: affiliate keşif/detay ve EAN katalog bilgisi; zamanlayıcıya otomatik bağlanmadı.
- Affiliate komisyon/son satış hacmi stok veya kâr sayılmaz. EAN sahiplik veya ürün uygunluğu kanıtı değildir.

## Canlı okuma sonuçları

- affiliate_query: {"status": "blocked", "diagnostic": "aliexpress.affiliate.product.query: InsufficientPermission"}
- affiliate_detail: {"status": "blocked", "diagnostic": "aliexpress.affiliate.productdetail.get: InsufficientPermission"}
- ean_info: {"status": "not_sent", "reason": "no_checksum_valid_actual_source_EAN"}

## Tüm katalog

| Bölüm | Yöntem | Durum | Gerekçe |
|---|---|---|---|
| System Tool | `/auth/token/create` | not_selected | İlk yetkilendirme/özel güvenlik tokenı; mevcut yenileme akışı için ek yöntem gerekmiyor. |
| System Tool | `/auth/token/refresh` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| System Tool | `/auth/token/security/create` | not_selected | İlk yetkilendirme/özel güvenlik tokenı; mevcut yenileme akışı için ek yöntem gerekmiyor. |
| System Tool | `/auth/token/security/refresh` | not_selected | İlk yetkilendirme/özel güvenlik tokenı; mevcut yenileme akışı için ek yöntem gerekmiyor. |
| AE-Affiliate | `aliexpress.affiliate.link.generate` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.category.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.featuredpromo.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.featuredpromo.products.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.hotproduct.download` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.hotproduct.query` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.order.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.order.list` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.order.listbyindex` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.product.shipping.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.productdetail.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Affiliate | `aliexpress.affiliate.product.query` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Affiliate | `aliexpress.affiliate.promotion.info.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.product.sku.detail.get` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Affiliate | `aliexpress.affiliate.product.smartmatch` | not_selected | Komisyon, kampanya veya yinelenen keşif işlevi; mevcut dropshipping için gerekli değil. |
| AE-Logistics | `aliexpress.asf.package.shipping.service.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.order.shipping.service.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.seller.address.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local2local.split.quantity.rts.pack` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.platform.logistics.rts` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.platform.logistics.document.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.platform.logistics.repack` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.dbs.declareship` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local2local.sub.declareship` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.dbs.declare.ship.modify` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local.unreachable.preference.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local.unreachable.preference.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local2local.transfer.to.offline` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.fulfillment.package.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.seller.fulfillment.info.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.local2local.self.pickup.declareship` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Logistics | `aliexpress.asf.shipment.pack` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.list.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.postproduct.redefining.createproductgroup` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.productgroups.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.postproduct.redefining.setgroups` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.postproduct.redefining.onlineaeproduct` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.postproduct.redefining.offlineaeproduct` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.batch.product.delete` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.batch.product.inventory.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.multi.stock.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.feed.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.hscode.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.schema.product.full.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.schema.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.carmodel.sixlevel.oe.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.schema.product.instance.post` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.template.save` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.template.delete` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.image.generate` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.wholesale.supplySigned` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.ladder.price.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.customize.product.submit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.customize.template.product.submit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.offer.redefining.supportsizeprop` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.offer.redefining.supportwigupgrade` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.offer.redefining.supportnewsizechartlist` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.customize.product.detail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.customize.product.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.data.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.wholesale.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.template.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.template.detail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.design.template.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.template.config` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.design.template.detail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.postproduct.redefining.getsizechartinfobytype` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.sale.prop.sequence.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.ladder.price.calculate` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.distribution.product.post` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.feed.submit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.merchant.profile.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.batch.product.price.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.customize.font.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.info.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.product.bind.brandmanufacturer` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.post` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Product Management | `aliexpress.solution.product.inventory.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.inventory.invitation.reject.reason.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.inventory.invitation.ticket.refuse` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.inventory.invitation.ticket.accept` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.stocks.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.stocks.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.products.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.prices.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.post` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.seller.self.hscode.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.plat.hscode.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.inventory.invitation.tickets.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.seller.hosting.publish.limit.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.seller.hosting.publish.limit.query.by.country` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Aliexpress-Direct-Product | `aliexpress.local.service.product.status.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.product.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.product.prices.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.product.status.update` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.products.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.product.post` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.products.stock.edit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-KoreanCrossborder-Product | `aliexpress.offer.local.cb.product.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.solution.order.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.seller.orderlist.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.new.redefining.findorderbyid` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.solution.order.receiptinfo.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.seller.order.decrypt` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.redefining.verifycode` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.redefining.sendcode` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Order & Transaction | `aliexpress.trade.redefining.confirmshippingmode` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.invoice.sellerInvoicingApplyInfo.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.tax.invoice.queryBrazilInvoiceInfo` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.invoice.sellerInvoicingResult.push` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.tax.hscode.queryRegulatoryAttributesInfoWithHsCode` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.tax.hscode.selectRegulatoryAttributesOptions` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.trade.tax.invoice.UploadBrazilInvoice` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.arrearsdetail.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.feeitem.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.settlefeeitemdetail.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.settleorderdetail.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.settlebilldetail.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Settlement | `aliexpress.fund.merchant.period.unsettleorderdetail.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Custmize | `aliexpress.customize.product.info.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Custmize | `aliexpress.customize.product.template.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Custmize | `aliexpress.customize.product.info.audit.result.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Custmize | `aliexpress.customize.product.info.create` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Dropshipper | `aliexpress.ds.image.searchV2` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.category.tree.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.order.afterpay` | preparation_only | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.order.create` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.category.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.trade.ds.order.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.freight.query` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.member.benefit.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.order.tracking.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.feed.itemids.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.logistics.buyer.freight.calculate` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.product.specialinfo.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.product.wholesale.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.product.get` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.search.event.report` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Dropshipper | `aliexpress.ds.text.search` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Image | `aliexpress.photobank.redefining.uploadimageforsdk` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Image | `aliexpress.photobank.redefining.delunusephoto` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Image | `aliexpress.photobank.redefining.listimagepagination` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Image | `aliexpress.image.redefining.uploadtempimageforsdk` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| AE-Seller | `global.seller.channel.info.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.profile.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.manufacture.detail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.Address.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.agreement.sign.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.msr.detail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.msr.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.queryThemeDetail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.manufacture.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.product.post.limit` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.queryPlanDetail` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.searchPlansForSeller` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.pagePlanRegistrations` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.plan.chance.download.all` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.plan.chance.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.arrangement.plan.list` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.searchThemes` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.apply.all` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.plan.chance.download` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.plan.products.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `ae.merchant.assortment.seller.plan.dashboard.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.applyBiddableItem` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.searchBiddableItems` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.seller.operation.plan.searchThemePlans` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.private.file.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Seller | `aliexpress.merchant.diagnosis.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-Category&Attributes | `aliexpress.category.tree.list` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.category.redefining.getchildattributesresultbypostcateidandpath` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.solution.seller.category.tree.query` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.category.itemQualification.list` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.category.qualifications.list` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.category.redefining.queryCascadeProperties` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Category&Attributes | `aliexpress.solution.sku.attribute.query` | not_selected | Satıcı ürün yayınlama nitelikleri veya mevcut DS kategori işlevinin tekrarı; eBay taxonomy yerine kullanılamaz. |
| AE-Refund&return | `aliexpress.issue.issuelist.get` | not_selected | Satıcı/kanal ihtilaf bağlamı ve alıcı yetkisi doğrulanmadı; ilk iadeler manuel, otomatik anlaşma/geri ödeme yok. |
| AE-Refund&return | `aliexpress.issue.detail.get` | not_selected | Satıcı/kanal ihtilaf bağlamı ve alıcı yetkisi doğrulanmadı; ilk iadeler manuel, otomatik anlaşma/geri ödeme yok. |
| AE-Refund&return | `aliexpress.issue.image.upload` | not_selected | Satıcı/kanal ihtilaf bağlamı ve alıcı yetkisi doğrulanmadı; ilk iadeler manuel, otomatik anlaşma/geri ödeme yok. |
| AE-Refund&return | `aliexpress.issue.solution.agree` | not_selected | Satıcı/kanal ihtilaf bağlamı ve alıcı yetkisi doğrulanmadı; ilk iadeler manuel, otomatik anlaşma/geri ödeme yok. |
| AE-Refund&return | `aliexpress.issue.solution.save` | not_selected | Satıcı/kanal ihtilaf bağlamı ve alıcı yetkisi doğrulanmadı; ilk iadeler manuel, otomatik anlaşma/geri ödeme yok. |
| AE-Freight (Shipment) | `aliexpress.freight.redefining.listfreighttemplate` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.shipping.service.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.batch.declareship` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.declareship.modify` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.sub.declareship` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.split.quantity.rts.pack` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.platform.logistics.document.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.platform.logistics.rts` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.platform.logistics.repack` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AliExpress Direct Logistic | `aliexpress.asf.local.supply.seller.address.get` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
| AE-EAN Code | `aliexpress.product.eancode.info.query` | implemented_local_tested | Mevcut DE/EUR tedarik akışı veya isteğe bağlı ürün/EAN araştırması; canlı yetki/akış ayrıca doğrulanır. |
| CSP-Seller | `global.seller.relation.query` | not_selected | AliExpress satıcı, yerel/hosting, özel ürün, sevkiyat, hesaplaşma veya başka iş modeli; mevcut alıcı rolü için seçilmedi. |
