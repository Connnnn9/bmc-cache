import argparse
import math
import time

from bmc_core_experiments import MemcachedClient


def build_trace(hot_keys, hot_repeats, cold_keys):
    trace = []
    cold_index = 0

    for round_index in range(hot_repeats):
        trace.extend(hot_keys)

        rounds_left = hot_repeats - round_index
        cold_left = len(cold_keys) - cold_index
        take = math.ceil(cold_left / rounds_left) if cold_left else 0
        trace.extend(cold_keys[cold_index : cold_index + take])
        cold_index += take

    return trace


def main():
    parser = argparse.ArgumentParser(description="BMC demand-admission workload")
    parser.add_argument("--host", required=True)
    parser.add_argument("--hot-keys", type=int, default=3)
    parser.add_argument("--hot-repeats", type=int, default=50)
    parser.add_argument("--cold-keys", type=int, default=150)
    parser.add_argument("--value-size", type=int, default=32)
    parser.add_argument("--label", required=True)
    parser.add_argument(
        "--skip-set",
        action="store_true",
        help="reuse existing keys without resetting their BMC cache state",
    )
    args = parser.parse_args()

    hot_keys = [f"hot_{index:03d}" for index in range(args.hot_keys)]
    cold_keys = [f"cold_{index:03d}" for index in range(args.cold_keys)]
    trace = build_trace(hot_keys, args.hot_repeats, cold_keys)

    client = MemcachedClient(args.host)
    try:
        if not args.skip_set:
            for key in hot_keys:
                client.set_tcp(key, b"H" * args.value_size)
            for key in cold_keys:
                client.set_tcp(key, b"C" * args.value_size)

        successful = 0
        start = time.perf_counter()
        for key in trace:
            response = client.get_udp(key)
            if b"VALUE " + key.encode("ascii") in response:
                successful += 1
        elapsed = time.perf_counter() - start
    finally:
        client.close()

    hot_requests = len(hot_keys) * args.hot_repeats
    print(f"Demand admission experiment - {args.label}")
    print(f"value size: {args.value_size} bytes")
    print(f"hot keys: {len(hot_keys)}")
    print(f"requests per hot key: {args.hot_repeats}")
    print(f"hot requests: {hot_requests}")
    print(f"cold keys: {len(cold_keys)}")
    print(f"requests per cold key: 1")
    print(f"cold requests: {len(cold_keys)}")
    print(f"total requests: {len(trace)}")
    print(f"successful: {successful}/{len(trace)}")
    print(f"seconds: {elapsed:.4f}")
    print(f"GET/sec: {len(trace) / elapsed:.2f}")


if __name__ == "__main__":
    main()
