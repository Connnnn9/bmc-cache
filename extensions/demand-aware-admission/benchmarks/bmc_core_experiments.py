import argparse
import socket
import statistics
import struct
import time


PORT = 11211


class MemcachedClient:
    def __init__(self, host, timeout=2.0):
        self.host = host
        self.timeout = timeout
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)
        self.request_id = 0

    def close(self):
        self.sock.close()

    def set_tcp(self, key, value):
        command = (
            f"set {key} 0 0 {len(value)}\r\n".encode("ascii")
            + value
            + b"\r\n"
        )
        with socket.create_connection((self.host, PORT), self.timeout) as sock:
            sock.sendall(command)
            response = sock.recv(4096)
        if not response.startswith(b"STORED"):
            raise RuntimeError(f"SET failed: {response!r}")
        return response.decode(errors="replace").strip()

    def get_udp(self, key):
        self.request_id = (self.request_id % 65535) + 1
        request_id = self.request_id
        header = struct.pack("!HHHH", request_id, 0, 1, 0)
        self.sock.sendto(header + f"get {key}\r\n".encode("ascii"), (self.host, PORT))

        fragments = {}
        expected = None
        deadline = time.perf_counter() + self.timeout

        while expected is None or len(fragments) < expected:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                raise TimeoutError("timed out while reassembling UDP response")
            self.sock.settimeout(remaining)
            packet, _ = self.sock.recvfrom(65535)
            if len(packet) < 8:
                continue
            response_id, sequence, total, _ = struct.unpack("!HHHH", packet[:8])
            if response_id != request_id:
                continue
            expected = total
            fragments[sequence] = packet[8:]

        return b"".join(fragments[index] for index in range(expected))


def run_throughput(client, key, requests, trials, warmup, label, figure):
    rates = []
    print(f"Figure {figure} adapted - {label}")

    for trial in range(1, trials + 1):
        for _ in range(warmup):
            client.get_udp(key)

        successful = 0
        start = time.perf_counter()
        for _ in range(requests):
            if b"VALUE " + key.encode("ascii") in client.get_udp(key):
                successful += 1
        elapsed = time.perf_counter() - start
        rate = requests / elapsed
        rates.append(rate)
        print(
            f"trial {trial}: successful={successful}/{requests} "
            f"seconds={elapsed:.4f} GET/sec={rate:.2f}"
        )

    print(f"average GET/sec: {statistics.mean(rates):.2f}")
    print(f"median GET/sec: {statistics.median(rates):.2f}")


def main():
    parser = argparse.ArgumentParser(description="Adapted BMC core experiments")
    parser.add_argument("--host", required=True)
    parser.add_argument("--experiment", choices=("fig6", "fig7"), required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--requests", type=int, default=10000)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=2000)
    parser.add_argument(
        "--skip-set",
        action="store_true",
        help="reuse the existing key without resetting BMC admission state",
    )
    args = parser.parse_args()

    client = MemcachedClient(args.host)
    try:
        if args.experiment == "fig6":
            key = "small_hot_key_01"
            value = b"s" * 32
            figure = "6"
        else:
            key = "large_hot_key_01"
            value = b"L" * 8192
            figure = "7"

        if not args.skip_set:
            print(client.set_tcp(key, value))
        run_throughput(
            client,
            key,
            args.requests,
            args.trials,
            args.warmup,
            args.label,
            figure,
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()
