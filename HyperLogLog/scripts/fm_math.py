"""Recompute the paper's probabilities and phi with Python's standard library."""

import math


EULER_GAMMA = 0.5772156649015328606


def q_exact(n, k):
    """Theorem 1: P(R >= k), using zero-based ranks.

    This inclusion-exclusion sum is exponential in k and can suffer
    cancellation. Bound it to teaching-size inputs, not production counting.
    """
    if n < 0 or k < 0 or k > 18:
        raise ValueError("Use n >= 0 and 0 <= k <= 18")
    if k == 0:
        return 1.0
    if k > n:
        return 0.0
    denominator = 2**k
    result = math.fsum(
        (-1 if j.bit_count() % 2 else 1) * ((denominator - j) / denominator)**n
        for j in range(denominator)
    )
    # Remove tiny floating-point excursions; not a statistical correction.
    return min(1.0, max(0.0, result))


def psi(x):
    """Equation (13): the smooth infinite product, truncated numerically."""
    if x <= 0:
        return 0.0
    product = 1.0
    while x < 40:
        product *= -math.expm1(-x)
        x *= 2
    return product  # Omitted factors differ from 1 by less than exp(-40).


def phi_product(terms):
    """Theorem 3.A, evaluated in log space; terms is a truncation count."""
    if terms < 0:
        raise ValueError("terms must be nonnegative")
    log_phi = EULER_GAMMA - math.log(2) / 2 + math.log(2 / 3)
    log_phi += math.fsum(
        (-1 if j.bit_count() % 2 else 1)
        * math.log1p(2 / (4 * j * (4 * j + 3)))
        for j in range(1, terms + 1)
    )
    return math.exp(log_phi)


def main():
    print("Theorem 3.A: product terms -> phi (no data fitting)")
    for terms in (1, 2, 4, 16, 100, 1000, 10000):
        print(f"{terms:6d} -> {phi_product(terms):.12f}")
    print("\nTwo unique customers: exact p(R=k)")
    for k in range(3):
        print(k, q_exact(2, k) - q_exact(2, k + 1))
    print("\nn=100: equations (Theorem 1, equation 14), zero-based k")
    print(" k      exact p         psi approximation")
    for k in range(3, 12):
        exact = q_exact(100, k) - q_exact(100, k + 1)
        approximate = psi(100 / 2**k) - psi(100 / 2**(k + 1))
        print(f"{k:2d}    {exact:.9f}       {approximate:.9f}")
    tails = [q_exact(100, k) for k in range(1, 18)]
    mean = math.fsum(tails)
    second = math.fsum((2 * k - 1) * q for k, q in enumerate(tails, 1))
    variance = second - mean**2
    print(f"\nTruncated exact moments for n=100: E[R]={mean:.9f}")
    print(f"Var(R)={variance:.9f}, SD(R)={math.sqrt(variance):.9f}")
    print("Compare the source's Table I carefully: see lesson section 5.")


if __name__ == "__main__":
    main()
