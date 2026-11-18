import unittest

from pc_advisor import checks, listing, search
from pc_advisor.models import Need, Offer


def offer(**kw):
    base = dict(source="gmktec", shop="GMKtec", title="t", url="https://x", price_eur=500.0, cpu="AMD Ryzen 7 8845HS",
                ram_gb=32, ram_soldered=False, form="mini")
    base.update(kw)
    return Offer(**base)


def codes(findings, level=None):
    return {f["code"] for f in findings if level is None or f["level"] == level}


class TestChecks(unittest.TestCase):
    def test_soldered_ram_below_minimum_is_a_blocker(self):
        need = Need(min_ram_gb=32)
        f = checks.check(offer(ram_gb=16, ram_soldered=True, cpu="AMD Ryzen 5 PRO 6650H"), need)
        self.assertIn("ram_soldered_below_min", codes(f, "blocker"))

    def test_upgradable_ram_below_minimum_is_a_warning(self):
        f = checks.check(offer(ram_gb=16, ram_soldered=False), Need(min_ram_gb=32))
        self.assertIn("ram_below_min_upgradable", codes(f, "warning"))
        self.assertFalse(checks.blockers(f))

    def test_weak_cpu_budget_and_mac(self):
        self.assertIn("cpu_too_weak", codes(checks.check(offer(cpu="Intel N150"), Need())))
        self.assertIn("over_budget", codes(checks.check(offer(price_eur=900), Need(budget_max=500))))
        self.assertIn("not_macos", codes(checks.check(offer(), Need(system="macos"))))

    def test_shop_policy_and_keyboard(self):
        self.assertIn("return_policy", codes(checks.check(offer(), Need())))  # GMKtec: 7 days + 15 %
        laptop_de = offer(source="lapstore", form="laptop")
        self.assertIn("keyboard_layout", codes(checks.check(laptop_de, Need())))

    def test_bilingual_messages(self):
        for f in checks.check(offer(ram_gb=8, ram_soldered=True), Need(min_ram_gb=16)):
            self.assertTrue(f["en"] and f["fr"])


class TestRanking(unittest.TestCase):
    def test_blockers_are_dropped_and_better_value_ranks_first(self):
        offers = [
            offer(title="weak", cpu="Intel N150", price_eur=200),
            offer(title="good", cpu="AMD Ryzen 7 8845HS", price_eur=600),
            offer(title="ok", cpu="AMD Ryzen 7 7730U", price_eur=600),
        ]
        ranked, dropped = search.rank(offers, Need(budget_max=800, min_ram_gb=32))
        self.assertEqual(dropped, 1)
        self.assertEqual([r["offer"]["title"] for r in ranked], ["good", "ok"])
        self.assertIn("parts", ranked[0]["score"])

    def test_ready_offers_beat_cheap_ones_that_need_parts(self):
        # Found on a live run: a 109 € refurbished box with 4 GB ranked first. Never again.
        offers = [
            offer(title="cheap 4GB", cpu="AMD Ryzen 9 6900HX", ram_gb=4, ram_soldered=False, price_eur=109),
            offer(title="barebone", cpu="AMD Ryzen 9 8945HS", ram_gb=None, barebone=True, price_eur=460),
            offer(title="complete", cpu="AMD Ryzen 7 7735HS", ram_gb=32, price_eur=570),
        ]
        ranked, _ = search.rank(offers, Need(budget_max=900, min_ram_gb=32))
        self.assertEqual(ranked[0]["offer"]["title"], "complete")
        self.assertTrue(ranked[0]["ready"])
        self.assertFalse(ranked[-1]["ready"])


class TestListing(unittest.TestCase):
    def test_pasted_listing(self):
        text = "Lenovo ThinkCentre M920q Tiny\ni5-8500T, 16 Go DDR4, SSD 256 Go NVMe, très bon état"
        result = listing.analyse(text, 150, Need(min_ram_gb=32))
        self.assertEqual(result["offer"]["ram_gb"], 16)
        self.assertIn("i5-8500T", result["offer"]["cpu"])
        self.assertFalse(result["offer"]["verified"])
        self.assertTrue(result["ask_the_seller"] and result["test_on_site"])


if __name__ == "__main__":
    unittest.main()
