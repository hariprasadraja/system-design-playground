import hashlib
from typing import List


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
    PHI = 0.77351

    def __init__(self, bitmap_size: int = 64):
        self.bitmap_size = bitmap_size

        # Bitmap initially contains only zeros
        self.bitmap = [0] * bitmap_size

    # -----------------------------------------------------
    # Step 1: Hash incoming value
    # -----------------------------------------------------
    def hash_value(self, value: str) -> int:
        """
        Convert any value into a uniformly distributed integer.

        SHA1 is used for demonstration.
        """
        digest = hashlib.sha1(value.encode()).hexdigest()

        return int(digest, 16)

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

        position = 0

        while (number & 1) == 0:  # mask 0000001
            position += 1
            number >>= 1

        return position

    # -----------------------------------------------------
    # Step 3: Update bitmap
    # -----------------------------------------------------
    def add(self, value: str):
        hashed = self.hash_value(value)
        binary_representation = bin(hashed)[2:]

        position = self.least_significant_one_position(hashed)
        print(f"{value} ({binary_representation}) -> position: {position}")

        if position < self.bitmap_size:
            print(f"Bitmap[{position}]: 1")
            self.bitmap[position] = 1

    # -----------------------------------------------------
    # Step 4: Find first zero bit
    # -----------------------------------------------------
    def first_zero_position(self) -> int:

        for i in range(self.bitmap_size):
            if self.bitmap[i] == 0:
                return i

        return self.bitmap_size - 1

    # -----------------------------------------------------
    # Step 5: Estimate cardinality
    # -----------------------------------------------------
    def estimate(self) -> float:

        R = self.first_zero_position()
        print("First zero position:", R)

        # Original FM estimate
        return (2**R) / self.PHI

    def print_bitmap(self):

        print("Bitmap:")
        print("".join(str(bit) for bit in self.bitmap))


# ==========================================================
# Example Usage
# ==========================================================

fm = FlajoletMartinBitmap(bitmap_size=32)

data = [
    "A",
    "B",
    "A",
    "C",
    "D",
    "D",
    "E",
    "F",
    "F",
    "G",
    "H",
    "H",
    "I",
    "J",
    "J",
    "K",
    "L",
]

for item in data:
    fm.add(item)

fm.print_bitmap()

print("First zero position:", fm.first_zero_position())
print("Estimated cardinality:", round(fm.estimate(), 2))
print("Actual distinct count:", len(set(data)))
