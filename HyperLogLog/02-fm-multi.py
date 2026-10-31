import hashlib
import statistics

import hashlib
import math


class FlajoletMartin:
    def __init__(self):
        self.max_rho = 0

    def _hash(self, value):
        h = hashlib.md5(str(value).encode()).hexdigest()
        return int(h, 16)

    def _rho(self, hashed_value):
        """
        Position of least significant 1 bit.
        Example:
        1      -> 0
        10     -> 1
        100    -> 2
        """
        if hashed_value == 0:
            return 128

        position = 0
        while (hashed_value & 1) == 0:
            position += 1
            hashed_value >>= 1

        return position

    def add(self, item):
        h = self._hash(item)
        r = self._rho(h)
        self.max_rho = max(self.max_rho, r)

    def estimate(self):
        # Flajolet-Martin correction constant
        phi = 0.77351
        return (2 ** self.max_rho) / phi


# Example usage
fm = FlajoletMartin()

data = [
    "apple",
    "banana",
    "orange",
    "apple",
    "banana",
    "grape",
    "kiwi"
]

for item in data:
    fm.add(item)

print("Estimated distinct count:", round(fm.estimate()))
print("Actual distinct count:", len(set(data)))


class FlajoletMartinMulti:
    def __init__(self, num_hashes=32):
        self.num_hashes = num_hashes
        self.max_rhos = [0] * num_hashes

    def _hash(self, value, seed):
        h = hashlib.md5(f"{seed}_{value}".encode()).hexdigest()
        return int(h, 16)

    def _rho(self, x):
        if x == 0:
            return 128

        r = 0
        while (x & 1) == 0:
            r += 1
            x >>= 1

        return r

    def add(self, item):
        for i in range(self.num_hashes):
            h = self._hash(item, i)
            self.max_rhos[i] = max(self.max_rhos[i], self._rho(h))

    def estimate(self):
        phi = 0.77351
        estimates = [(2 ** r) / phi for r in self.max_rhos]
        return statistics.median(estimates)


# Example
fm = FlajoletMartinMulti(num_hashes=64)

for item in data:
    fm.add(item)

print("Estimated distinct count:", round(fm.estimate()))