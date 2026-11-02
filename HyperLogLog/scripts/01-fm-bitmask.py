"""COUNT from the 1985 paper: one bitmap, first missing rank.

Run: python HyperLogLog/01-fm-bitmask.py
Then read 07-fm-pcsa-story.md and open 08-fm-pcsa-playground.html.
"""

from fm_common import HASH_BITS, PHI, first_zero, hash_customer, rho, small_visits


class FlajoletMartinBitmap:
    """
    Educational implementation of the original Flajolet-Martin algorithm.

    Core idea:
    ----------
    1. Hash each incoming item.
    2. Find position of the least significant set bit (LSB).
    3. Set that position in a bitmap.
    4. First zero in bitmap estimates log2(cardinality).

    This implementation prioritizes understanding over optimization.
    """

    # Correction constant from Flajolet-Martin paper
    PHI = PHI

    def __init__(self, bitmap_size: int = 64, seed: int = 0, trace: bool = False):
        if not 1 <= bitmap_size <= HASH_BITS:
            raise ValueError("bitmap_size must be between 1 and 64")
        self.bitmap_size = bitmap_size
        self.seed = seed
        self.trace = trace
        self.has_items = False

        # Bitmap initially contains only zeros
        self.bitmap = [0] * bitmap_size

    # -----------------------------------------------------
    # Step 1: Hash incoming value
    # -----------------------------------------------------
    def hash_value(self, value: str) -> int:
        """
        SHA-256 truncated to 64 bits is our practical uniform-hash model.
        Hash the customer ID, not the receipt ID or the entire receipt.
        """
        return hash_customer(value, self.seed)

    # -----------------------------------------------------
    # Step 2: Find least significant set bit position
    # -----------------------------------------------------
    def least_significant_one_position(self, number: int) -> int:
        """
        Example:

        binary: 1001000
                        ^
                        first 1 from right

        returns 3
        """

        return rho(number)  # Also handles zero without an infinite loop.

    # -----------------------------------------------------
    # Step 3: Update bitmap
    # -----------------------------------------------------
    def add(self, value: str):
        hashed = self.hash_value(value)
        position = self.least_significant_one_position(hashed)
        self.has_items = True
        if position < self.bitmap_size:
            self.bitmap[position] = 1
        # A rank outside the bitmap is not clamped into its last cell.
        if self.trace:
            print(f"{value}: hash suffix={hashed & 0xffff:016b}, rho={position}, "
                  f"R={self.first_zero_position()}")

    # -----------------------------------------------------
    # Step 4: Find first zero bit
    # -----------------------------------------------------
    def first_zero_position(self) -> int:

        return first_zero(self.bitmap)

    # -----------------------------------------------------
    # Step 5: Estimate cardinality
    # -----------------------------------------------------
    def estimate(self, raw: bool = False) -> float:
        # Empty-stream guard, NOT a general small-cardinality correction.
        if not self.has_items and not raw:
            return 0.0
        R = self.first_zero_position()
        if R == self.bitmap_size:
            raise OverflowError("Bitmap saturated: increase bitmap_size")
        # Log-calibrated single-bitmap estimate, not an unbiased count.
        return (2**R) / self.PHI

    def print_bitmap(self):

        print("Bitmap in rank order: index 0 is LEFT (not an integer display)")
        print("".join(str(bit) for bit in self.bitmap))


# ==========================================================
# Example Usage
# ==========================================================

if __name__ == "__main__":
    fm = FlajoletMartinBitmap(bitmap_size=32, trace=True)
    visits = small_visits()
    for visit in visits:
        print(f"Receipt {visit['receipt_id']}, checkout {visit['checkout']}", end=" -> ")
        fm.add(visit["customer_id"])

    fm.print_bitmap()
    print("Receipts:", len(visits))
    print("Actual unique customers:", len({v["customer_id"] for v in visits}))
    print("First missing rank (first zero'th position in right side) Rh0:", fm.first_zero_position())
    print("Single-bitmap estimate:", round(fm.estimate(), 2))
    before = fm.bitmap.copy()
    fm.trace = False
    
    for visit in visits * 10:
        fm.add(visit["customer_id"])

    print("Replay 200 receipts; bitmap unchanged:", fm.bitmap == before)
    print("A tiny dataset teaches updates; a single bitmap is very noisy.")
