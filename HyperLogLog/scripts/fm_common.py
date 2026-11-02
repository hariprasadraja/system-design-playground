"""Shared mechanics and synthetic grocery-store data for the FM lessons."""

import csv
import hashlib
from pathlib import Path


PHI = 0.773516290951
HASH_BITS = 64


def hash_customer(customer_id, seed=0):
    """Same ID + seed -> same 64-bit hash, including on another checkout."""
    message = f"{seed}:{customer_id}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(message).digest()[:8], "big")


def rho(number, width=HASH_BITS):
    """Zero-based trailing-zero count; zero has no 1, so return width."""
    if number < 0:
        raise ValueError("Use an unsigned hash")
    if number == 0:
        return width
    return (number & -number).bit_length() - 1


def first_zero(bitmap):
    """Scan increasing RANK, independently of how bits are printed."""
    for rank, bit in enumerate(bitmap):
        if bit == 0:
            return rank
    return len(bitmap)  # Sentinel: there is no zero within stored ranks.


def small_visits():
    path = Path(__file__).with_name("data") / "grocery-visits.csv"
    with path.open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def customer_stream(distinct=10000, repeat_visits=20000):
    """Promotion day: everyone visits once; regulars visit many more times.

    All IDs are synthetic. Hash ONLY customer_id, not receipt or checkout.
    Generator avoids keeping the full receipt stream in the sketch.
    """
    if distinct < 0 or repeat_visits < 0:
        raise ValueError("Counts must be nonnegative")
    for customer in range(distinct):
        yield f"C{customer + 1:05d}"
    if distinct:
        regulars = min(20, distinct)
        for visit in range(repeat_visits):
            yield f"C{visit % regulars + 1:05d}"
