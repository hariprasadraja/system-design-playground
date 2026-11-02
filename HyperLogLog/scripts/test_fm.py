"""Checks of paper definitions, data semantics, merging and finite-width edges."""

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

from HyperLogLog.scripts.fm_common import PHI, customer_stream, first_zero, rho, small_visits
from HyperLogLog.scripts.fm_math import phi_product, psi, q_exact


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


single = load("fm_single", "01-fm-bitmask.py")
multi = load("fm_multi", "fm_pcsa.py")


class PaperDefinitions(unittest.TestCase):
    def test_two_customer_distribution_by_enumeration(self):
        # Two customers can fill at most two distinct rank cells.
        probabilities = [q_exact(2, k) - q_exact(2, k + 1) for k in range(3)]
        self.assertEqual(probabilities, [0.25, 0.5, 0.25])
        self.assertEqual(q_exact(0, 0), 1)
        self.assertEqual(q_exact(0, 1), 0)

    def test_constant_and_distribution_calibration(self):
        self.assertAlmostEqual(phi_product(10000), PHI, places=8)
        self.assertAlmostEqual(q_exact(100, 6) - q_exact(100, 7), 0.3475761196)
        self.assertAlmostEqual(psi(100 / 64) - psi(100 / 128), 0.3452978210)

    def test_gap_distinguishes_maximum_from_first_zero(self):
        sketch = single.FlajoletMartinBitmap(bitmap_size=16)
        with patch.object(sketch, "hash_value", side_effect=[1, 2, 8, 4096, 4]):
            for customer in ("A", "B", "C", "lucky"):
                sketch.add(customer)
            self.assertEqual(sketch.first_zero_position(), 2)
            self.assertEqual(sketch.bitmap[12], 1)
            sketch.add("fills-gap")
        self.assertEqual(sketch.first_zero_position(), 4)

    def test_routing_uses_remaining_hash(self):
        sketch = multi.PCSA(num_maps=4, bitmap_size=16)
        with patch.object(multi, "hash_customer", return_value=40):
            self.assertEqual(sketch.add("C00001"), (0, 1))
        self.assertEqual(sketch.bitmaps[0][1], 1)
        self.assertEqual(sketch.bitmaps[0][3], 0)

    def test_mean_rank_then_exponentiate(self):
        direct = multi.FlajoletMartinMulti(num_hashes=4, bitmap_size=8)
        pcsa = multi.PCSA(num_maps=4, bitmap_size=8)
        maps = [[1] * r + [0] * (8 - r) for r in [3, 4, 4, 5]]
        direct.bitmaps = maps
        pcsa.bitmaps = maps
        self.assertAlmostEqual(direct.estimate(raw=True), 16 / PHI)
        self.assertAlmostEqual(pcsa.estimate(raw=True), 64 / PHI)

    def test_zero_and_saturation(self):
        self.assertEqual(rho(0, 58), 58)
        self.assertEqual(first_zero([1, 1]), 2)
        sketch = single.FlajoletMartinBitmap(bitmap_size=2)
        self.assertEqual(sketch.estimate(), 0)
        self.assertAlmostEqual(sketch.estimate(raw=True), 1 / PHI)
        with patch.object(sketch, "hash_value", return_value=0):
            sketch.add("zero")
        self.assertEqual(sketch.bitmap, [0, 0])
        sketch.bitmap = [1, 1]
        with self.assertRaises(OverflowError):
            sketch.estimate()
        with self.assertRaises(ValueError):
            multi.PCSA(num_maps=64, bitmap_size=59)

    def test_duplicates_order_and_overlapping_checkout_merge(self):
        visits = small_visits()
        self.assertEqual(len(visits), 20)
        self.assertEqual(len({v["customer_id"] for v in visits}), 12)
        central, left, right, reverse = [multi.PCSA() for _ in range(4)]
        for visit in visits:
            central.add(visit["customer_id"])
            (left if visit["checkout"] == "A" else right).add(visit["customer_id"])
        for visit in reversed(visits * 7):
            reverse.add(visit["customer_id"])
        self.assertEqual(left.merge(right).bitmaps, central.bitmaps)
        self.assertEqual(reverse.bitmaps, central.bitmaps)
        self.assertEqual(left.merge(left).bitmaps, central.bitmaps)
        with self.assertRaises(ValueError):
            central.merge(multi.PCSA(seed=1))

    def test_realistic_generated_ground_truth(self):
        stream = list(customer_stream(10000, 20000))
        self.assertEqual(len(stream), 30000)
        self.assertEqual(len(set(stream)), 10000)


if __name__ == "__main__":
    unittest.main()
