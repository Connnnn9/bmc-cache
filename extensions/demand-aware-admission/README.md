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

## Next Step

The safer real-BMC implementation would start with a simple BPF map:

key -> request_count

Then BMC would admit a key into the kernel cache only after:

request_count >= threshold

## Experimental Real-BMC Patch Status

A minimal version of this policy was also added to the real BMC kernel program in:

bmc/bmc_kern.c

The experimental patch adds:

- BMC_DEMAND_THRESHOLD = 10
- map_request_count: cache index -> request count
- request-count increment when XDP parses a GET key
- admission check before TC marks a cache entry valid

The intended rule is:

request_count >= 10

Only then can a Memcached VALUE reply be admitted into the BMC kernel cache.

Validation completed so far:

- bmc_kern.c compiled successfully with clang-9 and llc-9
- bmc_kern.o was generated as an eBPF object
- patched BMC loaded successfully
- libbpf created map_request_count
- BMC attached to XDP on interface 2
- TC egress attached successfully
- basic Memcached SET/GET still worked

Important limitation:

This confirms build/load/basic correctness. It does not yet prove runtime hit-rate or speed improvement, because the VM uses generic/SKB XDP and is not suitable for paper-level performance measurement.
