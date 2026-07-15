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


def byte_value(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise TypeError(f"Unsupported byte value: {value!r}")


def decode_u32(value):
    if isinstance(value, int):
        return value
    if isinstance(value, list):
        raw = bytes(byte_value(item) for item in value[:4])
        return int.from_bytes(raw, "little")
    raise TypeError(f"Unsupported u32 map value: {value!r}")


def decode_cache_entry(value):
    if isinstance(value, dict):
        return int(value["valid"]), int(value["hash"]) & 0xFFFFFFFF
    if isinstance(value, list):
        raw = bytes(byte_value(item) for item in value)
        if len(raw) < 16:
            raise ValueError(f"Cache entry is too short: {len(raw)} bytes")
        valid = raw[8]
        stored_hash = int.from_bytes(raw[12:16], "little")
        return valid, stored_hash
    raise TypeError(f"Unsupported cache entry value: {type(value).__name__}")


def inspect_key(key):
    key_hash = fnv1a(key)
    cache_index = key_hash % BMC_CACHE_ENTRY_COUNT
    cache_entry = map_lookup("map_kcache", cache_index)
    request_count = map_lookup("map_request_cou", cache_index)

    valid, stored_hash = decode_cache_entry(cache_entry)
    stored = valid == 1 and stored_hash == key_hash
    return {
        "key": key,
        "cache_index": cache_index,
        "request_count": decode_u32(request_count),
        "stored": stored,
    }


def format_keys(keys):
    if not keys:
        return "(none)"
    if len(keys) <= 12:
        return ", ".join(keys)
    return f"{', '.join(keys[:6])}, ... , {', '.join(keys[-3:])} ({len(keys)} total)"


def summarize(label, records):
    stored = [record["key"] for record in records if record["stored"]]
    not_stored = [record["key"] for record in records if not record["stored"]]
    print(f"{label} keys requested: {len(records)}")
    print(f"{label} keys stored in BMC: {len(stored)}/{len(records)}")
    print(f"{label} stored: {format_keys(stored)}")
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
