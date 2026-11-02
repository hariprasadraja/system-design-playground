# FM → PCSA: one grocery store, from receipts to reliable estimates

**The whole story:** Hari owns **Hari's Grocery**. Customers sometimes return several times. Two checkout machines record receipts. Hari wants **how many different customers visited**, using very little memory.

The source is Flajolet & Martin, *Probabilistic Counting Algorithms for Data Base Applications* (1985), your [PDF](Faljolet-Martin%20Algorithm.pdf). References below give **printed page / PDF page**; printed page 182 is PDF page 1.

## Start here

1. Open **[the interactive lab](08-fm-pcsa-playground.html)** in a browser. It works offline; keep its companion `fm-pcsa-playground.js` alongside it.
2. Read sections 1–4 and step through the receipts in Lab 1.
3. Read sections 5–7 and run Labs 2–3.
4. Read sections 8–11 and try the distribution, constant, merge and deletion experiments.
5. Section 12 maps the **whole paper**, including its mathematical proof machinery, to this story.

Python examples (run from the repository root; Python 3.10+, no packages). The optional last check also requires Node.js:

```powershell
python HyperLogLog/01-fm-bitmask.py
python HyperLogLog/fm_pcsa.py --distinct 10000 --repeats 20000 --maps 64
python HyperLogLog/fm_pcsa.py --distinct 12 --repeats 8 --maps 64
python HyperLogLog/fm_math.py
python -m unittest discover -s HyperLogLog -p "test_fm*.py"
node --test HyperLogLog/test-fm-playground.cjs
```

The small [CSV](data/grocery-visits.csv) has **20 receipts, 12 unique customers**, repeated customers, and overlapping checkouts. The generated promotion day has **10,000 unique customers plus 20,000 repeat visits** concentrated on 20 regulars. Both are synthetic but model the actual question. Exact sets in the lab are a teaching scoreboard; they are **not part of the sketch**.

Verified Python readouts with the default seed 0:

| Dataset | Actual unique IDs | Single bitmap | Direct, m=64 | PCSA, m=64 |
|---|---:|---:|---:|---:|
| 20 receipts, IDs C00001–C00012 | 12 | 5.17 (R=2) | 12.98 | 89.26 |
| 30,000-receipt promotion | 10,000 | — | 9,607.01 | 8,528.03 |

The PCSA result is about 14.72% low in this particular run. This is deliberately shown: a roughly 10% standard error is **not** a ±10% guarantee. Change `--seed` to study variability rather than selecting only favourable runs.

---

## 1. What precisely are we counting?

One receipt might contain:

```text
receipt=R003, checkout=A, customer=C00001, basket=bread
```

Hash **C00001**. Hashing `R003` would count receipts. Hashing the whole row would count different receipt records. Counting people also assumes the same person consistently uses the same customer ID.

We give each customer a permanent, random-looking binary ticket: their hash. A repeat visit produces **exactly the same ticket**. There are no fresh coin flips on repeat visits.

The ideal model says distinct customers' hash bits act like independent fair coin flips. A deterministic hash is a practical way to approximate that model. A fixed dataset and fixed hash seed always produce the same answer. To study variability, rerun the same customers with **different hash seeds**.

Three separate quantities will appear:

| Symbol | Plain English | Grocery meaning |
|---|---|---|
| `n` | Actual distinct count | Number of different customer IDs |
| `ρ(h)` (rho) | Rank of this one hash | Number of trailing zeros in one customer's ticket |
| `R` | First missing rank | First unmarked box in a notebook, starting at rank 0 |
| `M` | Maximum observed rho | Largest rank any ticket has reached |
| `m` | Number of bitmaps | Number of virtual notebooks |
| `A` | Mean of the R values | Average notebook reading |

**ρ, R, and M are not interchangeable.** This distinction explains the largest gap in the old examples.

## 2. What did `self.max_rhos[i] = max(...)` mean?

The old code was:

```python
self.max_rhos[i] = max(self.max_rhos[i], self._rho(h))
```

Expand it:

```python
previous_record = self.max_rhos[i]
this_customers_rank = self._rho(h)
larger_of_the_two = max(previous_record, this_customers_rank)
self.max_rhos[i] = larger_of_the_two
```

`i` identifies a hash function/observer. Imagine observer 2 has written **3** as its highest rank so far:

| Next customer's rho | Calculation | New record |
|---:|---|---:|
| 1 | `max(3, 1)` | 3 |
| 5 | `max(3, 5)` | 5 |
| 2 | `max(5, 2)` | 5 |
| 5 again | `max(5, 5)` | 5 |

That line means **“remember the record, forget everything smaller.”** It neither increments a customer count nor averages anything.

But consider these two notebooks:

```text
Observed ranks: {0, 1, 3}        M=3, R=2
Observed ranks: {0, 1, 2, 3}     M=3, R=4
```

A maximum cannot distinguish them. The paper's bitmap can.

### The important correction

The former `02-fm-multi.py` used maximum ranks, applied `0.77351`, and took a median of individual estimates. **That combination is not the COUNT/direct-averaging/PCSA algorithm analysed in this paper.** It was misleading to label it as such.

The runnable companion **[fm_pcsa.py](fm_pcsa.py)** implements the paper's actual route:

```python
bitmaps[i][rank] = 1                  # remember that exact rank appeared
R_i = first_zero(bitmaps[i])          # preserve knowledge of gaps
A = sum(R_values) / number_of_maps   # average R, then exponentiate
```

Max-based sketches are a legitimate different family, including later LogLog/HLL designs, with their own indexing and calibration. **Do not borrow their constants or estimators for bitmap FM, or vice versa.** Earlier HLL notes in this folder describe the old max-based example; use this lesson as the source of truth for the 1985 paper.

## 3. One notebook: COUNT

For illustration only, assign the first customers these short tickets:

| Customer | Hash in ordinary binary notation | rho | Mark |
|---|---|---:|---|
| C00001 | `1011` | 0 | box 0 |
| C00002 | `0110` | 1 | box 1 |
| C00003 | `1000` | 3 | box 3 |
| C00001 again | `1011` | 0 | box 0, already marked |

These are hand-picked teaching tickets, not the SHA-256 outputs in Python.

The notebook now says:

```text
rank:    0 1 2 3 4 5 6 7
marked:  1 1 0 1 0 0 0 0
             ^ first missing rank R=2
```

There is no requirement to set boxes below an observed rank. Seeing rank 3 sets **only box 3**. If a later customer has rank 2, the bitmap becomes `11110000` and R jumps from 2 to 4.

Duplicate visits do not change a set bit. Different customers can also hit the same rank; that is intended compression, not necessarily a collision of their entire hashes.

The single-bitmap readout is:

```text
estimate = 2^R / φ          φ ≈ 0.77351629
```

You already understand `2^R`: one extra rung represents approximately a doubling of the customer population. The rest of this lesson explains the correction and why one notebook is noisy.

### Plain words for the confusing line

Don't say: "box r means someone got rank ≥ r."

Say it like this instead:

**A filled box means the grocery store got big enough to reach that rung.**

Box 0 is the first rung at the bottom. Box 1 is the next rung up. If a customer's luck streak reaches rung 5, we know the store has grown big enough to hit step 5 — so we fill the boxes along the way.

We stop at the first **empty** box. That empty box is the true edge of the store. Raising 2 to that number gives us our guess for how many customers there were.

### Better, concrete example

One checkout, 20 customers that day.

- Most customers are ordinary → box 0 gets filled.
- Some are luckier → boxes 1, 2, 3 get filled.
- One is very lucky → box 5 gets filled.

The notebook for boxes 0 through 5 looks like this:

```text
boxes:  0 1 2 3 4 5
state:  1 1 1 1 0 1
```

We read from the bottom and stop at the first empty box → that is **R = 4**.

Estimate: `2^4 / φ ≈ 20.7` → about **20 customers** — exactly right.

If we had stopped at the last filled box instead (5), the estimate would be about **41** — twice too big.

That is why we scan for the first empty box: it is the real edge of the store.

## 4. Why scan left to right? Evidence, not a convention to memorise

**The real rule is scan ranks 0, 1, 2, … and stop at the first zero.**

The paper prints `BITMAP[0]` on the **left**. An integer printer usually puts bit 0 on the **right**. The same stored bits can be drawn either way:

```text
Array/rank drawing:          1 1 0 1 0 0 0 0
Indices:                    0 1 2 3 4 5 6 7
Scan:                       ---------->

Packed integer drawing:     0 0 0 0 1 0 1 1    integer value 11
Bit indices:                7 6 5 4 3 2 1 0
Scan:                       <----------
```

Both give **R=2**. Byte endianness does not change this rule either.

There are also **two different scans**:

1. Inspect **a hash** from its least-significant end to find its first **one**: rho.
2. Inspect **the bitmap** in increasing rank to find its first **zero**: R.

### Three pieces of direct evidence in the paper

1. **p. 185 / PDF 4:** rho is the position of the least significant 1; ranks start at zero. The example bitmap `111111111111001100000000` has R=12 and highest set rank 15. This explicitly establishes its array display order.
2. **p. 186 / PDF 5:** the mathematical definition of `R_n=r` requires **every rank j<r to have appeared and rank r never to have appeared**. That determines which end to start from without any picture.
3. **Fig. 1, p. 197 / PDF 16:** pseudocode starts `R := 0` and increments R while `BITMAP[i,R]=1`.

Why not start at the largest rank? With a wide enough bitmap, that end is mostly zeros; you'd measure the chosen storage width instead of the customer population.

Why not use the highest **one**? That is M, a different statistic. The paper explicitly says on **p. 206 / PDF 25** that it has a flatter distribution and appreciably worse standard error.

Concrete evidence: after ranks `{0,1,3}`, add one very lucky customer with rank 12. **M jumps 3→12; R stays 2.** The missing common rank 2 still matters. The lab lets you reproduce this, and reverse the display without changing R.

For a mathematical comparison, the ideal maximum obeys:

```text
P(M ≥ k) = 1 − (1 − 2^−k)^n.
```

Only one lucky customer is needed. In contrast, `R≥k` needs **all** ranks 0 through k−1. That gives R a much sharper upper tail. This is evidence about distributional accuracy, not a promise that R wins on every individual dataset.

## 5. Probability distribution: four different questions

The store stays the same. We now ask what would happen across many imaginary hash assignments to the same customers.

### 5.1 One customer's rank

Read the hash from the least-significant end:

| Rank k | Bits in reading order | Chance of exactly this rank | Expected customers among 64 |
|---:|---|---:|---:|
| 0 | `1` | 1/2 | 32 |
| 1 | `01` | 1/4 | 16 |
| 2 | `001` | 1/8 | 8 |
| 3 | `0001` | 1/16 | 4 |
| 4 | `00001` | 1/32 | 2 |
| 5 | `000001` | 1/64 | 1 |

These are **expectations**, not quotas. A day with 64 unique customers need not contain a rank-5 ticket.

```text
P(ρ=k) = 2^−(k+1)       exactly k zeros, then a one
P(ρ≥k) = 2^−k           at least k zeros; next bit unrestricted
```

### 5.2 Will a particular box be marked?

Each distinct customer misses box k with probability `1−2^−(k+1)`.
All n miss it with probability `(1−2^−(k+1))^n`. Therefore:

```text
P(box k is marked) = 1 − (1−2^−(k+1))^n.
```

For 8 customers and box 2:

```text
Expected hits = 8 × 1/8 = 1.
Chance of zero hits = (7/8)^8 ≈ 34.36%.
Chance of at least one hit ≈ 65.64%.
```

**“One expected hit” does not mean “certainly one hit.”** This is why the boundary is a messy fringe of zeros and ones.

### 5.3 Where will the first missing box be?

The paper defines:

```text
p[n,k] = P(R=k)          first missing box is EXACTLY k
q[n,k] = P(R≥k)          all boxes below k are marked
p[n,k] = q[n,k] − q[n,k+1]
```

Do not confuse these with the distribution of one customer's rho.

Start with **two unique customers**:

* R=0 when both miss box 0: `(1/2)^2 = 1/4`.
* R≥1 when at least one hits box 0: `3/4`.
* R≥2 requires one at rank 0 and one at rank 1, in either order:
  `2 × (1/2) × (1/4) = 1/4`.
* R≥3 is impossible: two customers cannot occupy three different rank boxes.

So the complete distribution is:

| R | Probability | Out of many trials, approximately |
|---:|---:|---:|
| 0 | 1/4 | 25% |
| 1 | 1/2 | 50% |
| 2 | 1/4 | 25% |

### 5.4 Inclusion–exclusion, without the intimidating notation

For `R≥2`, Hari needs both boxes 0 and 1 filled.

Start with all possible days. Subtract days missing box 0. Subtract days missing box 1. Days missing **both** got subtracted twice, so add those back once:

```text
q[n,2] = 1 − (1/2)^n − (3/4)^n + (1/4)^n.
```

For n=2: `1 − 1/4 − 9/16 + 1/16 = 1/4`, matching the customer-by-customer reasoning.

For more boxes, keep subtracting missing singles, adding missing pairs, subtracting missing triples, and so on. This is exactly the mechanism on **pp. 186–188 / PDF 5–7**.

Theorem 1 packages it as:

```text
q[n,k] = Σ from j=0 to 2^k−1 of (−1)^popcount(j) × (1−j/2^k)^n.
```

`popcount(j)` just counts 1s in j's binary representation. It says how many missing-box events were selected, which decides the plus/minus sign. The paper sometimes includes endpoint `j=2^k`; its term is zero when n>0. Handle n=0 separately: R=0 with certainty.

Do not multiply individual box-fill probabilities to get an **exact fixed-n** answer: the occupancies are dependent. With only two customers, filling one box consumes a customer that cannot fill another.

### The smooth approximation in Theorem 2

For a rare event with chance a, `(1−a)^n ≈ exp(−na)`. For the store, this replaces a cumbersome “n repeated misses” calculation by a smooth curve.

The paper defines:

```text
ψ(x) = (1−e^−x)(1−e^−2x)(1−e^−4x)…
q[n,k] ≈ ψ(n/2^k)
p[n,k] ≈ ψ(n/2^k) − ψ(n/2^(k+1)).
```

Interpretation: the rarest required box, k−1, expects `n/2^k` hits; the preceding box expects twice that, then four times that. The factors are approximate probabilities that each is nonempty. Poissonising the customer total gives a related independence justification; the paper obtains its fixed-n approximation using inclusion–exclusion and exponential estimates. It is **not exact independence at fixed n**.

Theorem 2 also proves: far below log₂n, R is almost surely larger; near log₂n the transition occurs; far above it the tail dies rapidly. Its upper-tail range begins at **(3/2)log₂n + δ**, not “4 log n” as the OCR suggests.

### A source-reading trap in Table I

**p. 191 / PDF 10:** the heading says q, but the bell-shaped entries are point probabilities p, not decreasing tail probabilities q. There are also apparent one-column rank offsets and exact/approximation row inconsistencies.

Using the paper's zero-based definition and equations, for n=100, k=6:

```text
Exact p[100,6]       ≈ 0.34757612
ψ approximation     ≈ 0.34529782
```

The table places closely related values under k=7, with about `0.3452` in the upright row and `0.3476` in italics. We use **recomputed equations**, label p versus q explicitly, and keep zero-based ranks throughout. The math script and Lab 4 let you verify this independently.

## 6. Variance and standard deviation: how much does the answer wobble?

Return to the two-customer distribution `[25%, 50%, 25%]` for R=`[0,1,2]`.

1. Average R: `0×1/4 + 1×1/2 + 2×1/4 = 1`.
2. Distances from that average: `−1, 0, +1`.
3. Square them: `1, 0, 1`. Otherwise positive and negative distances cancel.
4. Probability-weighted average square: `1×1/4 + 0×1/2 + 1×1/4 = 0.5`.
5. Undo the square: `sqrt(0.5) ≈ 0.7071`.

**Variance = 0.5 ranks². Standard deviation = 0.7071 ranks.** Neither is the customer count.

For a general distribution:

```text
μ = E[R] = Σ k·p[n,k]
Var(R) = Σ (k−μ)²·p[n,k] = E[R²]−μ²
SD(R) = sqrt(Var(R))
```

For large n the paper proves (**Theorem 3.B**, p. 195 / PDF 14), up to small periodic effects:

```text
SD(R) ≈ 1.12127 ranks
Var(R) ≈ 1.25725 ranks².
```

This does **not** mean 1.12 customers or 1.12% error. A displacement of 1.12 in R changes `2^R` by a factor of approximately **2.18**. That illustrates the single notebook's roughness; it is not an exact confidence interval.

If 64 sufficiently independent observers each measure R, their average A has:

```text
Var(A) ≈ Var(R)/64
SD(A) ≈ 1.12127/8 ≈ 0.14016 ranks.
```

Why square root? Independent variances add: the sum has variance `64σ²`; dividing the sum by 64 divides its variance by `64²`. Result: `σ²/64`. Taking a square root gives `σ/8`.

If observers reuse the same hash, their notebooks are identical: **no accuracy improvement**. Averaging requires genuinely different information.

### Convert rank wobble to count wobble

A small rank error d changes a count by `2^d ≈ 1 + ln(2)·d`. Thus:

```text
relative standard error ≈ ln(2) × 1.12127 / sqrt(m)
                        ≈ 0.78 / sqrt(m).
```

This is an intuitive first-order derivation; Theorems 4–5 justify the PCSA result despite bucket-allocation randomness.

For n=10,000 and m=64, SD of the estimate is about **975 customers**. “10% accuracy” means roughly this scale of dispersion, **not every run within ±10%**. For large m a near-normal approximation can suggest a rough ±2-SD interval; it is not a universal guarantee, especially for small n/m or small m.

Bias is different: the paper calls `E[estimate]/n` its **bias ratio**. Ideal is 1. A ratio of 1.0047 means average overestimation by 0.47%, even though individual results scatter much more widely. The usual additive bias is `E[estimate]−n`.

In trial reports we use sample variance (divide by trials−1) to estimate the underlying variance. Do not confuse **SD across count estimates** with **SD/sqrt(trials)**, the uncertainty of their sample mean. Also, RMSE² = variance + additive-bias²; standard error here is not RMSE.

## 7. Direct averaging → stochastic averaging → PCSA

### Plan A: 64 observers watch every receipt

Each observer has a different hash and its own bitmap. Each sees all n unique customers. Average the **first-zero ranks**:

```text
A = (R₀ + R₁ + … + Rₘ₋₁)/m
direct estimate = 2^A / φ.
```

Example ranks `[3,4,4,5]`: A=4, estimate=`16/φ≈20.69`.

Do not average `2^R/φ` arithmetically, and do not substitute a median. Averaging the ranks then exponentiating is equivalent to a **geometric mean** of their individual readouts. These operations give different answers.

The problem: 64 hashes and 64 notebook updates per receipt. Duplicate visits still cost processing even though they add no new statistical information.

### Plan B: route each customer to one virtual notebook

Hari keeps 64 notebooks but hashes each receipt only once. Some hash bits choose a notebook; the remaining bits determine the rank within it.

**Stochastic** means random-like. Here it refers to random-like **partitioning** of customers into notebooks. The average itself is an ordinary arithmetic average of R values.

Do not route by round-robin receipt number: a repeat customer could contaminate several notebooks. Do not route by physical checkout: one customer can use both checkouts. Route by the customer's stable hash.

With m=4, take a teaching hash `h=40`:

```text
h = 101000₂ = 40
    1010 | 00
    rest | bucket address

bucket = 40 mod 4 = 0
rest   = 40 div 4 = 10 = 1010₂
rho(rest) = 1
Set BITMAPS[0][1] = 1.
```

`mod` means remainder; `div` means integer division. This is ordinary `40 = 4×10 + 0`.

Using `rho(h)` instead would give 3 and accidentally reuse routing bits. Bucket 0 would always have those low bits zero, destroying the required rank distribution.

Power-of-two m makes the split especially simple: `log₂m` low bits select the notebook, and all other bits are independent of that address under the uniform model. Implementations here deliberately use powers of two.

### What PCSA stands for

**Probabilistic Counting with Stochastic Averaging.** One hash; one routed bitmap update; first zero per bitmap; average those R values.

Each notebook gets about n/m distinct customers, so `2^A/φ` estimates **customers per notebook**. Multiply by m to recover the store total:

```text
PCSA estimate = (m/φ) × 2^A
```

For the same example ranks `[3,4,4,5]`, PCSA says `4×16/φ≈82.74`. Direct averaging said 20.69 because every direct observer saw the **whole** population.

Actual notebook populations need not be identical. For a particular notebook:

```text
N_bucket ~ Binomial(n, 1/m)
E[N_bucket] = n/m
Var(N_bucket) = n(1/m)(1−1/m).
```

At n=6,400, m=64, a notebook expects 100 unique customers with SD≈9.92. No rebalancing is required. Lemma 5 proves sufficiently strong concentration for fixed m as n grows. The counts across notebooks are not exactly independent: their sum is n. The proof handles this instead of assuming perfect equal loads.

### Memory versus accuracy

Table II (p. 197 / PDF 16), for the raw PCSA estimator in its large-load regime:

| m | Bias ratio | Standard error | Packed 32-bit bitmap payload |
|---:|---:|---:|---:|
| 2 | 1.1662 | 61.0% | 8 B |
| 4 | 1.0792 | 40.9% | 16 B |
| 8 | 1.0386 | 28.2% | 32 B |
| 16 | 1.0191 | 19.6% | 64 B |
| 32 | 1.0095 | 13.8% | 128 B |
| 64 | 1.0047 | 9.7% | 256 B |
| 128 | 1.0023 | 6.8% | 512 B |
| 256 | 1.0011 | 4.8% | 1 KiB |
| 512 | 1.0005 | 3.4% | 2 KiB |
| 1024 | 1.0003 | 2.4% | 4 KiB |

Four times the memory buys about half the standard error. For target ε, the approximation suggests `m≈(0.78/ε)²`. Python lists and JavaScript arrays are educational representations and use much more space than packed bits.

## 8. Where does 0.77351 actually come from?

### First: what it corrects

The first missing rank is systematically displaced from log₂n. The paper proves:

```text
E[R] = log₂n + log₂φ + P(log₂n) + o(1)
     ≈ log₂n − 0.3704964.
```

`o(1)` means a term that vanishes as n grows. `P` is a tiny periodic ripple, discussed below. φ is **not** the probability of a trailing-zero pattern, nor a universal “hash correction.”

For Hari, the rank ruler reads approximately 0.3705 divisions too low on average. Calibrate that ruler:

```text
2^(log₂n + log₂φ) = φn
divide by φ to recover the correct scale.
```

### A numerical way to understand its origin

1. Compute `q[n,k]` from the distribution.
2. Compute `E[R] = q[n,1] + q[n,2] + …`.
3. Subtract `log₂n`.
4. Exponentiate: `2^(E[R]−log₂n)` approaches values very close to φ.

Why does the tail sum give the average? A result R=3 contributes one each to “R≥1,” “R≥2,” and “R≥3”: exactly three contributions.

There is a subtlety: the tiny periodic ripple survives, so **there is not a single exact ordinary limit for all integer n** after simply subtracting log₂n. The constant is the non-oscillating part. Averaging over the fractional part of log₂n removes that ripple. Simulations support this calibration; the paper proves it analytically.

### The actual product from Theorem 3.A

On **p. 193 / PDF 12**, the paper gives:

```text
φ = (e^γ / sqrt(2)) × (2/3)
    × product over j=1,2,… of
      [ ((4j+1)(4j+2)) / ((4j)(4j+3)) ]^((-1)^popcount(j)).
```

* γ≈0.5772156649 is Euler's constant, not a fitted dataset parameter.
* `product` means multiply all the factors.
* An even number of 1-bits gives exponent +1: multiply by that factor.
* An odd number gives exponent −1: divide by that factor.

The first factors are:

```text
j=1, binary 1:   divide by 30/28
j=2, binary 10:  divide by 90/88
j=3, binary 11:  multiply by 182/180
```

Evaluating progressively:

| Product terms | Approximate φ |
|---:|---:|
| 1 | 0.783631884 |
| 2 | 0.766217842 |
| 4 | 0.769667770 |
| 16 | 0.773161124 |
| 100 | 0.773506706 |
| 1,000 | 0.773516388 |
| 10,000 | 0.773516290 |

This is a deterministic numerical computation of a derived constant, **not fitting the grocery dataset**. Lab 5 and `fm_math.py` evaluate it live using logarithms for numerical stability. The familiar `0.77351` is the paper's shortened value.

### How did the authors get that product? The bridge, without complex calculus

1. Inclusion–exclusion gives the exact distribution.
2. Its smooth approximation gives the expected rank as a sum over scales `n/2, n/4, n/8, …`.
3. A **Mellin transform** reorganises a function according to multiplicative scales. It is useful because all our scales differ by factors of two.
4. The transform contains a function `N(s)=Σ (-1)^popcount(j)/j^s`, initially defined where it converges, then extended analytically.
5. The main term extracted by their inverse-transform/residue calculation is:

   `log₂n + (γ + N′(0))/ln(2) − 1/2`.

6. Consequently `ln φ = γ + N′(0) − ln(2)/2`.
7. Grouping the terms of N four at a time (Lemma 3) gives:

   `N′(0) = ln(2/3) + Σ (-1)^popcount(j) ln[((4j+1)(4j+2))/((4j)(4j+3))]`.

8. Exponentiating converts that sum of logarithms to the product above.

That is the chain from the probability model to the number. The advanced mathematics establishes the approximation and controls errors; a simulation alone cannot prove the constant.

### The critical “average before exponentiating” trap

In general:

```text
2^(E[R]) ≠ E[2^R].
```

For two equally likely notebook readings R=2 and R=4:

```text
2^(average R) = 2^3 = 8
average(2^R) = (4+16)/2 = 10.
```

So `E[R]≈log₂(φn)` does **not** prove that `2^R/φ` is an unbiased count estimator. The examples `10.502, 100.4997, 1000.502` on p. 196 refer to **`2^(E[R])/φ`**, not the expected value of a single notebook's exponentiated readout.

Averaging many R values reduces the spread before exponentiation. PCSA still has a residual bias ratio approximately `1+0.31/m`. Section 4 suggests:

```text
bias-adjusted estimate = raw PCSA estimate / (1+0.31/m).
```

It is a useful asymptotic approximation, not a correction for all small populations. The intuition for its scale is exponential curvature: about `((ln 2)² Var(R))/(2m)≈0.302/m`, close to the paper's practical rounded coefficient 0.31.

## 9. The two checkouts: merge sketches, not estimates

Checkout A and checkout B have separate receipt logs. C00001 may appear in both.

Both checkouts must use the **same customer encoding, hash, seed, m and bitmap dimensions**. They each construct a PCSA sketch. Hari combines corresponding bits with OR:

```text
Checkout A:  1 0 1 0
Checkout B:  0 1 1 0
Union:       1 1 1 0
```

This produces **exactly the same sketch** as processing the combined logs centrally, even with overlap. That is why merging causes no additional estimation error. It does not make the estimate itself exact.

Do not add the two count estimates: shared customers get counted twice. Do not average their R values to merge: each processor holds pieces of the same notebooks, not independent replicas of the whole store.

The paper describes O(s) messages for s processors, each carrying a sketch. Actual communication volume is O(s·m·L) bits before compression. Its ideal speedup assumes balanced work and small communication overhead; real hardware may be less ideal.

## 10. Deletions and scrolling: two easily missed ideas

### Deletions need counters, not just bits

Suppose C00001 and C00002 both mark box 0. Deleting C00001's receipt must not clear box 0 if C00002 still exists. Even a repeat receipt from C00001 may remain.

Replace each bit with the **number of currently present record occurrences** mapped to that cell:

```text
insert receipt: cell_count += 1
delete that receipt: cell_count -= 1
bitmap cell is marked exactly when cell_count > 0
```

Duplicate occurrences must also increment these counters, so removing one copy leaves the others represented. With a valid stream of insertions/deletions, the positive cells match the bitmap of the remaining multiset. The memory cost now depends on occurrence counts, and counters can overflow. A lossy sketch cannot check whether a requested deletion is legitimate; the application must provide valid deletions.

The paper proposes this on **p. 205 / PDF 24**. Lab 6 demonstrates why a single Boolean is insufficient.

### Scrolling compresses the bitmap's predictable parts

Low ranks are almost all ones, very high ranks almost all zeros, and information clusters in a narrow fringe. The paper suggests storing a common boundary plus the mixed fringe rather than all the redundant cells.

In its example the first four columns are all ones; a five-column fringe stores rows `10100`, `11000`, `01011`, `11010`; everything beyond is zero. Lab 6 reconstructs this exact matrix from its boundary and fringe.

The suggested practical eight-bit window reduces memory/communication, but **discarding out-of-window rare bits without a policy is not automatically lossless**. Such bits may matter later when gaps fill. A robust implementation needs appropriate overflow handling/window management. This compression is not a sliding time window: it scrolls **rank positions**, not yesterday's receipts.

## 11. Limitations and implementation traps

| Limitation | What happens at Hari's Grocery? | Practical implication |
|---|---|---|
| Approximation | One lucky hash assignment changes the answer | Evaluate many seeds; no per-run ±10% guarantee |
| Small n/m | Most virtual notebooks are empty | Raw formula has a floor: even with no customers it returns m/φ |
| Empty stream | m=64 gives a raw result ≈82.74 for n=0 | Implementations explicitly return 0 for known-empty streams; this does not fix n=1… |
| Startup nonlinearity | Twelve customers with 64 notebooks look absurd | Paper says asymptotics are close once n/m exceeds roughly 10–20; it suggests exact-distribution corrections but supplies no complete small-range algorithm |
| Residual bias | Average estimate is slightly high | Optional `1+0.31/m` correction; it does not eliminate variance |
| Bad hash | If every ticket is even, box 0 never fills | Uniform-looking low bits and sufficient independence are essential |
| Duplicate consistency | Changing seed on each receipt gives repeat visitors new identities | Freeze hash/encoding/seed for a sketch and all its merge partners |
| Finite hash space | Distinct customer IDs can have identical whole hashes | At high occupancy, estimates increasingly describe distinct hashes; use adequate hash width |
| Short bitmap | The first missing rank lies beyond stored cells | Detect saturation; never silently report the last index as a found zero |
| Zero hash/remainder | There is no 1-bit to find | Define rho(0)=remaining width; guard out-of-range array access; do not loop forever or clamp into the last cell |
| Routing consumes bits | 64 notebooks consume 6 hash bits | A 64-bit hash leaves 58 for rank measurement; bitmap width and total hash width are different quantities |
| Too many notebooks | Better large-n variance but smaller n/m | Accuracy does not improve monotonically at fixed tiny n |
| Expensive direct averaging | m hashes per receipt | PCSA uses one hash and one update, then O(mL) straightforward readout |
| ID semantics | One human uses two loyalty accounts | Counts distinct encoded IDs, not automatically distinct humans |
| Basic sketch cannot delete | A bit doesn't say who or how many set it | Use occurrence counters if deletions are required |
| No membership/listing | A box shared by many customers is not an ID | Cannot recover customer names or answer “did C00001 visit?” reliably |
| No direct intersection | A AND B bitmaps can match through different customers | OR supports union; AND is not set intersection. Inclusion–exclusion of estimated counts can be noisy, especially for small overlaps |
| No intrinsic time decay | Yesterday's bits remain | Time-windowed counting needs additional organisation, such as mergeable time buckets |
| Merge compatibility | Different seeds/m values mean different virtual notebooks | Validate compatibility before bitwise OR |
| Real memory/cost | Lists have object overhead; hashing reads the key | Packed mL bits is a payload claim; “O(1) update” treats key hashing/word operations appropriately |

**Bitmap sizing from Section 4:** choose `L > log₂(n/m) + 4` for the rank bitmap. This is a probabilistic sizing guideline, not a hard maximum-count guarantee. The paper quotes a truncation-error bound below `5×10⁻³` under its assumptions. Its infinite-hash analysis and finite-word pseudocode need careful reconciliation: allocate enough **hash bits for address + rank**, not just enough bitmap storage.

A full hash collision differs from two customers hitting the same rank. The latter is the mechanism the analysis intentionally uses. Birthday collisions can begin long before the hash space is mostly full; their mere existence does not instantly make the cardinality estimate unusable.

Python uses SHA-256 truncated to 64 bits. The offline browser uses a seeded 32-bit teaching hash for receipt traces, and a seeded pseudorandom uniform-word model for repeated statistical trials. Those are explicitly labelled; their outputs need not match each other. None proves that a real hash meets the ideal infinite-independent-bit assumption. The bad-hash experiment deliberately violates it.

## 12. Map of the whole paper: what else was in it?

| Paper material | Grocery translation / where covered |
|---|---|
| Introduction, pp. 182–184 | Database query optimisers choose plans partly from distinct counts. Exact sorting/sets cost space and I/O. Hari's exact customer set is our baseline, not the scalable sketch. Naively sampling receipts can overrepresent regular visitors. |
| Morris comparison, p. 184 | Morris counts events, with roughly log₂log₂n bits; duplicate-insensitive distinct counting is a different problem. |
| COUNT, pp. 184–185 | Ticket rho → exact-rank bitmap → first zero; sections 1–4. |
| Probability model and Theorem 1, pp. 186–188 | Independent fair bits for distinct IDs, p vs q, inclusion–exclusion; section 5. The noncommutative polynomials enumerate ordered sequences of customers' rank categories, then remove sequences missing a required category. |
| Theorem 2, pp. 188–190 | Exponential approximation, ψ product, sharp tails; section 5 and Lab 4. |
| Table I, p. 191 | Numerical comparisons of distributions; recompute rather than inherit the notation/index inconsistencies described above. |
| Lemmas 1–3, pp. 190–193 | Convert the distribution into moments, use scale-based Mellin analysis, group N(s) terms to control convergence; section 8. |
| Theorems 3.A–3.B, pp. 193–195 | Mean-rank calibration φ, SD≈1.12127, periodic fluctuations; sections 6 and 8. |
| Direct averaging and PCSA, pp. 195–197 | Every observer sees everyone vs one stable notebook per customer; section 7. |
| Theorem 4, pp. 198–201 | Computes the first and second moments of the PCSA count estimate, not just R. These determine bias and variance. |
| Lemma 4, pp. 199–200 | Studies `E[β^R]`, β=2^(1/q), because count estimates exponentiate averaged ranks. This avoids the invalid shortcut `E[2^R]=2^E[R]`. |
| Lemma 5, pp. 200–201 | Random notebook populations concentrate around n/m. The multinomial sum averages over all population splits; asymptotically the nearly equal splits dominate. |
| Theorem 5 and expansions, pp. 198, 201–202 | Convert the moments into bias≈1+0.31/m and SE≈0.78/√m; errors are not uniform in m. You cannot increase m indefinitely at fixed n and still claim large-load accuracy. |
| Implementation, pp. 202–203 | Hash choice, L, m, bias and startup corrections; section 11. The historical multiplicative hash example is not a general modern recommendation. |
| Tables III–IV, pp. 204–205 | Real Unix manual lines and five-character blocks, exact cardinalities, varying m and hash constants; empirical checks against theory. Our store data replaces the domain, not the methodology. The paper aggregates 160 simulations; one run is not a variance measurement. |
| Distributed counting, pp. 204–205 | OR checkout sketches, including overlapping customer populations; section 9 and Lab 6. |
| Scrolling and deletions, p. 205 | Compress the fringe; replace bits with occurrence counters; section 10 and Lab 6. |
| Conclusion, p. 206 | Alternative statistics: maximum occupied rank is noisier; minimum hash gives another estimator. Storage/accuracy tradeoffs motivated later work. The 1985 VAX timing is historical, not a current benchmark. |
| Appendix, pp. 206–208 | Bounds the tiny periodic terms using Fourier coefficients, the fast decay of the Gamma function along imaginary directions, and bounds for N(s). |
| Note added in proof, p. 209 | The sign sequence `(-1)^popcount(j)` is the Thue–Morse (Morse–Thue) sequence. A related infinite-product identity is noted; it is not an extra runtime step in PCSA. |

### Why the tiny periodic ripple exists

The bitmap measures integer ranks, a binary ruler. Doubling n shifts the distribution by about one rank and leaves the fractional part of log₂n unchanged. A tiny discretisation effect therefore repeats with **period one in log₂n**, rather than dying away completely. Theorem 3.A bounds its amplitude by `10⁻⁵` rank units. The appendix proves such fluctuations are negligible for practical counting; they are not random hash noise and not the 10% standard error.

No calculus is needed to operate the algorithm, but these proof steps explain why its constants and error claims are justified rather than guessed.

## 13. Guided experiments: predict first, then reveal

1. **Lab 1, receipt stream:** step through a repeat customer. Predict whether its box or R changes. Then finish 20 receipts and compare 20 receipts, 12 IDs, and the estimate.
2. **Lab 1, rank gap:** select the hand-picked ranks. Before adding rank 12, predict R and M. Reverse the display. Neither statistic should change just because the view reverses.
3. **Lab 2, PCSA:** trace `40 mod 4` and `40 div 4`. Generate the promotion day. Compare direct-averaging work with PCSA work; inspect actual per-bucket populations.
4. **Lab 3, repeated trials:** keep n fixed and compare m=16,64,256. Roughly halve SD each time m quadruples. Then try n=12,m=64: the startup bias dominates.
5. **Lab 4, probability:** use n=2. Reproduce p=[1/4,1/2,1/4]. Change to n=100 and compare exact versus approximate distributions, then sampled frequencies.
6. **Lab 5, φ:** increase product terms. Notice the value settles near 0.77351629 without any customer data. Compare average-then-exponentiate with exponentiate-then-average.
7. **Lab 6:** merge two overlapping checkout logs; replay duplicates; remove one of two receipts sharing a cell; reconstruct the paper's scrolling example.

### Check your understanding

* Observed ranks `{0,1,4}`: what are R and M? **R=2, M=4.**
* If the bitmap is drawn backwards, does the count change? **No; scan increasing rank.**
* Does PCSA randomly route every visit anew? **No; same customer, same hash, same notebook.**
* Why multiply by m in PCSA? **Each notebook saw about n/m customers.**
* Why not multiply by m in direct averaging? **Every observer saw all n customers.**
* Does φ make one bitmap unbiased in count space? **No; it calibrates the mean rank in log space.**
* Does 9.7% standard error guarantee this run within 9.7%? **No.**
* Can I make m enormous to count twelve customers perfectly? **No; the raw estimator's small-load behaviour gets worse.**

**Mental model to keep:** a bitmap records which rarity levels have appeared; its first missing level is a noisy logarithmic ruler. PCSA cheaply creates many such rulers by stable random partitioning, averages their readings, and calibrates the result.
