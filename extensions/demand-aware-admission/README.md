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
