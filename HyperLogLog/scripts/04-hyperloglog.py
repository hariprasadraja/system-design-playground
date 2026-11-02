"""
HyperLogLog (HLL) from scratch, with a reproducible verification suite.

Mental model
------------
FM / LogLog / HyperLogLog all answer one question:
    "How many DISTINCT items have I seen?"  (not which items, and not exactly)

The hash of every item is treated as a random 64-bit string.

    +------------------------ 64 hash bits ------------------------+
    | p index bits |          q = 64 - p rank bits                 |
    +--------------+-----------------------------------------------+
       choose 1 of             count leading zeros + 1
       m = 2^p registers

Each register remembers the largest rank ever seen for its index.
A rare pattern (many leading zeros) is evidence that many items were hashed.

LogLog combines registers with a GEOMETRIC mean.
HyperLogLog combines them with a HARMONIC mean, which is much less
sensitive to one unusually large register, so it has lower variance.

Estimate:        E = alpha_m * m^2 / sum(2^(-register[j]))
Small range:     use linear counting while E <= 2.5*m and some registers are 0.
Expected error:  about 1.04 / sqrt(m)  (0.81% for the default m = 16384).
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Iterable

MASK64 = (1 << 64) - 1


def stable_hash_64(value: object, seed: int = 0) -> int:
    """A deterministic, uniformly distributed 64-bit hash (BLAKE2b)."""
    payload = f"{seed}\x1f{value!r}".encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big")


def _alpha(m: int) -> float:
    """Bias-correction constant used by the original HLL paper."""
    if m == 16:
        return 0.673
    if m == 32:
        return 0.697
    if m == 64:
        return 0.709
    return 0.7213 / (1.0 + 1.079 / m)


class HyperLogLog:
    """HyperLogLog cardinality sketch using 64-bit hashes."""

    def __init__(self, p: int = 14, seed: int = 0) -> None:
        if not 4 <= p <= 20:
            raise ValueError("p must be between 4 and 20")
        self.p = p
        self.m = 1 << p              # number of registers
        self.q = 64 - p              # bits left for the rank
        self.seed = seed
        # Ranks fit in one byte (q + 1 <= 61), so bytearray is compact.
        self.registers = bytearray(self.m)

    def _index_and_rank(self, hash64: int) -> tuple[int, int]:
        # First p bits select the register.
        index = hash64 >> self.q

        # Remaining q bits contain the pattern whose leading zeros we count.
        remainder = hash64 & ((1 << self.q) - 1)

        # Example: remainder=0b00101 has bit_length 3, so rank = q - 3 + 1.
        # If remainder is all zero, rank becomes q + 1 (the maximum).
        rank = self.q - remainder.bit_length() + 1
        return index, rank

    def add_hash(self, hash64: int) -> None:
        """Update the sketch from an already-computed 64-bit hash."""

        """Trim the hash into 64 bits"""
        hash64 &= MASK64


        index, rank = self._index_and_rank(hash64)
        if rank > self.registers[index]:
            self.registers[index] = rank

    def add(self, value: object) -> None:
        """Add one item (duplicates are naturally harmless)."""
        self.add_hash(stable_hash_64(value, self.seed))

    def update(self, values: Iterable[object]) -> None:
        for value in values:
            self.add(value)

    def merge(self, other: "HyperLogLog") -> "HyperLogLog":
        """Merge another sketch of the same shape in place (register-wise max)."""
        if self.p != other.p or self.seed != other.seed:
            raise ValueError("sketches must use the same p and hash seed")
        for i, rank in enumerate(other.registers):
            if rank > self.registers[i]:
                self.registers[i] = rank
        return self

    def estimate(self) -> float:
        """Estimated number of distinct items."""
        m = self.m

        # Harmonic mean of 2^register, written as the denominator of HLL.
        harmonic_sum = sum(math.ldexp(1.0, -rank) for rank in self.registers)
        raw = _alpha(m) * m * m / harmonic_sum

        zero_registers = self.registers.count(0)

        # Small-range correction: linear counting is more accurate when the
        # sketch is sparse (many empty registers).
        if raw <= 2.5 * m and zero_registers > 0:
            return m * math.log(m / zero_registers)

        # Large-range correction for a 64-bit hash space (rare in practice).
        huge = (1 << 64) / 30.0
        if raw > huge:
            ratio = raw / (1 << 64)
            if ratio < 1.0:
                return -(1 << 64) * math.log1p(-ratio)

        return raw

    def __repr__(self) -> str:
        return f"HyperLogLog(p={self.p}, m={self.m}, estimate={self.estimate():.1f})"


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _ids(n: int, namespace: str = "user") -> list[str]:
    """Deterministic unique test data; hashing makes it look random to HLL."""
    return [f"{namespace}-{i}" for i in range(n)]


def _check(name: str, condition: bool, detail: str) -> None:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}: {detail}")
    if not condition:
        raise AssertionError(name)


def check_tiny_example() -> None:
    data = ["apple", "banana", "apple", "cherry", "date", "banana"]
    sketch = HyperLogLog(p=14)
    sketch.update(data)
    estimate = sketch.estimate()
    nonempty = {i: rank for i, rank in enumerate(sketch.registers) if rank}
    _check(
        "tiny hand-checked data",
        abs(estimate - 4) < 0.01,
        f"{data} -> exact=4, HLL={estimate:.2f}, nonempty registers={nonempty}",
    )


def check_duplicates() -> None:
    values = _ids(5_000, "duplicate-test")
    once = HyperLogLog(p=12)
    once.update(values)

    many = HyperLogLog(p=12)
    for _ in range(5):
        many.update(values)

    _check(
        "duplicates are idempotent",
        once.registers == many.registers,
        f"5000 IDs added once vs five times -> registers identical, "
        f"estimate={once.estimate():.0f}",
    )


def check_merge() -> None:
    left = HyperLogLog(p=12)
    right = HyperLogLog(p=12)
    whole = HyperLogLog(p=12)

    left.update(_ids(30_000, "left"))
    right.update(_ids(30_000, "right"))
    whole.update(_ids(30_000, "left"))
    whole.update(_ids(30_000, "right"))

    left.merge(right)
    _check(
        "register-wise merge",
        left.registers == whole.registers,
        f"30k + 30k shards -> estimate={left.estimate():.0f} (exact=60000)",
    )


def check_small_range() -> None:
    sketch = HyperLogLog(p=14)
    sketch.update(_ids(250, "small"))
    estimate = sketch.estimate()
    error = abs(estimate - 250) / 250
    _check(
        "small-range linear counting",
        error < 0.01,
        f"exact=250, HLL={estimate:.2f}, relative error={error:.4%}",
    )


def accuracy_benchmark() -> None:
    """Measure error over several cardinalities and sketch sizes."""
    sizes = (1_000, 10_000, 100_000, 1_000_000)
    p_values = (10, 12, 14)       # m = 1024, 4096, 16384
    trials = 3

    print("\nAccuracy benchmark")
    print("Dataset: unique IDs 'trial<t>/user-<i>', hashed with BLAKE2b.")
    print("Each cell is the mean absolute relative error over 3 independent salts.\n")
    print(f"{'n':>10} | {'m=1024':>10} | {'m=4096':>10} | {'m=16384':>10}")
    print("-" * 52)

    for n in sizes:
        errors = {p: [] for p in p_values}
        for trial in range(trials):
            sketches = {p: HyperLogLog(p=p, seed=trial) for p in p_values}
            for i in range(n):
                h = stable_hash_64(f"trial{trial}/user-{i}", seed=trial)
                for sketch in sketches.values():
                    sketch.add_hash(h)

            for p in p_values:
                estimate = sketches[p].estimate()
                errors[p].append(abs(estimate - n) / n)

        cells = " | ".join(
            f"{sum(errors[p]) / len(errors[p]):>9.3%}" for p in p_values
        )
        print(f"{n:>10,} | {cells}")

    print("\nTheoretical standard error 1.04/sqrt(m):")
    for p in p_values:
        m = 1 << p
        print(f"  m={m:>5}: {1.04 / math.sqrt(m):.3%}")


def main() -> None:
    print("HyperLogLog verification")
    print("=" * 52)
    check_tiny_example()
    check_duplicates()
    check_merge()
    check_small_range()
    accuracy_benchmark()

    print("\nExample memory footprint:")
    for p in (10, 12, 14, 16):
        m = 1 << p
        print(f"  p={p:>2}, m={m:>6,} registers -> {m} bytes (~{m / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
