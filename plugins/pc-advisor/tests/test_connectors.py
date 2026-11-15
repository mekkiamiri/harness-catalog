"""Connectors are tested on small synthetic samples that mimic each site's structure (no real page is stored)."""

import unittest

from pc_advisor.connectors import apple_fr, shopify
from pc_advisor.sources import by_id

SHOPIFY_CATALOG = [
    {
        "title": "GMKtec NucBox K8 Plus AMD Ryzen™ 7 8845HS", "handle": "k8-plus", "product_type": "Mini PC",
        "body_html": "<p>DDR5 5600 MT/s, SO-DIMM ×2, extensible jusqu'à 48 Go</p>",
        "variants": [
            {"id": 1, "title": "Barebone (sans SSD/RAM/System) / European", "price": "389.99", "available": True},
            {"id": 2, "title": "32GB RAM +1TB SSD / European", "price": "829.99", "available": True},
            {"id": 3, "title": "64GB RAM +1TB SSD / European", "price": "1069.99", "available": False},
        ],
    },
    {
        "title": "Ninkear S14 Laptop", "handle": "s14", "product_type": "",
        "body_html": "<p>AMD Ryzen 5 6600H, 16GB LPDDR5 memory</p>",
        "variants": [{"id": 4, "title": "AMD Ryzen™ 5 6600H / 16G RAM +512GB SSD", "price": "569.99", "available": True}],
    },
    {"title": "USB Type-C Laptop Dock Station", "handle": "dock", "body_html": "",
     "variants": [{"id": 5, "title": "11 in 1 HUB", "price": "36", "available": True}]},
]

APPLE_NEW = (
    '"prices":{"m6-12-12":{"comparativeDisplayPrice":"À partir de <span class=\\"nowrap\\">1 049 €</span>","amount":1049.00,"promoSavings":null},'
    '"m5pro-18-20":{"comparativeDisplayPrice":"À partir de 2 219 €","amount":2219.00,"promoSavings":null}}'
    "<li>Mac mini, puce M6, CPU 12 cœurs, GPU 12 cœurs, 32 Go de mémoire, 1 To de stockage</li>"
    "<li>Mac mini, puce M6, CPU 12 cœurs, GPU 12 cœurs, 16 Go de mémoire, 256 Go de stockage</li>"
    "<li>Mac mini, puce M5 Pro, CPU 18 cœurs, GPU 20 cœurs, 64 Go de mémoire, 1 To de stockage</li>"
)
APPLE_REFURB_LISTING = (
    '<a href="/fr/shop/product/fu9d3f/a/Mac-mini-reconditionn%C3%A9-avec-puce-Apple-M4?fnode=1">x</a>'
    '<a href="/fr/shop/product/fu9d3f/a/Mac-mini-reconditionn%C3%A9-avec-puce-Apple-M4">dup</a>'
    '<a href="/fr/shop/product/abcd12/a/MacBook-Air-reconditionn%C3%A9">other</a>'
)
APPLE_REFURB_PAGE = (
    "<title>Mac\xa0mini reconditionné avec puce Apple\xa0M4, CPU 10\xa0cœurs, GPU 10\xa0cœurs - Apple (FR)</title>"
    '"description":"Initialement commercialisé en octobre 202416 Go de mémoire unifiée"'
    '"currentPrice":{"amount":"<span>Maintenant</span>809,00 €","raw_amount":"809.00"}'
    '"value":"16 Go de mémoire unifiée" ... SSD de 256 Go ... 120 Go/s de bande passante mémoire'
)


class TestShopify(unittest.TestCase):
    def test_offers_from_catalog(self):
        offers = shopify.offers_from(by_id("gmktec"), SHOPIFY_CATALOG, 0)
        self.assertEqual(len(offers), 4)  # the dock is not a computer
        bare, full, out, laptop = offers
        self.assertTrue(bare.barebone)
        self.assertIsNone(bare.ram_gb)
        self.assertEqual((full.ram_gb, full.storage_gb, full.ram_soldered), (32, 1000, False))
        self.assertFalse(out.available)
        self.assertEqual(laptop.form, "laptop")
        self.assertTrue(laptop.ram_soldered)
        self.assertTrue(full.url.endswith("/products/k8-plus?variant=2"))


class TestApple(unittest.TestCase):
    def test_new_starting_prices(self):
        offers = apple_fr.new_offers(APPLE_NEW, "Mac mini", "https://www.apple.com/fr/shop/buy-mac/mac-mini", 0)
        by_chip = {o.cpu: o for o in offers}
        m6 = by_chip["Apple M6"]
        self.assertEqual((m6.price_eur, m6.ram_gb, m6.storage_gb), (1049.0, 16, 256))
        self.assertTrue(m6.starting_price)
        self.assertEqual(by_chip["Apple M5 Pro"].ram_gb, 64)

    def test_refurb(self):
        links = apple_fr.refurb_links(APPLE_REFURB_LISTING, "mac-mini")
        self.assertEqual(len(links), 1)
        offer = apple_fr.refurb_offer(APPLE_REFURB_PAGE, links[0], "mini", 0)
        self.assertEqual((offer.price_eur, offer.ram_gb, offer.storage_gb, offer.cpu), (809.0, 16, 256, "Apple M4"))
        self.assertEqual(offer.condition, "refurbished")


if __name__ == "__main__":
    unittest.main()
