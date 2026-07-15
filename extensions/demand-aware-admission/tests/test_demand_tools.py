import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmarks"))
sys.path.insert(0, str(ROOT / "scripts"))

from demand_admission_experiment import build_trace
from inspect_demand_state import fnv1a


class DemandWorkloadTests(unittest.TestCase):
    def test_trace_contains_expected_hot_and_cold_requests(self):
        hot = ["hot_000", "hot_001", "hot_002"]
        cold = [f"cold_{index:03d}" for index in range(150)]
        counts = Counter(build_trace(hot, 50, cold))

        self.assertEqual(sum(counts.values()), 300)
        for key in hot:
            self.assertEqual(counts[key], 50)
        for key in cold:
            self.assertEqual(counts[key], 1)

    def test_fnv1a_matches_known_value(self):
        self.assertEqual(fnv1a("hello"), 1335831723)


if __name__ == "__main__":
    unittest.main()
