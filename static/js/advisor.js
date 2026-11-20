const $ = (id) => document.getElementById(id);
const fmt = (n, d = 1) => Number(n).toLocaleString(undefined, { maximumFractionDigits: d });
let data = null;

// The server may briefly answer with an HTML error page (for example while
// it restarts); turn that into a readable message instead of a JSON error
async function readJson(res) {
  try {
    return await res.json();
  } catch {
    throw new Error("The server is busy or restarting – please try again in a few seconds.");
  }
}
let selected = 0;

$("explain").addEventListener("click", async () => {
  $("explain").disabled = true;
  $("explain").textContent = "Writing explanation…";
  $("explain-error").classList.add("hidden");
  $("explanation").classList.add("hidden");
  try {
    const res = await fetch("/api/explain", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result: data, crop_index: selected, language: $("language").value }),
    });
    const json = await readJson(res);
    if (!res.ok) throw new Error(json.error || "Request failed");
    const source = json.offline
      ? "Summary written by the app (AI service unavailable, offline mode)"
      : `Explained by AI (${json.provider})`;
    $("explanation").textContent = `${json.explanation}\n\n— ${source}. Check doses with your local agriculture officer.`;
    $("explanation").classList.remove("hidden");
  } catch (err) {
    $("explain-error").textContent = err.message;
    $("explain-error").classList.remove("hidden");
  } finally {
    $("explain").disabled = false;
    $("explain").textContent = "Explain my report";
  }
});

document.querySelectorAll(".demo").forEach((b) => b.addEventListener("click", () => {
  const d = b.dataset;
  $("N").value = d.n; $("P").value = d.p; $("K").value = d.k; $("ph").value = d.ph;
  $("district").value = d.district; $("lat").value = ""; $("lon").value = "";
  $("planting_date").value = d.date; $("irrigated").checked = true;
  $("form").requestSubmit();
}));

$("gps").addEventListener("click", () => {
  if (!navigator.geolocation) return showError("GPS not supported in this browser");
  navigator.geolocation.getCurrentPosition(
    (pos) => { $("lat").value = pos.coords.latitude.toFixed(4); $("lon").value = pos.coords.longitude.toFixed(4); },
    () => showError("Could not read your location")
  );
});

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  body.irrigated = $("irrigated").checked;
  $("submit").disabled = true;
  $("submit").textContent = "Fetching weather…";
  $("error").classList.add("hidden");
  try {
    const res = await fetch("/api/predict", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
    const json = await readJson(res);
    if (!res.ok) throw new Error(json.error || "Request failed");
    data = json;
    render();
  } catch (err) {
    showError(err.message);
  } finally {
    $("submit").disabled = false;
    $("submit").textContent = "Get recommendation";
  }
});

function showError(msg) { $("error").textContent = msg; $("error").classList.remove("hidden"); }

function render() {
  const w = data.season_weather;
  $("summary").innerHTML = `
    <h2>Season &amp; weather</h2>
    <p><span class="pill">📍 ${data.location.name}</span><span class="pill">🗓️ ${data.season.name}</span></p>
    <p class="muted">${data.season.description}. Typical weather for ${w.window_start} – ${w.window_end},
      averaged over ${w.years.length} years (${Math.min(...w.years)}–${Math.max(...w.years)}), NASA POWER.</p>
    ${weatherStats(w.mean)}`;
  $("tabs").innerHTML = data.top_crops.map((c, i) =>
    `<button class="tab${i === 0 ? " active" : ""}" data-i="${i}">${i + 1}. ${c.crop}</button>`).join("");
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("active"));
    t.classList.add("active");
    showCrop(+t.dataset.i);
  }));
  showCrop(0);
  $("results").classList.remove("hidden");
  $("results").scrollIntoView({ behavior: "smooth" });
}

function weatherStats(m) {
  return `<div class="grid">
    <div class="stat"><b>${fmt(m.avg_temp)} °C</b><span>Avg temperature</span></div>
    <div class="stat"><b>${fmt(m.total_rainfall, 0)} mm</b><span>Total rainfall</span></div>
    <div class="stat"><b>${fmt(m.avg_humidity, 0)} %</b><span>Avg humidity</span></div>
    <div class="stat"><b>${fmt(m.avg_solar)} MJ/m²</b><span>Solar radiation / day</span></div>
  </div>`;
}

function showCrop(i) {
  selected = i;
  $("explanation").classList.add("hidden");
  $("explain-error").classList.add("hidden");
  const c = data.top_crops[i], y = c.yield, w = c.weather;
  const notes = y.limiting_factors.length
    ? `<ul class="notes">${y.limiting_factors.map((n) => `<li>${n}</li>`).join("")}</ul>`
    : `<p class="muted">No major limiting factors found.</p>`;
  $("detail").innerHTML = `
    <p class="muted">${c.fits_season ? "✅ Suited to this season" : "⚠️ Not usually sown in this season"}
      · sown in: ${c.sowing_seasons.join(", ")} · model confidence ${fmt(c.probability * 100, 0)}%</p>
    <div class="grid" style="margin:12px 0">
      <div class="stat"><span>📈 Expected yield</span><b class="big">${fmt(y.per_acre.expected)}</b><span>${y.per_acre.unit} (${fmt(y.expected, 2)} ${y.unit})</span></div>
      <div class="stat"><span>Range (past years)</span><b>${fmt(y.per_acre.low)} – ${fmt(y.per_acre.high)}</b><span>${y.per_acre.unit} · ${y.percent_of_potential}% of potential</span></div>
      <div class="stat"><span>Growing period</span><b>${c.growing_days} days</b><span>Harvest ≈ ${c.expected_harvest}</span></div>
    </div>
    <h2>Weather during crop period (${w.window_start} – ${w.window_end})</h2>
    ${weatherStats(w.mean)}
    <h2 style="margin-top:16px">What limits the yield</h2>
    ${notes}
    <h2 style="margin-top:16px">Yield by historical year</h2>
    <table><tr><th>Weather year</th><th>Yield (${y.unit})</th></tr>
      ${y.by_year.map((r) => `<tr><td>${r.year}</td><td>${fmt(r.yield, 2)}</td></tr>`).join("")}</table>
    ${fertilizerSection(c.fertilizer)}`;
}

function productList(products) {
  return products.map((p) => `${p.product} ${p.kg_per_acre} kg`).join(" + ") || "—";
}

function fertilizerSection(f) {
  const s = f.soil_status, d = f.adjusted_dose, a = f.dose_per_acre, r = f.recommended_dose;
  const nutrientRows = ["N", "P", "K"].map((k) => s.nutrients[k]).map((n) => `
    <tr><td>${n.name}</td><td>${fmt(n.value)}</td><td>${fmt(n.crop_need)}</td>
      <td><span class="badge s-${n.status}">${n.status}</span> ${n.percent_of_need}% of need</td></tr>`).join("");
  return `
    <h2 style="margin-top:20px">🌱 Soil status for this crop</h2>
    <table><tr><th>Nutrient</th><th>Your soil</th><th>Crop needs</th><th>Status</th></tr>
      ${nutrientRows}
      <tr><td>pH</td><td>${s.ph.value}</td><td>${s.ph.crop_range[0]} – ${s.ph.crop_range[1]}</td>
        <td>${s.ph.status} ${s.ph.suits_crop ? "✅" : "⚠️ outside crop range"}</td></tr></table>

    <h2 style="margin-top:20px">🧪 Fertilizer guidance</h2>
    <p class="dose">Nutrients needed: <b>N ${a.N} · P₂O₅ ${a.P2O5} · K₂O ${a.K2O}</b> kg/acre
      <span class="muted">(${d.N}-${d.P2O5}-${d.K2O} kg/ha, standard dose ${r.N}-${r.P2O5}-${r.K2O} adjusted for your soil)</span></p>
    <table><tr><th>Fertilizer</th><th>kg / acre</th><th>50 kg bags / acre</th><th>kg / hectare</th></tr>
      ${f.total_products.map((p) => `<tr><td>${p.product}</td><td>${p.kg_per_acre}</td><td>${p.bags_per_acre}</td><td>${p.kg_per_ha}</td></tr>`).join("")}</table>
    <h2 style="margin-top:16px">When to apply (per acre)</h2>
    <table><tr><th>Stage</th><th>Date</th><th>Apply</th></tr>
      ${f.schedule.map((st) => `<tr><td>${st.stage}</td><td>${st.date}</td><td>${productList(st.products)}</td></tr>`).join("")}</table>
    <h2 style="margin-top:16px">Other advice</h2>
    <ul class="tips">${f.amendments.map((t) => `<li>${t}</li>`).join("")}</ul>`;
}
