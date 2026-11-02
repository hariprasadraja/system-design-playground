"""
====================================================
LOGLOG ALGORITHM - EDUCATIONAL IMPLEMENTATION
====================================================

Goal:
Estimate the number of DISTINCT elements
without storing all elements.

This code demonstrates:

1. Hashing
2. Bucket selection
3. Leading-zero counting
4. Register updates
5. Cardinality estimation

The example includes sample data.
"""

import hashlib
import math
import random


class LogLog:
    """
    Educational LogLog implementation.

    m = number of buckets
    Must be power of 2
    """

    def __init__(self, m=64):

        if m & (m - 1):
            raise ValueError("m must be power of 2")

        self.m = m
        self.k = int(math.log2(m))  # log2(64) = 6, you will have 6 digit prefix to select register

        # Registers
        self.registers = [0] * m

        # Bias correction constant
        # Paper uses alpha ≈ 0.39701 for large m
        self.alpha = 0.39701

    # --------------------------------------------------
    # Hash function
    # --------------------------------------------------
    def hash_value(self, item):

        h = hashlib.sha1(str(item).encode()).hexdigest()

        return int(h, 16)

    # --------------------------------------------------
    # Position of first 1 bit
    # --------------------------------------------------
    def rho(self, value):

        if value == 0:
            return 65

        rank = 1

        while (value & (1 << 63)) == 0:
            rank += 1
            value <<= 1

        return rank

    # --------------------------------------------------
    # Add item
    # --------------------------------------------------
    def add(self, item):

        h = self.hash_value(item)

        # Use lower 64 bits
        h = h & ((1 << 64) - 1)

        # First k bits -> bucket id
        bucket = h >> (64 - self.k)

        # Remaining bits
        remaining = (h << self.k) & ((1 << 64) - 1)

        rank = self.rho(remaining)

        self.registers[bucket] = max(
            self.registers[bucket],
            rank
        )

    # --------------------------------------------------
    # Estimate cardinality
    # --------------------------------------------------
    def estimate(self):

        avg_register = sum(self.registers) / self.m

        estimate = (
            self.alpha
            * self.m
            * (2 ** avg_register)
        )

        return round(estimate)

    def show_registers(self):

        print("\nRegisters:")
        print(self.registers)


# ====================================================
# SAMPLE DATASET
# ====================================================

def generate_sample_data():

    """
    Create a stream with duplicates.

    True distinct count = 10,000
    Total records = 50,000
    """

    distinct_values = [
        f"user_{i}"
        for i in range(10000)
    ]

    stream = []

    for _ in range(50000):
        stream.append(
            random.choice(distinct_values)
        )

    return stream


# ====================================================
# DEMO
# ====================================================

def main():

    random.seed(42)

    stream = generate_sample_data()

    actual_distinct = len(set(stream))

    print("=" * 60)
    print("LOGLOG DEMO")
    print("=" * 60)

    print(f"Total records      : {len(stream)}")
    print(f"Actual distinct    : {actual_distinct}")

    ll = LogLog(m=64)

    for item in stream:
        ll.add(item)

    estimate = ll.estimate()

    print(f"LogLog estimate    : {estimate}")

    error = (
        abs(estimate - actual_distinct)
        / actual_distinct
    ) * 100

    print(f"Error (%)          : {error:.2f}")

    ll.show_registers()


if __name__ == "__main__":
    main()