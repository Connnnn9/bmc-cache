import argparse
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
            return None
        evicted = None
        if len(self.items) >= self.capacity:
            evicted, _ = self.items.popitem(last=False)
        self.items[key] = True
        return evicted

    def keys(self):
        return list(self.items.keys())


def build_trace(total_requests, repeated_key, repeated_count, interleave):
    if repeated_count > total_requests:
        raise ValueError("repeated_count cannot exceed total_requests")

    if not interleave:
        trace = [repeated_key for _ in range(repeated_count)]
        trace.extend(f"cold_{i}" for i in range(total_requests - repeated_count))
        return trace

    trace = []
    cold_index = 0
    hot_left = repeated_count
    cold_left = total_requests - repeated_count

    while hot_left or cold_left:
        if hot_left:
            trace.append(repeated_key)
            hot_left -= 1
        if cold_left:
            trace.append(f"cold_{cold_index}")
            cold_index += 1
            cold_left -= 1
        if cold_left:
            trace.append(f"cold_{cold_index}")
            cold_index += 1
            cold_left -= 1
    return trace


def simulate_cache_all(trace, cache_capacity):
    cache = LruCache(cache_capacity)
    hits = 0
    admitted = 0

    for key in trace:
        if cache.get(key):
            hits += 1
            continue
        cache.put(key)
        admitted += 1

    return {
        "policy": "cache_all",
        "hits": hits,
        "hit_rate": hits / len(trace),
        "admitted": admitted,
        "final_cache": cache.keys(),
    }


def simulate_demand_aware(trace, cache_capacity, threshold):
    cache = LruCache(cache_capacity)
    counts = Counter()
    hits = 0
    admitted = 0
    first_admitted_at = None

    for request_number, key in enumerate(trace, start=1):
        if cache.get(key):
            hits += 1
            continue

        counts[key] += 1
        should_admit = counts[key] >= threshold

        if should_admit:
            cache.put(key)
            admitted += 1
            if first_admitted_at is None:
                first_admitted_at = request_number
                print(
                    f"demand_aware admitted {key!r} at request {request_number} "
                    f"after count reached {counts[key]}"
                )

    return {
        "policy": "demand_aware",
        "hits": hits,
        "hit_rate": hits / len(trace),
        "admitted": admitted,
        "first_admitted_at": first_admitted_at,
        "final_cache": cache.keys(),
    }


def print_summary(result):
    print(f"\nPolicy: {result['policy']}")
    print(f"  hits: {result['hits']}")
    print(f"  hit rate: {result['hit_rate']:.2%}")
    print(f"  admitted keys: {result['admitted']}")
    if "first_admitted_at" in result:
        print(f"  first admitted at request: {result['first_admitted_at']}")
    print(f"  final cache keys: {result['final_cache']}")


def main():
    parser = argparse.ArgumentParser(
        description="Small threshold demo for demand-aware BMC admission."
    )
    parser.add_argument("--requests", type=int, default=50)
    parser.add_argument("--repeated-count", type=int, default=15)
    parser.add_argument("--threshold", type=int, default=10)
    parser.add_argument("--cache-capacity", type=int, default=10)
    parser.add_argument("--repeated-key", default="hot_hello")
    parser.add_argument("--interleave", action="store_true")
    args = parser.parse_args()

    trace = build_trace(
        args.requests,
        args.repeated_key,
        args.repeated_count,
        args.interleave,
    )

    print("Threshold trace demo")
    print("-" * 36)
    print(f"requests: {args.requests}")
    print(f"repeated key: {args.repeated_key}")
    print(f"repeated count: {args.repeated_count}")
    print(f"cold one-time keys: {args.requests - args.repeated_count}")
    print(f"interleaved trace: {args.interleave}")
    print(f"demand-aware rule: cache if request_count >= {args.threshold}")
    print(f"cache capacity: {args.cache_capacity}")

    print_summary(simulate_cache_all(trace, args.cache_capacity))
    print_summary(simulate_demand_aware(trace, args.cache_capacity, args.threshold))


if __name__ == "__main__":
    main()
