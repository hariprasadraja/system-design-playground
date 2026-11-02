/* Offline FM/PCSA teaching lab. Ranks are zero-based throughout. */
"use strict";

(() => {
  const PHI = 0.773516290951;
  const GAMMA = 0.5772156649015329;
  const encoder = new TextEncoder();

  function popcount(value) {
    let count = 0;
    while (value) { value &= value - 1; count++; }
    return count;
  }

  function rho(value, width = 32) {
    value >>>= 0;
    if (!value) return width; // No set bit: outside the representable ranks.
    return 31 - Math.clz32((value & -value) >>> 0);
  }

  function firstZero(mask, width = 24) {
    for (let rank = 0; rank < width; rank++) {
      if (((mask >>> rank) & 1) === 0) return rank;
    }
    return width; // Saturation sentinel, not the last valid index.
  }

  function mark(mask, rank, width) {
    return rank < width ? (mask | (1 << rank)) >>> 0 : mask;
  }

  // MurmurHash3 x86_32 for reproducible teaching traces, not a hash proof.
  function hash32(text, seed = 0) {
    const bytes = encoder.encode(text);
    let hash = seed >>> 0;
    let i = 0;
    const mix = k => {
      k = Math.imul(k, 0xcc9e2d51);
      k = (k << 15) | (k >>> 17);
      return Math.imul(k, 0x1b873593);
    };
    while (i + 4 <= bytes.length) {
      let k = bytes[i] | (bytes[i + 1] << 8) | (bytes[i + 2] << 16) | (bytes[i + 3] << 24);
      hash ^= mix(k);
      hash = (hash << 13) | (hash >>> 19);
      hash = (Math.imul(hash, 5) + 0xe6546b64) | 0;
      i += 4;
    }
    let tail = 0;
    for (let j = 0; i + j < bytes.length; j++) tail |= bytes[i + j] << (8 * j);
    if (i < bytes.length) hash ^= mix(tail);
    hash ^= bytes.length;
    hash ^= hash >>> 16;
    hash = Math.imul(hash, 0x85ebca6b);
    hash ^= hash >>> 13;
    hash = Math.imul(hash, 0xc2b2ae35);
    hash ^= hash >>> 16;
    return hash >>> 0;
  }

  function randomWords(seed) {
    let state = seed >>> 0;
    return () => {
      state = (state + 0x6d2b79f5) >>> 0;
      let t = Math.imul(state ^ (state >>> 15), state | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return (t ^ (t >>> 14)) >>> 0;
    };
  }

  function splitHash(hash, m) {
    const rest = Math.floor(hash / m);
    return {bucket: hash % m, rest, rank: rho(rest, 32 - Math.log2(m))};
  }

  function addHash(masks, hash, width) {
    const ticket = splitHash(hash, masks.length);
    masks[ticket.bucket] = mark(masks[ticket.bucket], ticket.rank, width);
    return ticket;
  }

  function readout(masks, width, scale = masks.length) {
    const ranks = Array.from(masks, mask => firstZero(mask, width));
    const mean = ranks.reduce((sum, r) => sum + r, 0) / ranks.length;
    const saturated = ranks.some(r => r === width);
    return {ranks, mean, saturated, estimate: saturated ? NaN : scale * 2 ** mean / PHI};
  }

  const qCache = new Map();
  function qExact(n, k) {
    if (k === 0) return 1;
    if (k > n) return 0;
    if (k < 0 || k > 20 || n < 0) throw new Error("Teaching formula supports 0 ≤ k ≤ 20 and n ≥ 0.");
    const key = `${n}/${k}`;
    if (qCache.has(key)) return qCache.get(key);
    const denominator = 2 ** k;
    let sum = 0, compensation = 0;
    // Kahan summation reduces roundoff in the alternating sum.
    for (let j = 0; j < denominator; j++) {
      const term = (popcount(j) % 2 ? -1 : 1) * ((denominator - j) / denominator) ** n;
      const adjusted = term - compensation;
      const next = sum + adjusted;
      compensation = (next - sum) - adjusted;
      sum = next;
    }
    const result = Math.min(1, Math.max(0, sum));
    qCache.set(key, result);
    return result;
  }

  function psi(x) {
    if (x <= 0) return 0;
    let product = 1;
    while (x < 40) { product *= -Math.expm1(-x); x *= 2; }
    return product;
  }

  function phiProduct(terms) {
    let logPhi = GAMMA - Math.log(2) / 2 + Math.log(2 / 3);
    for (let j = 1; j <= terms; j++) {
      logPhi += (popcount(j) % 2 ? -1 : 1) * Math.log1p(2 / (4 * j * (4 * j + 3)));
    }
    return Math.exp(logPhi);
  }

  function moments(values) {
    const mean = values.reduce((sum, x) => sum + x, 0) / values.length;
    const variance = values.length > 1
      ? values.reduce((sum, x) => sum + (x - mean) ** 2, 0) / (values.length - 1) : 0;
    return {mean, variance, sd: Math.sqrt(variance)};
  }

  function trial(n, m, random) {
    const masks = new Uint32Array(m);
    let single = 0, maximum = -1;
    for (let i = 0; i < n; i++) {
      const h = random();
      const rank = rho(h);
      single = mark(single, rank, 24);
      maximum = Math.max(maximum, rank);
      addHash(masks, h, 24);
    }
    return {R: firstZero(single, 24), M: maximum, ...readout(masks, 24)};
  }

  const ids = [1, 2, 1, 3, 4, 2, 5, 6, 3, 7, 8, 1, 9, 10, 4, 11, 12, 12, 2, 7];
  // Keep the physical checkout assignment aligned with data/grocery-visits.csv.
  const storeVisits = ids.map((id, i) => ({
    id: `C${String(id).padStart(5, "0")}`, receipt: `R${String(i + 1).padStart(3, "0")}`,
    checkout: ["A", "B", "A", "A", "B", "B", "A", "B", "A", "B", "A", "B", "A", "B", "A", "B", "A", "B", "A", "B"][i]
  }));

  const api = {PHI, popcount, rho, firstZero, mark, hash32, randomWords, splitHash,
    addHash, readout, qExact, psi, phiProduct, moments, trial, storeVisits};
  if (typeof module !== "undefined") module.exports = api;
  if (typeof document === "undefined") return;
  window.FMLab = api;

  const $ = id => document.getElementById(id);
  const format = (n, digits = 2) => Number.isFinite(n)
    ? n.toLocaleString("en-US", {maximumFractionDigits: digits}) : "saturated";
  const percent = n => `${(100 * n).toFixed(2)}%`;
  const frame = () => new Promise(resolve => requestAnimationFrame(resolve));
  function number(id) {
    const input = $(id);
    if (!input.checkValidity() || input.value === "" || !Number.isInteger(Number(input.value))) {
      input.reportValidity();
      throw new Error(`Enter a valid whole number for ${input.labels?.[0]?.textContent || id}.`);
    }
    return Number(input.value);
  }
  function on(id, action, event = "click") {
    $(id).addEventListener(event, async () => {
      const section = $(id).closest("section");
      section.querySelector(".input-error")?.remove();
      try { await action(); }
      catch (error) {
        const message = document.createElement("p");
        message.className = "note warning input-error";
        message.setAttribute("role", "alert");
        message.textContent = error.message;
        section.append(message);
      }
    });
  }
  function metrics(id, entries) {
    $(id).innerHTML = entries.map(([label, value]) =>
      `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`).join("");
  }
  function drawBitmap(id, mask, width, reverse = false, maximum = -1) {
    const R = firstZero(mask, width);
    const ranks = Array.from({length: width}, (_, i) => i);
    if (reverse) ranks.reverse();
    $(id).innerHTML = ranks.map(rank => {
      const bit = (mask >>> rank) & 1;
      return `<div class="cell ${bit ? "set" : ""} ${rank === R ? "first" : ""} ${rank === maximum ? "last" : ""}" title="Rank ${rank}: ${bit ? "observed" : "missing"}${rank === R ? "; first missing rank" : ""}"><small>${rank}</small><b>${bit}</b></div>`;
    }).join("");
  }

  // Lab 1: step-by-step customer stream.
  let receipt;
  function resetReceipts() {
    const scenario = $("receiptScenario").value;
    const tickets = [3, 6, 8, 3, 4096, 4];
    const toyIDs = [1, 2, 3, 1, 4, 5];
    const visits = scenario === "gap" ? tickets.map((hash, i) => ({
      id: `C${String(toyIDs[i]).padStart(5, "0")}`, receipt: `T${i + 1}`, checkout: "A", hash
    })) : storeVisits;
    receipt = {scenario, seed: number("receiptSeed"), visits, cursor: 0, mask: 0, maximum: -1,
      seen: new Set(), rows: [], processed: 0, trace: "No receipts processed. The raw formula is 1/φ ≈ 1.29 even when empty; a practical empty-stream guard returns 0."};
    renderReceipts();
  }
  function stepReceipt(render = true) {
    if (receipt.cursor >= receipt.visits.length) return;
    const visit = receipt.visits[receipt.cursor++];
    let hash = visit.hash ?? hash32(visit.id, receipt.seed);
    if (receipt.scenario === "bad") hash = (hash & 0xfffffffe) >>> 0;
    const rank = rho(hash);
    const before = receipt.mask;
    const oldMax = receipt.maximum;
    const fresh = !receipt.seen.has(visit.id);
    receipt.seen.add(visit.id);
    receipt.processed++;
    receipt.mask = mark(before, rank, 16);
    receipt.maximum = Math.max(oldMax, rank);
    const R = firstZero(receipt.mask, 16);
    receipt.rows.push([visit.receipt, visit.id, visit.checkout, fresh ? "yes" : "repeat", rank, R, receipt.maximum]);
    receipt.trace = `${visit.receipt}: hash(${visit.id}) = ${hash}\nOrdinary binary (MSB → LSB): ${hash.toString(2).padStart(32, "0")}\nRead hash from right: ρ = ${rank}. ${rank < 16 ? `Mark box ${rank}.` : "Rank is outside this 16-cell display/storage; do not clamp it."}\nOld max code: max(${oldMax < 0 ? "no record" : oldMax}, ${rank}) = ${receipt.maximum}.\nBitmap: ${before === receipt.mask ? "unchanged" : "one new rank marked"}. First missing rank: ${firstZero(before, 16)} → ${R}.\n${fresh ? "New ID does not necessarily mean a new rank or a changed R." : "Repeated ID → same ticket → no new evidence."}`;
    if (render) renderReceipts();
  }
  function renderReceipts() {
    const R = firstZero(receipt.mask, 16);
    metrics("receiptMetrics", [["Receipts processed", receipt.processed], ["True unique customers", receipt.seen.size],
      ["First missing rank R", R], ["Maximum rank M", receipt.maximum < 0 ? "none" : receipt.maximum],
      ["2^R / φ (empty guarded)", receipt.seen.size ? format(R === 16 ? NaN : 2 ** R / PHI) : "0"]]);
    drawBitmap("receiptBitmap", receipt.mask, 16, $("reverseBits").checked, receipt.maximum);
    $("receiptTrace").textContent = receipt.trace;
    $("receiptRows").innerHTML = receipt.rows.map(row => `<tr>${row.map(v => `<td>${v}</td>`).join("")}</tr>`).join("");
    $("receiptStep").disabled = $("receiptFinish").disabled = receipt.cursor === receipt.visits.length;
    $("receiptReplay").disabled = receipt.cursor === 0;
  }
  on("receiptReset", resetReceipts);
  on("receiptScenario", resetReceipts, "change");
  on("receiptSeed", resetReceipts, "change");
  on("reverseBits", renderReceipts, "change");
  on("receiptStep", () => stepReceipt());
  on("receiptFinish", () => { while (receipt.cursor < receipt.visits.length) stepReceipt(false); renderReceipts(); });
  on("receiptReplay", () => {
    const before = receipt.mask;
    for (const visit of receipt.visits.slice(0, receipt.cursor)) {
      let hash = visit.hash ?? hash32(visit.id, receipt.seed);
      if (receipt.scenario === "bad") hash = (hash & 0xfffffffe) >>> 0;
      receipt.mask = mark(receipt.mask, rho(hash), 16);
      receipt.processed++;
    }
    receipt.trace = `Replayed ${receipt.cursor} already-processed receipts.\nBitmaps identical: ${before === receipt.mask}. Exact distinct count remains ${receipt.seen.size}.\nReceipt count grows, but the evidence does not. The table lists the original pass.`;
    renderReceipts();
  });

  // Lab 2: route a ticket, then construct a whole promotion-day sketch.
  function traceRoute() {
    const hash = number("routeHash"), m = number("routeMaps");
    const {bucket, rest, rank} = splitHash(hash, m);
    const bits = hash.toString(2).padStart(32, "0"), p = Math.log2(m);
    $("routeOutput").textContent = `hash = ${hash} = ${bits.slice(0, -p)} | ${bits.slice(-p)}\n                                      rest | address\nbucket = ${hash} mod ${m} = ${bucket}\nrest   = ${hash} div ${m} = ${rest}\nρ(rest) = ${rank} → mark notebook ${bucket}, rank ${rank}\nρ(full hash) = ${rho(hash)} would reuse the address bits!\n${rest === 0 ? "Zero remainder: rho returns remaining width; skip an out-of-range bitmap update." : "Same customer always has this same routing and rank."}`;
  }
  on("routeTrace", traceRoute);
  let day = null;
  function inspectDay() {
    if (!day) return;
    const bucket = number("inspectBucket");
    drawBitmap("dayBitmap", day.masks[bucket], day.L);
    const stats = readout(day.masks, day.L);
    $("dayCalculation").textContent = `Notebook ${bucket}: ${day.counts[bucket]} actual unique customers; R=${stats.ranks[bucket]}\nSum of all R values = ${stats.ranks.reduce((a, b) => a + b, 0)}\nA = sum(R) / ${day.m} = ${stats.mean.toFixed(6)}\nRaw estimate = ${day.m} / φ × 2^${stats.mean.toFixed(6)} = ${format(stats.estimate)}\nApproximate bias-adjusted = ${format(stats.estimate / (1 + 0.31 / day.m))}\n${stats.saturated ? "At least one bitmap is full: the first zero is beyond storage. Increase L; no valid readout is reported." : day.n === 0 ? "Raw formula is nonzero. A known-empty guard returns 0." : "R is the first missing rank, not the maximum occupied rank."}`;
  }
  on("inspectBucket", inspectDay, "change");
  on("dayRun", async () => {
    const n = number("dayN"), repeats = number("dayRepeats"), m = number("dayM"), L = number("dayL"), seed = number("daySeed");
    $("dayStatus").textContent = "Processing customer receipts…";
    $("dayRun").disabled = true;
    try {
      await frame();
      const masks = new Uint32Array(m), counts = new Uint32Array(m);
      for (let i = 0; i < n; i++) {
        const id = `C${String(i + 1).padStart(5, "0")}`;
        const ticket = addHash(masks, hash32(id, seed), L);
        counts[ticket.bucket]++;
      }
      for (let i = 0; n && i < repeats; i++) {
        addHash(masks, hash32(`C${String(i % Math.min(n, 20) + 1).padStart(5, "0")}`, seed), L);
      }
      day = {n, repeats: n ? repeats : 0, m, L, seed, masks, counts};
      const stats = readout(masks, L), total = n + day.repeats;
      metrics("dayMetrics", [["Receipts / unique IDs", `${format(total, 0)} / ${format(n, 0)}`], ["Raw PCSA readout", format(stats.estimate)],
        ["True mean IDs per bucket", format(n / m)], ["Packed bitmap payload", `${format(m * L / 8)} B`],
        ["PCSA hash/update calls", format(total, 0)], ["Direct hash/update calls", format(total * m, 0)]]);
      $("dayCaution").hidden = false;
      $("dayCaution").className = `note ${n / m < 20 || stats.saturated ? "warning" : ""}`;
      $("dayCaution").textContent = stats.saturated ? "Storage saturation: at least one bitmap has no zero. Raise L." : n / m < 20
        ? `Small-load regime: n/m=${format(n / m)}. The raw formula has a floor m/φ=${format(m / PHI)}. The 0.78/√m accuracy rule does not fix this startup bias.`
        : `Large-load guideline: standard error ≈ ${percent(0.78 / Math.sqrt(m))}. This is a distributional SD, not a bound on this run. L > log₂(n/m)+4 suggests L > ${(Math.log2(n / m) + 4).toFixed(2)}.`;
      $("inspectBucket").innerHTML = Array.from({length: m}, (_, i) => `<option>${i}</option>`).join("");
      $("dayBuckets").innerHTML = stats.ranks.map((R, i) => `<tr><td>${i}</td><td>${counts[i]}</td><td>${R}</td><td>${R === L ? "saturated" : format(2 ** R / PHI)}</td></tr>`).join("");
      $("dayStatus").textContent = `Completed promotion day with seed ${seed}. Repeats change neither the bucket nor its rank evidence.`;
      $("directRun").disabled = false;
      $("directOutput").textContent = "Run direct averaging to compare this processed customer set. Each observer sees every unique customer; no factor m in its estimate.";
      inspectDay();
    } finally { $("dayRun").disabled = false; }
  });
  on("directRun", async () => {
    if (!day) return;
    const data = day;
    $("directRun").disabled = $("dayRun").disabled = true;
    $("directOutput").textContent = "Computing independent-observer bitmaps…";
    try {
      await frame();
      const masks = new Uint32Array(data.m);
      // Duplicate receipts have identical effects; calculate on distinct IDs
      // for browser responsiveness and explicitly disclose this shortcut below.
      for (let i = 0; i < data.n; i++) {
        const id = `C${String(i + 1).padStart(5, "0")}`;
        for (let observer = 0; observer < data.m; observer++) {
          const rank = rho(hash32(`${observer}/${id}`, data.seed));
          masks[observer] = mark(masks[observer], rank, data.L);
        }
        if (i % 500 === 0) await frame();
      }
      const stats = readout(masks, data.L, 1);
      $("directOutput").textContent = `Direct averaging (seed ${data.seed}):\nR values = [${stats.ranks.join(", ")}]\nA = ${stats.mean.toFixed(6)}\n2^A / φ = ${format(stats.estimate)}; empty-guarded = ${data.n ? format(stats.estimate) : "0"}\nPCSA = ${format(readout(data.masks, data.L).estimate)}; actual unique IDs = ${data.n}\nFor responsiveness this comparison computes on unique IDs only; replaying repeat receipts gives the identical sketch.\nA streaming direct implementation would perform ${format((data.n + data.repeats) * data.m, 0)} hash/update calls vs PCSA's ${format(data.n + data.repeats, 0)}.`;
    } finally { $("directRun").disabled = $("dayRun").disabled = false; }
  });

  // Lab 3: repeated independent-looking hash assignments, fixed n per trial.
  let cancelTrials = false;
  on("trialCancel", () => { cancelTrials = true; });
  on("trialRun", async () => {
    const n = number("trialN"), m = number("trialM"), count = number("trialCount"), seed = number("trialSeed");
    const random = randomWords(seed), estimates = [], ranks = [], maxima = [];
    cancelTrials = false;
    $("trialRun").disabled = true;
    $("trialCancel").disabled = false;
    $("trialMetrics").innerHTML = $("trialRows").innerHTML = $("trialHistogram").innerHTML = "";
    let saturated = 0;
    try {
      for (let t = 0; t < count; t++) {
        if (cancelTrials) break;
        const result = trial(n, m, random);
        ranks.push(result.R); maxima.push(result.M);
        if (result.saturated) saturated++;
        estimates.push(result.estimate);
        if (t % 10 === 0) { $("trialStatus").textContent = `Running trial ${t + 1} / ${count}…`; await frame(); }
      }
      $("trialStatus").textContent = `${cancelTrials ? "Cancelled after" : "Completed"} ${estimates.length} trials · n=${n}, m=${m}, seed=${seed}. ${n / m < 20 ? "Small-load regime: expect startup bias." : "Compare sample results to large-load theory."}`;
      if (estimates.length < 2) return;
      if (saturated) { $("trialStatus").textContent += ` ${saturated} saturated trials; count statistics withheld rather than dropping failed trials.`; return; }
      const stats = moments(estimates), r = moments(ranks), maximum = moments(maxima);
      const correction = 1 + 0.31 / m;
      metrics("trialMetrics", [["Actual unique customers", format(n, 0)], ["Mean raw estimate", format(stats.mean)],
        ["Bias ratio: mean / n", (stats.mean / n).toFixed(4)], ["Measured standard error", percent(stats.sd / n)]]);
      const rows = [
        ["Variance of count estimates", `${format(stats.variance)} customers²`, "Average squared distance from sample mean (denominator trials−1)"],
        ["SD of count estimates", `${format(stats.sd)} customers`, `${format(n * 0.78 / Math.sqrt(m))} customers (approx.)`],
        ["SD / true n", percent(stats.sd / n), `${percent(0.78 / Math.sqrt(m))} (approx.)`],
        ["Raw bias ratio", (stats.mean / n).toFixed(5), `${correction.toFixed(5)} (approx.)`],
        ["Bias-adjusted mean / n", (stats.mean / correction / n).toFixed(5), "Near 1 at large load; not a small-population correction"],
        ["Bias-adjusted SD / n", percent(stats.sd / correction / n), "A scale correction rescales SD too"],
        ["Mean R, one bitmap", r.mean.toFixed(5), `${Math.log2(PHI * n).toFixed(5)} (large n, ignoring ripple)`],
        ["Variance of R, one bitmap", `${r.variance.toFixed(5)} ranks²`, "About 1.25725 at large n"],
        ["SD(R), one bitmap", `${r.sd.toFixed(5)} ranks`, "About 1.12127 at large n"],
        ["SD(M), maximum-rank alternative", `${maximum.sd.toFixed(5)} ranks`, "Compare its wider scatter with R, not with count-unit SD"]
      ];
      $("trialRows").innerHTML = rows.map(row => `<tr>${row.map(v => `<td>${v}</td>`).join("")}</tr>`).join("");
      const boundaries = [-Infinity, -0.4, -0.2, -0.1, 0, 0.1, 0.2, 0.4, Infinity];
      const labels = ["below −40%", "−40% to −20%", "−20% to −10%", "−10% to 0%", "0% to +10%", "+10% to +20%", "+20% to +40%", "+40% or higher"];
      const bins = Array(8).fill(0);
      for (const estimate of estimates) {
        const error = estimate / n - 1;
        const index = boundaries.findIndex((edge, i) => i > 0 && error < edge) - 1;
        bins[index < 0 ? 7 : index]++;
      }
      $("trialHistogram").innerHTML = `<table><thead><tr><th>Relative count error</th><th>Trials</th><th>Frequency</th></tr></thead><tbody>${bins.map((v, i) => `<tr><td>${labels[i]}</td><td>${v} (${percent(v / estimates.length)})</td><td><span class="bar" style="width:${200 * v / estimates.length}px" aria-hidden="true"></span></td></tr>`).join("")}</tbody></table>`;
    } finally { $("trialRun").disabled = false; $("trialCancel").disabled = true; }
  });

  // Lab 4: exact fixed-n distribution, asymptotic product and empirical samples.
  let distribution = null;
  function renderDistribution() {
    if (!distribution) return;
    const {n, probabilities, tails, sampled, sampleCount} = distribution;
    let mean = 0, second = 0;
    probabilities.forEach((p, k) => { mean += k * p; second += k * k * p; });
    metrics("probMetrics", [["Mean R (displayed mass)", mean.toFixed(6)], ["Variance R (displayed mass)", Math.max(0, second - mean ** 2).toFixed(6)],
      ["SD R (rank units)", Math.sqrt(Math.max(0, second - mean ** 2)).toFixed(6)], ["Omitted tail P(R≥20)", tails[20].toExponential(2)]]);
    const rows = probabilities.map((p, k) => {
      if (p < 0.000001 && k > 2 && !(sampled?.[k])) return "";
      const approx = psi(n / 2 ** k) - psi(n / 2 ** (k + 1));
      return `<tr><td>${k}</td><td>${tails[k].toFixed(8)}</td><td>${p.toFixed(8)}</td><td>${approx.toFixed(8)}</td><td>${sampled ? ((sampled[k] || 0) / sampleCount).toFixed(4) : "—"}</td><td><span class="bar" style="width:${220 * p}px" aria-hidden="true"></span></td></tr>`;
    });
    $("probRows").innerHTML = rows.join("");
  }
  async function calculateDistribution() {
    const n = number("probN");
    $("probRun").disabled = $("probSample").disabled = true;
    $("probStatus").textContent = "Evaluating inclusion–exclusion…";
    try {
      await frame();
      const tails = Array.from({length: 21}, (_, k) => qExact(n, k));
      const probabilities = tails.slice(0, -1).map((q, k) => Math.max(0, q - tails[k + 1]));
      distribution = {n, tails, probabilities, sampled: null, sampleCount: 0};
      renderDistribution();
      $("probStatus").textContent = `Calculated for n=${n}. Rows below probability 0.000001 are hidden; moments use all ranks 0–19 without renormalising. The residual tail is shown separately.`;
    } finally { $("probRun").disabled = $("probSample").disabled = false; }
  }
  on("probRun", calculateDistribution);
  on("probSample", async () => {
    if (!distribution || distribution.n !== number("probN")) await calculateDistribution();
    const data = distribution;
    $("probRun").disabled = $("probSample").disabled = true;
    try {
      const random = randomWords(2026);
      data.sampled = Array(33).fill(0); data.sampleCount = 1000;
      for (let t = 0; t < 1000; t++) {
        let mask = 0;
        for (let i = 0; i < data.n; i++) mask = mark(mask, rho(random()), 32);
        data.sampled[firstZero(mask, 32)]++;
        if (t % 50 === 0) { $("probStatus").textContent = `Sampling ${t + 1} / 1000 trials at n=${data.n}…`; await frame(); }
      }
      renderDistribution();
      $("probStatus").textContent = `Sampled 1,000 trials at n=${data.n}, generator seed 2026. Frequencies fluctuate around exact p; they need not match exactly.`;
    } finally { $("probRun").disabled = $("probSample").disabled = false; }
  });

  // Lab 5: deterministic evaluation, no dataset or fitted parameter.
  function calculatePhi() {
    const terms = number("phiTerms");
    const phi = phiProduct(terms);
    metrics("phiMetrics", [["Computed φ", phi.toFixed(12)], ["Implied mean-rank offset", Math.log2(phi).toFixed(8)], ["Correction 1/φ", (1 / phi).toFixed(8)]]);
    $("phiRows").innerHTML = `<table><thead><tr><th>Terms included</th><th>Partial product φ</th></tr></thead><tbody>${[1, 2, 4, 16, 100, 1000, 10000].filter(n => n <= terms).map(n => `<tr><td>${n}</td><td>${phiProduct(n).toFixed(12)}</td></tr>`).join("")}</tbody></table><p class="small">Finite partial products can oscillate. The complete product gives approximately 0.773516290951. The paper writes 0.77351.</p>`;
  }
  on("phiRun", calculatePhi);

  // Lab 6: merge, occurrence counters and exact fringe reconstruction.
  on("mergeRun", () => {
    const m = 4, width = 16, seed = 7;
    const left = new Uint32Array(m), right = new Uint32Array(m), central = new Uint32Array(m);
    const aIDs = new Set(), bIDs = new Set();
    for (const visit of storeVisits) {
      const h = hash32(visit.id, seed);
      addHash(central, h, width);
      addHash(visit.checkout === "A" ? left : right, h, width);
      (visit.checkout === "A" ? aIDs : bIDs).add(visit.id);
    }
    const merged = left.map((mask, i) => (mask | right[i]) >>> 0);
    const bits = mask => Array.from({length: width}, (_, r) => (mask >>> r) & 1).join("");
    $("mergeOutput").textContent = `m=4, L=16, seed=7. Rank 0 is on the left.\n${Array.from(merged, (mask, i) => `Bucket ${i}: A ${bits(left[i])} OR B ${bits(right[i])} = ${bits(mask)}`).join("\n")}\n\nMerged bitmap equals central bitmap: ${merged.every((mask, i) => mask === central[i])}\nExact unique customers: A=${aIDs.size}, B=${bIDs.size}, union=${new Set([...aIDs, ...bIDs]).size}\nAdding exact checkout counts gives ${aIDs.size + bIDs.size}, which double-counts overlaps.\nMerged estimate = central estimate = ${format(readout(merged, width).estimate)}.\nThis tiny dataset has n/m=3: same-sketch equivalence holds even when the count estimate has startup bias.`;
  });
  let occurrences = {a: 1, b: 1};
  function renderDeletion(message = "Both customers have rank 0.") {
    const total = occurrences.a + occurrences.b;
    $("deleteOutput").textContent = `A's active receipts: ${occurrences.a}\nB's active receipts: ${occurrences.b}\nRank-0 occurrence counter = ${total}\nCorrect bitmap[0] = ${total > 0 ? 1 : 0}\n\n${message}\nA Boolean alone cannot tell whether another receipt still contributes. Counters need more memory and valid deletions.`;
  }
  on("deleteAddA", () => { occurrences.a++; renderDeletion("Even duplicate A receipts increment the occurrence counter."); });
  on("deleteAddB", () => { occurrences.b++; renderDeletion(); });
  on("deleteRemoveA", () => {
    if (!occurrences.a) { renderDeletion("No active A receipt exists to delete. A real sketch cannot validate customer-level deletions by itself."); return; }
    occurrences.a--;
    renderDeletion(occurrences.a + occurrences.b > 0 ? "Deleting one A receipt does NOT clear the bit: another receipt remains." : "The last contributing receipt is gone: clear the bit.");
  });
  on("deleteRemoveB", () => {
    if (!occurrences.b) { renderDeletion("No active B receipt exists to delete."); return; }
    occurrences.b--;
    renderDeletion(occurrences.a + occurrences.b > 0 ? "Another receipt remains: keep the bit set." : "The last contributing receipt is gone: clear the bit.");
  });
  on("deleteReset", () => { occurrences = {a: 1, b: 1}; renderDeletion(); });
  on("scrollRun", () => {
    const fringe = ["10100", "11000", "01011", "11010"];
    const expanded = fringe.map(row => "1111" + row + "0000");
    $("scrollOutput").textContent = `Boundary = 4; fringe width = 5.\n${expanded.map(row => `${row.slice(0, 4)} | ${row.slice(4, 9)} | ${row.slice(9)}`).join("\n")}\nStore the common boundary and four fringe words.\nFirst missing ranks = [${expanded.map(row => row.indexOf("0")).join(", ")}].\nThe reconstructed matrix matches the paper's example. Its proposed practical window is 8 bits, not a proof that all possible fringes fit.`;
  });

  resetReceipts(); traceRoute(); calculatePhi(); renderDeletion();
  calculateDistribution().catch(error => { $("probStatus").textContent = error.message; });
})();
