import argparse
import random
from collections import Counter, OrderedDict


class LruCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.items = OrderedDict()

    def get(self, key):
        if key not in self.items:
            return False
        self.items.move_to_end(key)
        return True

    def put(self, key):
        if key in self.items:
            self.items.move_to_end(key)
            return
        if len(self.items) >= self.capacity:
            self.items.popitem(last=False)
        self.items[key] = True

    def keys(self):
        return list(self.items.keys())


def build_trace(large_requests, small_requests, cold_requests, seed):
    trace = [("large_hot", 8192)] * large_requests
    trace.extend(("small_hot", 32) for _ in range(small_requests))
    trace.extend((f"cold_{index}", 32) for index in range(cold_requests))
    random.Random(seed).shuffle(trace)
    return trace


def simulate_demand_only(trace, threshold, cache_capacity, max_cacheable_size):
    cache = LruCache(cache_capacity)
    counts = Counter()
    metrics = Counter()

    for key, value_size in trace:
        if cache.get(key):
            metrics["hits"] += 1
            continue

        metrics["full_lookups"] += 1
        counts[key] += 1
        if counts[key] < threshold:
            continue

        if value_size > max_cacheable_size:
            metrics["oversize_rejections"] += 1
            continue

        cache.put(key)
        metrics["admitted"] += 1

    return make_result("demand_only", metrics, cache, set(), len(trace))


def simulate_demand_and_size_aware(
    trace, threshold, cache_capacity, max_cacheable_size
):
    cache = LruCache(cache_capacity)
    counts = Counter()
    noncacheable = set()
    metrics = Counter()

    for key, value_size in trace:
        if key in noncacheable:
            metrics["fast_bypasses"] += 1
            continue

        if cache.get(key):
            metrics["hits"] += 1
            continue

        metrics["full_lookups"] += 1
        counts[key] += 1

        if value_size > max_cacheable_size:
            noncacheable.add(key)
            metrics["noncacheable_markers"] += 1
            continue

        if counts[key] >= threshold:
            cache.put(key)
            metrics["admitted"] += 1

    return make_result(
        "demand_and_size_aware", metrics, cache, noncacheable, len(trace)
    )


def make_result(policy, metrics, cache, noncacheable, request_count):
    return {
        "policy": policy,
        "requests": request_count,
        "hits": metrics["hits"],
        "full_lookups": metrics["full_lookups"],
        "fast_bypasses": metrics["fast_bypasses"],
        "oversize_rejections": metrics["oversize_rejections"],
        "noncacheable_markers": metrics["noncacheable_markers"],
        "admitted": metrics["admitted"],
        "final_cache": cache.keys(),
        "noncacheable": sorted(noncacheable),
    }


def print_result(result):
    print(f"\nPolicy: {result['policy']}")
    print(f"  requests: {result['requests']}")
    print(f"  cache hits: {result['hits']}")
    print(f"  full BMC lookups: {result['full_lookups']}")
    print(f"  fast non-cacheable bypasses: {result['fast_bypasses']}")
    print(f"  repeated oversize rejections: {result['oversize_rejections']}")
    print(f"  non-cacheable markers created: {result['noncacheable_markers']}")
    print(f"  admitted keys: {result['admitted']}")
    print(f"  final cache keys: {result['final_cache']}")
    print(f"  non-cacheable keys: {result['noncacheable']}")


def main():
    parser = argparse.ArgumentParser(
        description="Compare demand-only and demand-plus-size-aware BMC admission."
    )
    parser.add_argument("--large-requests", type=int, default=100)
    parser.add_argument("--small-requests", type=int, default=15)
    parser.add_argument("--cold-requests", type=int, default=35)
    parser.add_argument("--threshold", type=int, default=10)
    parser.add_argument("--cache-capacity", type=int, default=10)
    parser.add_argument("--max-cacheable-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=7645)
    args = parser.parse_args()

    if min(args.large_requests, args.small_requests, args.cold_requests) < 0:
        parser.error("request counts must be non-negative")
    if args.threshold <= 0 or args.cache_capacity <= 0:
        parser.error("threshold and cache capacity must be positive")

    trace = build_trace(
        args.large_requests,
        args.small_requests,
        args.cold_requests,
        args.seed,
    )

    print("Demand-and-size-aware BMC trace demo")
    print("-" * 42)
    print(f"large-hot requests (8192 bytes): {args.large_requests}")
    print(f"small-hot requests (32 bytes): {args.small_requests}")
    print(f"one-time cold requests: {args.cold_requests}")
    print(f"demand threshold: {args.threshold}")
    print(f"maximum cacheable value: {args.max_cacheable_size} bytes")

    demand_only = simulate_demand_only(
        trace, args.threshold, args.cache_capacity, args.max_cacheable_size
    )
    improved = simulate_demand_and_size_aware(
        trace, args.threshold, args.cache_capacity, args.max_cacheable_size
    )
    print_result(demand_only)
    print_result(improved)

    avoided = demand_only["full_lookups"] - improved["full_lookups"]
    reduction = avoided / demand_only["full_lookups"] if demand_only["full_lookups"] else 0
    print("\nImprovement")
    print(f"  full BMC lookups avoided: {avoided}")
    print(f"  full-lookup reduction: {reduction:.2%}")


if __name__ == "__main__":
    main()
