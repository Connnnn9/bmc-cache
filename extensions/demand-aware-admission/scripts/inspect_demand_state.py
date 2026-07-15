import argparse
import json
import os
import subprocess
from pathlib import Path


FNV_OFFSET_BASIS_32 = 2166136261
FNV_PRIME_32 = 16777619
BMC_CACHE_ENTRY_COUNT = 3250000


def fnv1a(key):
    result = FNV_OFFSET_BASIS_32
    for byte in key.encode("ascii"):
        result ^= byte
        result = (result * FNV_PRIME_32) & 0xFFFFFFFF
    return result


def map_lookup(map_name, cache_index):
    key_bytes = cache_index.to_bytes(4, "little")
    command = [
        "bpftool",
        "-j",
        "map",
        "lookup",
        "name",
        map_name,
        "key",
        "hex",
        *(f"{byte:02x}" for byte in key_bytes),
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(completed.stdout)["value"]


def inspect_key(key):
    key_hash = fnv1a(key)
    cache_index = key_hash % BMC_CACHE_ENTRY_COUNT
    cache_entry = map_lookup("map_kcache", cache_index)
    request_count = map_lookup("map_request_cou", cache_index)

    stored_hash = int(cache_entry["hash"]) & 0xFFFFFFFF
    stored = int(cache_entry["valid"]) == 1 and stored_hash == key_hash
    return {
        "key": key,
        "cache_index": cache_index,
        "request_count": int(request_count),
        "stored": stored,
    }


def summarize(label, records):
    stored = [record["key"] for record in records if record["stored"]]
    not_stored = [record["key"] for record in records if not record["stored"]]
    print(f"{label} keys requested: {len(records)}")
    print(f"{label} keys stored in BMC: {len(stored)}/{len(records)}")
    print(f"{label} stored: {', '.join(stored) if stored else '(none)'}")
    if not_stored:
        sample = ", ".join(not_stored[:10])
        suffix = " ..." if len(not_stored) > 10 else ""
        print(f"{label} not stored: {sample}{suffix}")


def main():
    parser = argparse.ArgumentParser(description="Inspect hot/cold BMC admission state")
    parser.add_argument("--hot-keys", type=int, default=3)
    parser.add_argument("--hot-repeats", type=int, default=50)
    parser.add_argument("--cold-keys", type=int, default=150)
    parser.add_argument("--json-output")
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this inspector with sudo so bpftool can read BPF maps.")

    hot = [inspect_key(f"hot_{index:03d}") for index in range(args.hot_keys)]
    cold = [inspect_key(f"cold_{index:03d}") for index in range(args.cold_keys)]

    print("BMC demand-admission state")
    print("----------------------------------------")
    print(f"Hot requests sent: {args.hot_keys * args.hot_repeats}")
    print(f"Cold requests sent: {args.cold_keys}")
    print(f"Total requests sent: {args.hot_keys * args.hot_repeats + args.cold_keys}")
    print()
    summarize("Hot", hot)
    print()
    summarize("Cold", cold)

    result = {
        "hot": hot,
        "cold": cold,
        "hot_stored": sum(record["stored"] for record in hot),
        "cold_stored": sum(record["stored"] for record in cold),
    }
    if args.json_output:
        output = Path(args.json_output)
        output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(f"\nJSON result written to: {output}")


if __name__ == "__main__":
    main()
