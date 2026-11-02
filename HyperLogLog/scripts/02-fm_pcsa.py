"""Paper-faithful direct averaging and PCSA, using one grocery-store story.

02-fm-multi.py keeps max_rhos and takes a median. That is NOT the
bitmap/first-zero estimator analysed in this paper. See lesson section 2
for a line-by-line explanation of that max() expression.

Run: python HyperLogLog/fm_pcsa.py --distinct 10000 --repeats 20000 --maps 64
"""

import argparse
import math

from fm_common import HASH_BITS, PHI, customer_stream, first_zero, hash_customer, rho


class FlajoletMartinMulti:
    """Direct averaging: every customer updates EVERY bitmap (p. 196)."""

    def __init__(self, buckets=64, bitmap_size=32, seed=0):
        if buckets < 1 or not 1 <= bitmap_size <= HASH_BITS:
            raise ValueError("Need positive num_hashes and bitmap_size in 1..64")
        self.buckets_count = buckets
        self.bitmap_size = bitmap_size
        self.seed = seed
        self.bitmaps = [[0] * bitmap_size for _ in range(buckets)]
        self.has_items = False

    def add(self, customer_id):
        self.has_items = True
        for i in range(self.buckets_count):
            # Domain-separated hashes model independent observers.
            # It refers to different hash functions, but we can use one hash with a different seed per observer. This is a common trick in practice. 
            h = hash_customer(customer_id, self.seed + i)
            rank = rho(h)
            if rank < self.bitmap_size:
                self.bitmaps[i][rank] = 1  # Keep gaps, not just the maximum!
            print(f"DA:Customer {customer_id} hashed to {h}, bucket {i}, rank {rank}")  # Debugging output

    def ranks(self):
        return [first_zero(bitmap) for bitmap in self.bitmaps]

    def estimate(self, raw=False):
        if not self.has_items and not raw:
            return 0.0
        ranks = self.ranks()
        if self.bitmap_size in ranks:
            raise OverflowError("A bitmap saturated: increase bitmap_size")
        average_rank = sum(ranks) / self.buckets_count
        # Each observer saw the whole stream: NO factor num_hashes here.
        return 2**average_rank / PHI


class PCSA:
    """Stochastic averaging: each customer updates ONE bitmap (Fig. 1)."""

    def __init__(self, num_maps=64, bitmap_size=32, seed=0):
        if num_maps < 1 or num_maps & (num_maps - 1):
            raise ValueError("Use a positive power of two for num_maps")
        self.address_bits = num_maps.bit_length() - 1
        self.rank_bits = HASH_BITS - self.address_bits
        if not 1 <= bitmap_size <= self.rank_bits:
            raise ValueError("Bitmap must fit in the hash bits left after routing")
        self.num_bucket = num_maps
        self.bitmap_size = bitmap_size
        self.seed = seed
        self.bitmaps = [[0] * bitmap_size for _ in range(num_maps)]
        self.has_items = False

    def add(self, customer_id):
        hashed = hash_customer(customer_id, self.seed)
        
        bucket = hashed % self.num_bucket       # Which virtual notebook?
        remaining = hashed // self.num_bucket  # Remove the routing bits.
        rank = rho(remaining, self.rank_bits)
        self.has_items = True
        if rank < self.bitmap_size:
            self.bitmaps[bucket][rank] = 1



        return bucket, rank  # Helpful for tracing; not stored per customer.
 
    def ranks(self):
        return [first_zero(bitmap) for bitmap in self.bitmaps]

    def estimate(self, bias_correct=False, raw=False):
        if not self.has_items and not raw:
            return 0.0
        ranks = self.ranks()
        if self.bitmap_size in ranks:
            raise OverflowError("A bitmap saturated: increase bitmap_size")
        average_rank = sum(ranks) / self.num_bucket
        estimate = self.num_bucket * 2**average_rank / PHI
        if bias_correct:
            estimate /= 1 + 0.31 / self.num_bucket  # Section 4, p. 203.
        return estimate

    def merge(self, other):
        if (self.num_bucket, self.bitmap_size, self.seed) != (
            other.num_maps, other.bitmap_size, other.seed
        ):
            raise ValueError("Merge needs matching hash seed, map count and width")
        for left, right in zip(self.bitmaps, other.bitmaps):
            for rank in range(self.bitmap_size):
                left[rank] |= right[rank]
        self.has_items |= other.has_items
        return self

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--distinct", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=16)
    parser.add_argument("--maps", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.distinct < 0 or args.repeats < 0:
        parser.error("Counts must be nonnegative")
    try:
        pcsa = PCSA(args.maps, seed=args.seed)
        direct = FlajoletMartinMulti(args.maps, seed=args.seed)
    except ValueError as error:
        parser.error(str(error))
    receipts = 0

    # Known cardinality checks the demo; the sketch never uses it.
    for customer_id in customer_stream(args.distinct, args.repeats):
        direct.add(customer_id)
        pcsa.add(customer_id)
        receipts += 1


    print(f"Hari's Grocery: {receipts:,} receipts; {args.distinct:,} unique customers")
    print(f"Direct: {args.maps} hashes + updates per receipt; estimate={direct.estimate():,.2f}")
    print(f"PCSA:   1 hash + update per receipt; estimate={pcsa.estimate():,.2f}")
    print(f"PCSA with approximate bias correction: {pcsa.estimate(bias_correct=True):,.2f}")
    print("PCSA first missing ranks:", pcsa.ranks())
    print(f"Mean unique customers per virtual bucket: {args.distinct / args.maps:.2f}")
    print(f"Large-load theoretical standard error: {0.78 / math.sqrt(args.maps):.2%}")
    print("This is a standard deviation across hash trials, not a guaranteed error bound.")
    if args.distinct / args.maps < 20:
        print("Small-load regime: the paper's asymptotic formula is unreliable here.")
    print("Packed bitmap payload:", args.maps * pcsa.bitmap_size // 8,
          "bytes (Python lists use substantially more).")


if __name__ == "__main__":
    main()

    # H1      H2             H3
# Direct - [[1,1,0,0,0,1,0],[1,0,0,0,0,1,0],[1,1,1,0,0,1,0]]
# sum = 2 + 2 + 2 / 3 = 2
# 2^2 / PHI = 4 / 0.77351 = 5.17

# Pre-Define 3 Buckets

#                     C1,C4,C7                C2,C5,C8             C3 ,C6                         
# Stochastic - [[1,1,0,0,0,1,0],[1,1,1,0,0,0,0],[1,0,0,0,0,1,0]]
# sum = 2 + 3 + 1 / 3 = 2
# 3 * 2^2 / PHI = 3 * 4 
