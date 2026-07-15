import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "simulations"))

from size_aware_trace_demo import (
    build_trace,
    simulate_demand_and_size_aware,
    simulate_demand_only,
)


class SizeAwarePolicyTest(unittest.TestCase):
    def test_large_hot_key_is_bypassed_after_first_response(self):
        trace = build_trace(100, 15, 35, seed=7645)
        baseline = simulate_demand_only(trace, 10, 10, 1000)
        improved = simulate_demand_and_size_aware(trace, 10, 10, 1000)

        self.assertEqual(improved["noncacheable"], ["large_hot"])
        self.assertEqual(improved["fast_bypasses"], 99)
        self.assertEqual(improved["noncacheable_markers"], 1)
        self.assertEqual(improved["admitted"], 1)
        self.assertEqual(improved["hits"], 5)
        self.assertLess(improved["full_lookups"], baseline["full_lookups"])

    def test_small_hot_key_still_obeys_demand_threshold(self):
        trace = [("small_hot", 32)] * 15
        improved = simulate_demand_and_size_aware(trace, 10, 10, 1000)

        self.assertEqual(improved["full_lookups"], 10)
        self.assertEqual(improved["hits"], 5)
        self.assertEqual(improved["admitted"], 1)
        self.assertEqual(improved["fast_bypasses"], 0)


if __name__ == "__main__":
    unittest.main()
