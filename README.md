# System-Design-Playground

List of works and other experimental stuffs on system design. 

## Flajolet–Martin and PCSA

- [Story-based lesson: one grocery store](HyperLogLog/07-fm-pcsa-story.md)
- [Offline interactive laboratory](HyperLogLog/08-fm-pcsa-playground.html) — open the HTML file locally in a browser.
- [First-empty-position learning aid](HyperLogLog/09-fm-pcsa-first-zero.html) — bitmap scan, the first `0`, and why `2^R` becomes the estimate.
- [LogLog learning aid](HyperLogLog/playground/loglog-playground.html) — geometric mean, `α ≈ 0.39701`, one bucket per item.
- [HyperLogLog learning aid](HyperLogLog/playground/hyperloglog-playground.html) — harmonic mean, `α_m`, linear counting.
- [FM vs LogLog vs HyperLogLog — comparative study](HyperLogLog/playground/comparison-fm-loglog-hll.html) — all three side by side, error and performance.
- [Single-bitmap COUNT](HyperLogLog/scripts/01-fm-bitmap.py) and [direct averaging + PCSA](HyperLogLog/scripts/02-fm_pcsa.py)
- [Synthetic receipt data](HyperLogLog/data/grocery-visits.csv) and [reproducible probability/constant calculations](HyperLogLog/fm_math.py)
