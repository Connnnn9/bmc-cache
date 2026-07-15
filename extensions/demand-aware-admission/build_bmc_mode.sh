#!/usr/bin/env bash

set -euo pipefail

mode="${1:-}"

if [[ -z "$mode" ]]; then
    echo "Choose a BMC experiment mode:"
    echo "  1) original       - original cache-all admission"
    echo "  2) demand         - cache after request_count >= 10"
    echo "  3) demand-size    - demand-aware plus oversized-key bypass"
    read -r -p "Selection [1-3]: " selection

    case "$selection" in
        1) mode="original" ;;
        2) mode="demand" ;;
        3) mode="demand-size" ;;
        *) echo "Invalid selection: $selection" >&2; exit 2 ;;
    esac
fi

case "$mode" in
    original)
        flags="-DBMC_DEMAND_AWARE=0 -DBMC_SIZE_AWARE=0"
        description="Original BMC cache-all admission"
        ;;
    demand)
        flags="-DBMC_DEMAND_AWARE=1 -DBMC_SIZE_AWARE=0"
        description="Demand-aware admission (threshold 10)"
        ;;
    demand-size)
        flags="-DBMC_DEMAND_AWARE=1 -DBMC_SIZE_AWARE=1"
        description="Demand-and-size-aware admission"
        ;;
    *)
        echo "Usage: $0 {original|demand|demand-size}" >&2
        exit 2
        ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

echo "Building mode: $description"
echo "Compile flags: $flags"

make -C "$repo_root/bmc" clean
make -C "$repo_root/bmc" CLANG=clang-9 LLC=llc-9 EXTRA_CFLAGS="$flags"
file "$repo_root/bmc/bmc_kern.o"

echo "$mode" > "$script_dir/.last_build_mode"
echo "Build complete: $mode"
