# Demand-Aware BMC Admission Prototype

This folder contains a prototype extension for BMC.

The goal is not to measure speed. Our VM environment uses generic/SKB XDP, so speed is not meaningful compared with the paper's native-XDP setup.

The goal is to test a cache admission policy.

## Folder Layout

```text
benchmarks/   Windows-to-VM UDP benchmark client
scripts/      selectable BMC build flow
simulations/  policy-only trace simulations
tests/        Python unit tests
results/      one consolidated project results report
```

Run the unit tests from this directory with:

```bash
python3 -m unittest discover -s tests
```

## Visual Demand-Admission Test

The Windows benchmark creates a deterministic 32-byte workload with three hot
keys requested 50 times each and 150 cold keys requested once each:

```powershell
python benchmarks/demand_admission_experiment.py --host 192.168.1.71 --label ORIGINAL
```

After the workload, inspect the live BPF maps in the Ubuntu VM:

```bash
sudo python3 scripts/inspect_demand_state.py
```

Repeat with demand-aware mode. The terminal report lists the stored hot keys
and reports how many cold keys were admitted, based on direct `map_kcache`
lookups rather than inferred counters. Verified summaries are recorded in the
single `results/BMC_PROJECT_RESULTS.md` file; raw output files are not committed.

## Problem

Basic cache-all behavior can cache a key after the first reply. This can pollute the cache with one-time cold keys.

## Proposed Policy

Demand-aware admission caches a key only after:

request_count >= 10

This means BMC waits until a key proves repeated demand before storing it.

## 50-Request Trace

Command:

python3 simulations/threshold_trace_demo.py --requests 50 --repeated-count 15 --threshold 10 --cache-capacity 10 --interleave

Key result:

demand_aware admitted 'hot_hello' at request 28 after count reached 10
cache_all admitted keys: 36
demand_aware admitted keys: 1

## 500-Request Trace

Command:

python3 simulations/threshold_trace_demo.py --requests 500 --repeated-count 100 --threshold 10 --cache-capacity 50 --interleave

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
python3 simulations/size_aware_trace_demo.py
```

The default trace contains 100 requests for an 8192-byte hot value, 15 requests
for a 32-byte hot value, and 35 one-time cold requests. The size-aware policy
marks the large key once and fast-passes its next 99 requests. It reduces full
BMC lookups from 145 to 46 (68.28%) while preserving the small-hot-key hits.

## Experimental Real-BMC Implementation

The real kernel program in `bmc/bmc_kern.c` now implements:

- `map_request_count`: cache index to saturated request count
- `map_noncacheable`: cache index to oversized-value marker
- request-count increment when TC observes a Memcached VALUE reply
- TC admission only after `request_count >= 10`
- TC detection of oversized or multi-datagram Memcached replies
- early XDP pass for keys marked non-cacheable
- request-count and non-cacheable-marker reset on TCP SET
- runtime counters for rejected admissions, markers, and fast bypasses

Counting replies at TC is equivalent to counting misses before admission: each
miss that Memcached answers contributes one unit of demonstrated demand. It
also keeps the admission policy testable when a generic/SKB XDP environment
cannot perform the packet-head adjustment required by BMC's fast reply path.

## Real-BMC Validation

The extension was compiled with clang/LLVM 9 and loaded in an Ubuntu 20.04
VirtualBox VM using generic/SKB XDP. A Windows client stored an 8192-byte value
and issued 50 UDP GET requests. All 50 requests completed successfully.

The final kernel counters were:

```text
get_recv_count 50
get_resp_count 50
miss_count 1
noncacheable_mark_count 1
noncacheable_bypass_count 49
```

Direct `bpftool` inspection confirmed that the large key had a non-cacheable
marker of 1, a request count of 1, and no valid entry in `map_kcache`. This
demonstrates the intended path: the first oversized reply marks the key, then
the next 49 requests bypass the full BMC cache lookup and continue to normal
Memcached.

Validation also uncovered and fixed two accounting problems: invalid cache
entries were initially reported as hits, and the extended per-CPU statistics
structure needed an 8-byte-aligned size. These fixes make the runtime counters
consistent with the direct BPF map state.

The measured 1183.35 GET/s is a functional VM result, not a paper-level
performance claim. Generic/SKB XDP in VirtualBox cannot reproduce the native
driver-XDP environment used by the paper.

## Three-Mode Comparison

Use the build selector to compare three admission policies while keeping the
toolchain, corrected hit accounting, statistics layout, and workload constant:

```bash
cd extensions/demand-aware-admission
./scripts/build_bmc_mode.sh
```

The interactive choices are:

```text
1. original:    original cache-all admission
2. demand:      cache only after request_count >= 10
3. demand-size: demand-aware admission plus oversized-key bypass
```

The same modes can be selected without the menu:

```bash
./scripts/build_bmc_mode.sh original
./scripts/build_bmc_mode.sh demand
./scripts/build_bmc_mode.sh demand-size
```

Each build must be loaded separately. Run the same client workload, request
count, warmup, and trial count for all three configurations. The original mode
keeps the false-hit and per-CPU statistics fixes so its measurements remain
comparable and trustworthy; only the admission policy is disabled.
