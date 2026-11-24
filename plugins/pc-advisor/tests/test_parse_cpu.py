import unittest

from pc_advisor import cpu, parse


class TestParse(unittest.TestCase):
    def test_cpu_names(self):
        cases = {
            "GMKtec NucBox K8 Plus AMD Ryzen™ 7 8845HS": "AMD Ryzen 7 8845HS",
            "GMKtec Nucbox M8 AMD Ryzen™ 5 PRO 6650H Mini PC": "AMD Ryzen 5 PRO 6650H",
            "GMKtec EVO-X2 AMD Ryzen™ AI Max+ 395 Mini PC": "AMD Ryzen AI Max+ 395",
            "GMKtec EVO-X1 AMD Ryzen™ AI 9 HX 370": "AMD Ryzen AI 9 HX 370",
            "Beelink SER9 Pro AMD Ryzen™ 7 H 255": "AMD Ryzen 7 H 255",
            "Ninkear U9 Pro AI Performance Laptop Intel® Core™ Ultra 9 185H": "Core Ultra 9 185H",
            "Mac mini reconditionné avec puce Apple M4 Pro, CPU 12 cœurs": "Apple M4 Pro",
            "Dell Latitude 7430 Intel Core i5-1245U": "Intel Core i5-1245U",
            "GMKtec NucBox G3 Plus Intel® Twin Lake N150": "N150",
            "Intel® Celeron® J3160 (GN31) / 4GB RAM +128GB SSD": "Celeron J3160",
        }
        for text, expected in cases.items():
            self.assertIn(expected.replace("Intel ", ""), parse.cpu(text), text)

    def test_ram_is_not_storage_nor_vram(self):
        self.assertEqual(parse.ram_gb("32GB RAM +1TB SSD / Europe"), 32)
        self.assertEqual(parse.ram_gb("16 Go de RAM + SSD de 512 Go"), 16)
        self.assertEqual(parse.ram_gb("Intel® Core™ Ultra 5 125H / LPDDR5 24GB+1TB SSD"), 24)
        self.assertEqual(parse.ram_gb("Initialement commercialisé en octobre 202416 Go de mémoire unifiée"), None)
        self.assertEqual(parse.ram_gb("blah 202416 Go de mémoire unifiée ... 16 Go de mémoire unifiée"), 16)
        self.assertIsNone(parse.ram_gb("RTX 3050 4GB GDDR6"))
        self.assertIsNone(parse.ram_gb("SSD de 512 Go"))

    def test_storage(self):
        self.assertEqual(parse.storage_gb("32GB RAM +1TB SSD"), 1000)
        self.assertEqual(parse.storage_gb("16 Go de RAM + 512 Go SSD"), 512)
        self.assertEqual(parse.storage_gb("SSD de 256 Go"), None)  # word order handled by the Apple connector

    def test_soldered_and_barebone(self):
        self.assertTrue(parse.ram_soldered("16 Go de mémoire LPDDR4 à 3733 MT/s (soudée, non évolutive)"))
        self.assertFalse(parse.ram_soldered("DDR5 5600 MT/s, SO-DIMM ×2, extensible jusqu'à 48 Go"))
        self.assertIsNone(parse.ram_soldered("32GB RAM"))
        self.assertFalse(parse.ram_soldered("i5-8500T, 16 Go DDR4, SSD 256 Go"))
        self.assertTrue(parse.ram_soldered("16GB LPDDR5 6400"))
        self.assertTrue(parse.ram_soldered("32 Go de RAM", "Intel Core Ultra 7 258V"))  # Lunar Lake: on package
        self.assertTrue(parse.ram_soldered("64GB", "AMD Ryzen AI Max+ 395"))
        self.assertTrue(parse.is_barebone("Barebone (sans SSD/RAM/System) / Europe"))
        self.assertTrue(parse.is_barebone("Barebone(ohne RAM+ohne SSD)"))


class TestCpuTiers(unittest.TestCase):
    def tier(self, name):
        return cpu.classify(name)["tier"]

    def test_classic_traps(self):
        self.assertEqual(self.tier("Intel N150"), 1)
        self.assertEqual(self.tier("Intel Core i5-6500"), 1)
        self.assertLess(self.tier("AMD Ryzen 7 7730U"), self.tier("AMD Ryzen 7 7735HS"))
        self.assertLess(self.tier("AMD Ryzen 7 7735HS"), self.tier("AMD Ryzen 9 8945HS") + 1)
        self.assertEqual(self.tier("AMD Ryzen AI Max+ 395"), 5)
        self.assertIn("Zen 3", " ".join(cpu.classify("AMD Ryzen 7 7730U")["notes"]))

    def test_intel_and_apple(self):
        self.assertEqual(self.tier("Intel Core i5-8500T"), 2)
        self.assertEqual(self.tier("Intel Core i7-10700"), 3)
        self.assertEqual(self.tier("Core Ultra 9 185H"), 5)
        self.assertEqual(self.tier("Apple M4"), 4)
        self.assertEqual(self.tier("Apple M5 Pro"), 5)
        self.assertEqual(self.tier(""), 0)


if __name__ == "__main__":
    unittest.main()
