# Demand-Aware BMC Admission Prototype

This folder contains a prototype extension for BMC.

The goal is not to measure speed. Our VM environment uses generic/SKB XDP, so speed is not meaningful compared with the paper's native-XDP setup.

The goal is to test a cache admission policy.

## Problem

Basic cache-all behavior can cache a key after the first reply. This can pollute the cache with one-time cold keys.

## Proposed Policy

Demand-aware admission caches a key only after:

request_count >= 10

This means BMC waits until a key proves repeated demand before storing it.

## 50-Request Trace

Command:

python3 threshold_trace_demo.py --requests 50 --repeated-count 15 --threshold 10 --cache-capacity 10 --interleave

Key result:

demand_aware admitted 'hot_hello' at request 28 after count reached 10
cache_all admitted keys: 36
demand_aware admitted keys: 1

## 500-Request Trace

Command:

python3 threshold_trace_demo.py --requests 500 --repeated-count 100 --threshold 10 --cache-capacity 50 --interleave

Key result:

cache_all admitted keys: 401
demand_aware admitted keys: 1

## Interpretation

Demand-aware admission avoids cache pollution by refusing one-time cold keys.

## Demand-and-Size-Aware Extension

The Figure 7 worst-case workload exposes a second admission problem: a key can
be hot while its value is too large for BMC's fixed-size cache. Repeating the
full BMC lookup for that key adds work without a possibility of a cache hit.

The improved policy applies two rules:

```text
admit if request_count >= 10 and value_size <= maximum_cacheable_size
fast-pass if the key is known to have a non-cacheable value
```

Run the policy comparison with:

```bash
python3 size_aware_trace_demo.py
```

The default trace contains 100 requests for an 8192-byte hot value, 15 requests
for a 32-byte hot value, and 35 one-time cold requests. The size-aware policy
marks the large key once and fast-passes its next 99 requests. It reduces full
BMC lookups from 145 to 46 (68.28%) while preserving the small-hot-key hits.

## Experimental Real-BMC Implementation

The real kernel program in `bmc/bmc_kern.c` now implements:

- `map_request_count`: cache index to saturated request count
- `map_noncacheable`: cache index to oversized-value marker
- request-count increment on an XDP cache miss
- TC admission only after `request_count >= 10`
- TC detection of oversized or multi-datagram Memcached replies
- early XDP pass for keys marked non-cacheable
- request-count and non-cacheable-marker reset on TCP SET
- runtime counters for rejected admissions, markers, and fast bypasses

Python policy tests pass locally. The eBPF object must still be compiled, loaded,
and exercised in the Ubuntu VM because the Windows host cannot run the Linux
eBPF verifier.
