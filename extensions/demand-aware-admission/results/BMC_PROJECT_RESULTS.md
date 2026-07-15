# BMC Project Experiment Results

This is the single source of truth for verified project results. Raw terminal
outputs are reviewed and summarized here instead of being committed as many
separate files.

## Environment

```text
Server: Ubuntu 20.04 VirtualBox VM
Kernel: Linux 5.15 generic
BMC mode: generic/SKB XDP
Client: Windows host over bridged networking
Memcached protocol: UDP GET, TCP SET
```

The VM environment is suitable for functional and policy validation. Its
throughput is not directly comparable to the paper's native driver-XDP setup.

## Experiment Matrix

| Experiment | Configuration A | Configuration B | Configuration C | Value size |
|---|---|---|---|---:|
| Basic acceleration | Memcached only | Original BMC | - | 32 B |
| Demand admission | Original BMC | Demand-aware | - | 32 B |
| Large-value handling | Original BMC | Demand-aware | Demand + size-aware | 8192 B |

## 1. Basic Acceleration

Status: Complete.

| Mode | Average GET/s | Median GET/s | Speedup |
|---|---:|---:|---:|
| Memcached only | 4621.47 | 4787.56 | 1.00x |
| Original BMC | 6051.76 | 6232.68 | 1.31x |

Original BMC improved average throughput by 30.95% and median throughput by
30.18%. All timed requests succeeded. The clean BMC counter snapshot was:

```text
get_recv_count: 4000
get_resp_count: 1
hit_count: 3999
miss_count: 1
update_count: 1
```

The first GET missed and taught BMC; the following 3999 warmup and timed GETs
were returned from the kernel cache.

## 2. Demand Admission

Status: Complete.

Controlled workload:

```text
Value size: 32 bytes
Hot keys: 3, requested 50 times each (150 requests)
Cold keys: 150, requested once each (150 requests)
Total: 300 requests
```

| Mode | GET/s | Hot keys stored | Cold keys stored | Cache updates | Rejected admissions |
|---|---:|---:|---:|---:|---:|
| Original BMC | 3795.08 | 3/3 | 150/150 | 153 | 0 |
| Demand-aware | 4272.06 | 3/3 | 0/150 | 3 | 177 |

Direct `map_kcache` inspection is used to determine whether each deterministic
hot or cold key is actually stored. Original BMC admitted every unique key,
including all 150 keys requested only once. Demand-aware admission retained all
three hot keys and rejected every cold key.

The 177 rejected admissions are exactly the expected 150 one-time cold-key
replies plus the first nine replies for each of the three hot keys
(`150 + 3 * 9`). The tenth reply admitted each hot key.

Both runs reported zero XDP cache hits because VirtualBox generic/SKB XDP
failed BMC's packet-head adjustment for all 300 GETs. This does not invalidate
the admission result: TC observed all 300 Memcached replies, applied the demand
threshold, and the final BPF map contents directly confirmed the policy state.
The throughput values are recorded for completeness and are not treated as a
speed comparison.

## 3. Large-Value Handling

Status: Complete.

Controlled workload:

```text
Value size: 8192 bytes
Requests per trial: 300
Warmup per trial: 100
Trials: 10
Total BMC-observed GETs: 4000
```

| Mode | Average GET/s | Median GET/s | Misses | Markers | Bypasses |
|---|---:|---:|---:|---:|---:|
| Original BMC | 1159.88 | 1192.12 | 4000 | 0 | 0 |
| Demand-aware | 2928.92 | 3020.25 | 4000 | 0 | 0 |
| Demand + size-aware | 2937.67 | 3161.21 | 1 | 1 | 3999 |

Demand-aware admission alone reached its threshold after nine rejected replies,
but the 8192-byte value could not fit in BMC's fixed-size cache. It therefore
continued through the full BMC lookup path for all 4000 requests and produced
no cache update.

Demand + size-aware marked the oversized key after its first reply and
fast-passed the following 3999 requests. This reduced full BMC cache lookups
from 4000 to 1 (99.975%) while all 3000 timed requests still completed
successfully. Average throughput was nearly unchanged (+0.30%) and median
throughput increased by 4.67%; VM variability and normal Memcached processing
remain dominant, so the lookup reduction is the primary result.

### Verified Size-Aware Functional Check

An earlier 50-request functional run verified the real eBPF size-aware path:

```text
Successful requests: 50/50
Throughput: 1183.35 GET/s
miss_count: 1
noncacheable_mark_count: 1
noncacheable_bypass_count: 49
map_noncacheable: 1
map_request_count: 1
map_kcache.valid: 0
```

Interpretation: the first oversized reply marked the key as non-cacheable. The
following 49 requests bypassed the full BMC cache lookup and continued to
normal Memcached. The 8192-byte value was never admitted into `map_kcache`.

## Exploratory Runs

Earlier 3000-request runs are retained only as context because VM performance
varied substantially and their parameters differ from the final matrix:

| Mode | Average GET/s | Median GET/s |
|---|---:|---:|
| Original BMC | 2233.59 | 2513.46 |
| Demand-aware | 1244.29 | 1156.36 |

These exploratory numbers are not used for the final policy comparison.
