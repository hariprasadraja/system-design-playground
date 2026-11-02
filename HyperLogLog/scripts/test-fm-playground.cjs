// Run: node --test HyperLogLog/test-fm-playground.cjs
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fm = require("./fm-pcsa-playground.js");
const close = (a, b, tolerance = 1e-8) => assert.ok(Math.abs(a - b) < tolerance, `${a} != ${b}`);

test("exact two-customer distribution matches enumeration and paper calibration", () =>
{
  assert.deepEqual([0, 1, 2].map(k => fm.qExact(2, k) - fm.qExact(2, k + 1)), [0.25, 0.5, 0.25]);
  close(fm.qExact(100, 6) - fm.qExact(100, 7), 0.3475761195737535);
  close(fm.psi(100 / 64) - fm.psi(100 / 128), 0.34529782098481954);
  close(fm.phiProduct(10000), 0.773516290951);
});

test("routing consumes address bits; gaps survive a rare outlier", () =>
{
  assert.deepEqual(fm.splitHash(40, 4), { bucket: 0, rest: 10, rank: 1 });
  assert.equal(fm.firstZero((1 << 0) | (1 << 1) | (1 << 3) | (1 << 12), 16), 2);
  assert.equal(fm.rho(0, 26), 26);
  assert.equal(fm.mark(0, 16, 16), 0);
  assert.ok(fm.readout([15], 4).saturated);
  close(fm.readout([7, 15, 15, 31], 8).estimate, 64 / fm.PHI);
  close(fm.readout([7, 15, 15, 31], 8, 1).estimate, 16 / fm.PHI);
});

test("standard hash test vector and overlapping grocery checkout union", () =>
{
  assert.equal(fm.hash32("foo", 0), 0xf6a5c420);
  assert.equal(fm.storeVisits.length, 20);
  assert.equal(new Set(fm.storeVisits.map(x => x.id)).size, 12);
  const a = new Uint32Array(4), b = new Uint32Array(4), central = new Uint32Array(4);
  for (const row of fm.storeVisits)
  {
    const h = fm.hash32(row.id, 7);
    fm.addHash(row.checkout === "A" ? a : b, h, 16);
    fm.addHash(central, h, 16);
  }
  assert.deepEqual(a.map((mask, i) => (mask | b[i]) >>> 0), central);
  const replay = new Uint32Array(4);
  for (const row of [...fm.storeVisits, ...fm.storeVisits].reverse()) fm.addHash(replay, fm.hash32(row.id, 7), 16);
  assert.deepEqual(replay, central);
});

test("seeded large-load experiment agrees with rank SD and square-root error scaling", () =>
{
  const standardErrors = [];
  for (const m of [16, 64, 256])
  {
    const random = fm.randomWords(42);
    const trials = Array.from({ length: 600 }, () => fm.trial(6400, m, random));
    const stats = fm.moments(trials.map(t => t.estimate));
    const se = stats.sd / 6400;
    assert.ok(Math.abs(se - 0.78 / Math.sqrt(m)) < 0.025);
    assert.ok(Math.abs(fm.moments(trials.map(t => t.R)).sd - 1.12127) < 0.15);
    assert.ok(Math.abs(stats.mean / 6400 - 1) < 0.05);
    standardErrors.push(se);
  }
  assert.ok(standardErrors[0] > 1.5 * standardErrors[1]);
  assert.ok(standardErrors[1] > 1.5 * standardErrors[2]);
});
