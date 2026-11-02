# HyperLogLog — Intuition (for someone who already knows FM + LogLog)

> **One-sentence thesis:** HyperLogLog = LogLog's registers, unchanged,
> combined with a **harmonic mean instead of a geometric mean**.
> That single swap is 90% of the paper. Everything else is bias correction.

Run the companion experiment while reading: open `06-hyperloglog-playground.html`
(§4 holds the verified results of the removed `05-hyperloglog-intuition.py`)
Your working implementation is `04-hyperloglog.py`.

---

## 1. The lineage — what actually changed each time

| | FM (`02-fm-multi.py`) | LogLog (`03-loglog.py`) | HyperLogLog (`04-hyperloglog.py`) |
|---|---|---|---|
| Observation | max ρ over whole stream | max ρ **per bucket** | max ρ per bucket (identical) |
| Buckets | 1 (× many hashes, median) | m = 2^p, split hash bits | m = 2^p, split hash bits (identical) |
| Estimator | 2^maxρ / φ | α·m·2^{mean(R)} | α·m² / Σ 2^(−Rⱼ) |
| Mean used | — | **geometric** mean of 2^R | **harmonic** mean of 2^R |
| Std. error | huge / jumps by 2× | 1.30/√m | **1.04/√m** |

Read that table again: **the data structure did not change from LogLog to
HyperLogLog. Only the averaging function did.** So the only question you
need to answer to "master" HLL is: *why is harmonic averaging so much better?*

## 2. Intuition you already have (30-second recap)

Hash = fair coin flips. ρ = "flips until first heads", so:

```
P(ρ ≥ k) = 2^-(k-1)      ρ=5 needs 00001: probability 1/16
```

Seeing ρ = k is evidence ~2^k distinct items passed through, because you
had to "pay" ~2^k hashes to get that lucky once. FM takes the single
biggest ρ (noisy — one lucky hash doubles the answer). LogLog splits the
stream into m buckets (**stochastic averaging**: one hash gives you the
bucket bits *and* the ρ bits for free) and averages — variance drops.

## 3. THE core intuition: geometric mean trusts the luckiest bucket

Each bucket gives an estimate `xⱼ = 2^{Rⱼ}`. How do you combine m estimates?

- **LogLog:** geometric mean = `2^{mean(R)}`. In log-space it averages
  fairly, but exponentiating re-amplifies big values.
- **HyperLogLog:** harmonic mean = `m / Σ(1/xⱼ) = m / Σ 2^{-Rⱼ}`.
  A harmonic mean is **dominated by the smallest values**.

Worked example (Experiment 1 in the script — verify the numbers yourself):

```
registers R = [3,3,3,3,3,3,3,10]   seven buckets say "~8", one lucky bucket says "1024"
(shared α=0.635 for both, to isolate the mean alone — verified in Exp 1)
LogLog:      α · 8 · 2^{(3·7+10)/8}                          ≈ 74.6
HyperLogLog: α · 8² / (7·2^-3 + 2^-10)                       ≈ 46.4
             the outlier contributes 2^-10 = 0.001 to a sum of ≈ 0.876 — it vanishes.
             Inject R=25 instead: LogLog jumps to ≈273.6, HyperLogLog stays ≈46.5.
```

### The only table you need: `2^r` vs `2^-r`

`r` = register value = (leading zeros + 1). Probability of that exact
pattern `0...01` is `2^-r`. Read the table both ways:

| r | pattern | P(pattern) = 2^-r | 2^r ("this bucket saw ~") | 2^-r = contribution to HLL sum Σ2^-R |
|---|---|---|---|---|
| 0 | *(empty register)* | — | 1 | 1.0 |
| 1 | `1` | 0.5 | 2 | 0.5 |
| 2 | `01` | 0.25 | 4 | 0.25 |
| 3 | `001` | 0.125 | 8 | 0.125 |
| 4 | `0001` | 0.0625 | 16 | 0.0625 |
| 5 | `00001` | 0.03125 | 32 | 0.03125 |
| 6 | `000001` | 0.015625 | 64 | 0.015625 |
| 7 | `0000001` | 0.0078125 | 128 | 0.0078125 |
| 8 | 7 zeros + `1` | 0.00390625 | 256 | 0.00390625 |
| 9 | 8 zeros + `1` | 0.001953125 | 512 | 0.001953125 |
| 10 | 9 zeros + `1` | 0.0009765625 | 1,024 | 0.0009765625 |
| 15 | 14 zeros + `1` | 0.0000305 | 32,768 | 0.0000305 |
| 20 | 19 zeros + `1` | 0.00000095 | 1,048,576 | 0.00000095 |

Three rules the table makes obvious:

1. **+1 to `r` ⟹ `2^r` doubles, `2^-r` halves.** Log-scale register,
   exponential meaning — that's why counting to billions fits in 12 KB.
2. **LogLog reads the `2^r` column** (via `2^mean(R)`): the r=10 row
   screams "1024!" and drags the geometric mean up.
3. **HyperLogLog reads the `2^-r` column**: the r=10 row whispers 0.001
   into `Σ2^-R`, while an empty register (r=0) shouts 1.0. Small
   registers dominate the sum, so `n̂ = α·m²/Σ2^-R` stays calm.
   Worked: registers `[3,3,10]` → Σ = 0.125+0.125+0.001 = 0.251,
   i.e. the "1024" bucket is 0.4% of the evidence.

Why is "ignore the big ones" the *right* bias, not a hack?

1. A large Rⱼ is usually **luck, not signal** — ρ has a heavy geometric
   tail, so max-statistics are systematically jumpy (you learned this
   pain with FM's single max).
2. A small Rⱼ is **strong evidence**: if a bucket has seen thousands of
   items, its max ρ is almost surely large. A bucket still sitting at
   R=2 after the whole stream is proof its share of the stream was tiny.
   Harmonic mean listens to exactly those trustworthy witnesses.
3. Mathematically (the honest sketch of the proof): let `Z = Σ 2^{-Rⱼ}`.
   For n distinct items, each bucket gets ~n/m items, and one can show
   `E[2^{-Rⱼ}] ≈ (m/n)·c` — i.e. `2^{-R}` behaves like an (almost)
   **unbiased estimator of m/n**, whereas `2^{R}` has enormous variance.
   Averaging nearly-unbiased, low-variance terms `2^{-Rⱼ}` and inverting
   gives `n̂ ≈ α·m²/Z`. The constant αₘ (0.7213/(1+1.079/m) for large m)
   just removes the residual bias `c`, which comes from the discreteness
   of ρ (Flajolet's analysis uses Poissonisation + Mellin transforms —
   you do *not* need that machinery to use or reason about HLL).

Mnemonic: **FM/LogLog ask "how lucky did we get?" HLL asks "how unlucky
did we stay?"** Empty and low registers are the reliable signal.

## 4. The two corrections (know when each fires)

The raw harmonic estimator is biased at the extremes. `04-hyperloglog.py:106`:

1. **Small range — Linear Counting** (`raw ≤ 2.5m` and some register is 0):
   balls-into-bins says the fraction of empty registers `V/m ≈ e^{−n/m}`,
   so `n̂ = m·ln(m/V)`. Intuition: when n ≪ m, most information is in
   *which registers are still empty*, not in ρ values. This is what makes
   n=4 and n=250 accurate in the checks.
2. **Large range** (`raw > 2⁶⁴/30`): hashes start colliding in a 64-bit
   space; `−2⁶⁴·ln(1 − raw/2⁶⁴)` un-saturates the estimate. You will
   essentially never hit this with 64-bit hashes.

## 5. Cost, error, and the "log log" name

- **Error:** σ ≈ 1.04/√m. p=14 → m=16384 → **0.81%**, whether n is 10⁵ or 10⁹.
  Quadrupling m only halves error — that's the price schedule; choose p from it.
- **Memory:** a register only stores a max ρ ≤ 64−p, and ρ itself is about
  log₂(n/m) — so a register needs ~log₂log₂(n) bits: **the "LogLog" name**.
  5–6 bits/register in production (Redis: 12 KB total at p=14). Your
  bytearray uses 1 byte/register — same idea, unpacked.
- **Duplicates / order:** free. `max()` is idempotent and commutative
  (`04-hyperloglog.py:86`). Replay the stream 5×, registers don't move.
- **Merge:** elementwise `max()` = exact union of sketches
  (`04-hyperloglog.py:97`) — *this*, plus tiny size, is why HLL won in
  distributed systems (Redis `PFADD/PFCOUNT`, BigQuery, Kafka, Druid…).
  Same p + same hash seed are required, or the registers are incomparable.
- **Cannot do:** deletions, membership ("was x seen?"), intersections
  (only via inclusion–exclusion, badly), or listing items. It's a
  one-way, lossy summary — by design.

## 6. Mastery checklist + self-test

You have mastered HLL when you can answer these without looking:

1. Why doesn't one hash with ρ=40 destroy an HLL estimate, when it would
   destroy FM's? → Its contribution is 2⁻⁴⁰ ≈ 0 in the harmonic sum.
2. n doubles. Roughly what happens to a typical register? → Each bucket
   gets 2× items, so max ρ rises by ~1 (seeing one more leading zero
   needs ~2× the trials). Registers creep up logarithmically — hence
   counting to billions in 12 KB.
3. Why is linear counting *better* than the harmonic formula for n=100,
   m=16384? → Almost all registers are 0; ρ values carry ~no information,
   but the *count of empty bins* pins down n via `m·ln(m/V)`.
4. Two services use p=14 but different hash seeds. Can you merge? → No.
   Same item lands in different registers with different ρ; max() would
   fabricate cardinality. Rebuild with a shared hash.
5. You need 0.4% error. What m? → m ≈ (1.04/0.004)² ≈ 67,600 → p=17
   (m=131072, σ≈0.29%) or accept p=16 (0.41%).

**Exercises (do them, don't read about them):**
1. In `06-hyperloglog-playground.html` §3, change the injected outlier from
   R=25 to R=50. Predict *before running* whether each estimator moves.
2. Set p=4 (m=16) and run Experiment 3. Watch σ ≈ 26% — feel why nobody
   ships tiny m without bias tables (production HLL++ adds exactly that:
   empirical bias correction + sparse representation; same core idea).
3. Feed the sketch 1M copies of *one* item. Explain the estimate from the
   registers (how many are non-zero, and why linear counting nails it).

## 7. Where to go next

Flajolet et al. 2007, *"HyperLogLog: the analysis of a near-optimal
cardinality estimation algorithm"* — read §1–3 now; the Mellin-transform
§4 is optional. Then HyperLogLog++ (Heule et al. 2013) for the bias/sparse
fixes used in production.
