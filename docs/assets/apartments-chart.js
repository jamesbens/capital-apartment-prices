/* Apartment price per m² by capital: compare up to 2 cities × any of 1/2/3 bedrooms.
   Encoding: colour = city (fixed slot per selector, never repainted), line dash + marker = bedrooms. */
(function () {
  const { theme, fetchFirst, tooltipBase, onRerender, fmt } = window.PortfolioCharts;

  const DASH = { "1": "solid", "2": [8, 5], "3": [2, 4] };
  const SYMBOL = { "1": "circle", "2": "rect", "3": "triangle" };
  const MAX_CITIES = 2;

  function dashSvg(key, color) {
    const da = key === "1" ? "" : key === "2" ? "6 4" : "2 3";
    return `<svg viewBox="0 0 22 8" aria-hidden="true"><line x1="0" y1="4" x2="22" y2="4" stroke="${color}" stroke-width="2" stroke-dasharray="${da}"/></svg>`;
  }

  window.renderApartments = async function ({ root, sources, defaults = ["Paris", "London"] }) {
    const t0 = theme();
    const els = {
      a: root.querySelector("[data-city-a]"),
      b: root.querySelector("[data-city-b]"),
      chips: root.querySelector("[data-bedrooms]"),
      currency: root.querySelector("[data-currency]"),
      view: root.querySelector("[data-view]"),
      chart: root.querySelector("[data-chart]"),
      table: root.querySelector("[data-table]"),
      hint: root.querySelector("[data-hint]"),
      summary: root.querySelector("[data-summary]"),
      note: root.querySelector("[data-note]"),
    };

    let d;
    try {
      ({ data: d } = await fetchFirst(sources));
    } catch (err) {
      els.chart.innerHTML = `<p class="chart-note">Chart data could not be loaded (${err.message}).</p>`;
      return;
    }

    const state = { cities: defaults.slice(0, MAX_CITIES), bedrooms: new Set(["1", "2", "3"]), currency: "EUR", view: "chart" };
    const cityNames = d.cities.map((c) => c.name);
    state.cities = state.cities.filter((c) => cityNames.includes(c));

    // --- Controls ---------------------------------------------------------
    const optionList = (includeNone) =>
      (includeNone ? `<option value="">— none —</option>` : "") +
      d.cities.map((c) => `<option value="${c.name}">${c.name} · ${c.country}</option>`).join("");
    els.a.innerHTML = optionList(false);
    els.b.innerHTML = optionList(true);
    els.a.value = state.cities[0] || cityNames[0];
    els.b.value = state.cities[1] || "";

    els.chips.innerHTML = d.bedrooms.map((b) =>
      `<button type="button" class="chip" data-key="${b.key}" aria-pressed="true">${dashSvg(b.key, t0.ink2)}${b.label}</button>`).join("");

    function syncSelects() {
      // A city cannot be picked twice: disable it in the other selector.
      [...els.a.options].forEach((o) => (o.disabled = o.value === els.b.value && o.value !== ""));
      [...els.b.options].forEach((o) => (o.disabled = o.value === els.a.value));
      state.cities = [els.a.value, els.b.value].filter(Boolean);
      root.querySelector("[data-dot-a]").style.background = theme().s1;
      root.querySelector("[data-dot-b]").style.background = els.b.value ? theme().s2 : "transparent";
    }
    els.a.addEventListener("change", () => { syncSelects(); draw(); });
    els.b.addEventListener("change", () => { syncSelects(); draw(); });

    els.chips.addEventListener("click", (e) => {
      const btn = e.target.closest(".chip");
      if (!btn) return;
      const k = btn.dataset.key;
      if (state.bedrooms.has(k) && state.bedrooms.size === 1) {
        els.hint.textContent = "Keep at least one apartment size selected.";
        return;
      }
      state.bedrooms.has(k) ? state.bedrooms.delete(k) : state.bedrooms.add(k);
      btn.setAttribute("aria-pressed", state.bedrooms.has(k));
      els.hint.textContent = "";
      draw();
    });

    function segment(el, key) {
      el.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        state[key] = btn.dataset.value;
        el.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", b === btn));
        draw();
      });
    }
    segment(els.currency, "currency");
    segment(els.view, "view");

    // --- Data shaping -----------------------------------------------------
    const bedroomLabel = Object.fromEntries(d.bedrooms.map((b) => [b.key, b.label]));
    const shortBr = (k) => `${k} BR`;
    function seriesData() {
      const keys = [...state.bedrooms].sort();
      const out = [];
      state.cities.forEach((city, ci) => {
        keys.forEach((k) => {
          const eur = d.values[city][k];
          const vals = state.currency === "USD" ? eur.map((v, i) => Math.round(v * d.meta.usd_per_eur[d.years[i]])) : eur;
          out.push({ city, cityIndex: ci, key: k, name: `${city} · ${shortBr(k)}`, values: vals });
        });
      });
      return out;
    }

    // --- Chart ------------------------------------------------------------
    const chart = echarts.init(els.chart, null, { renderer: "canvas" });
    new ResizeObserver(() => chart.resize()).observe(els.chart);

    function draw() {
      const t = theme();
      const rows = seriesData();
      const colorOf = (r) => (r.cityIndex === 0 ? t.s1 : t.s2);
      const sym = state.currency === "USD" ? "$" : "€";
      els.chips.querySelectorAll(".chip").forEach((c) => (c.innerHTML = dashSvg(c.dataset.key, t.ink2) + bedroomLabel[c.dataset.key]));
      root.querySelector("[data-dot-a]").style.background = t.s1;
      root.querySelector("[data-dot-b]").style.background = els.b.value ? t.s2 : "transparent";

      const narrow = els.chart.clientWidth < 640;
      const directLabels = rows.length <= 4 && !narrow;
      chart.setOption({
        animationDuration: 700,
        textStyle: { fontFamily: t.font },
        grid: { left: 64, right: directLabels ? 120 : 20, top: narrow ? 72 : 48, bottom: 36 },
        legend: {
          top: 0, left: 0, itemWidth: 28, itemHeight: 10, itemGap: 16,
          textStyle: { color: t.ink2, fontSize: 12 },
        },
        tooltip: {
          ...tooltipBase(t), trigger: "axis",
          axisPointer: { type: "line", lineStyle: { color: t.muted, type: "dashed" } },
          valueFormatter: (v) => `${sym}${fmt.num(v)} /m²`,
        },
        xAxis: {
          type: "category", data: d.years.map(String), boundaryGap: false,
          axisLine: { lineStyle: { color: t.axis } }, axisTick: { show: false },
          axisLabel: { color: t.muted, fontSize: 11 },
        },
        yAxis: {
          type: "value", scale: true, axisLine: { show: false },
          axisLabel: { color: t.muted, fontSize: 11, formatter: (v) => sym + fmt.num(v) },
          splitLine: { lineStyle: { color: t.grid } },
        },
        series: rows.map((r) => ({
          name: r.name, type: "line", data: r.values, symbol: SYMBOL[r.key], symbolSize: 8, showSymbol: true,
          lineStyle: { width: 2, type: DASH[r.key], color: colorOf(r) },
          itemStyle: { color: colorOf(r), borderColor: t.surface, borderWidth: 2 },
          emphasis: { focus: "series" },
          endLabel: { show: directLabels, color: t.ink2, fontSize: 12, formatter: () => r.name, distance: 8 },
        })),
      }, true);

      // 10-year change summary under the chart
      const first = d.years[0], last = d.years[d.years.length - 1];
      els.summary.innerHTML = rows.map((r) => {
        const ch = r.values[r.values.length - 1] / r.values[0] - 1;
        return `<div class="kpi"><span><i class="city-dot" style="background:${colorOf(r)}"></i>${r.name}</span>` +
          `<b>${sym}${fmt.num(r.values[r.values.length - 1])}<small style="display:inline;color:var(--muted)"> /m² in ${last}</small></b>` +
          `<small>${ch >= 0 ? "+" : ""}${fmt.pct(ch, 0)} vs ${first}</small></div>`;
      }).join("");

      // Accessible table view of exactly what the chart shows
      els.table.innerHTML = `<table class="data"><thead><tr><th>Year</th>${rows.map((r) => `<th>${r.name}</th>`).join("")}</tr></thead><tbody>${
        d.years.map((y, i) => `<tr><td>${y}</td>${rows.map((r) => `<td>${sym}${fmt.num(r.values[i])}</td>`).join("")}</tr>`).join("")
      }</tbody></table>`;
      const showTable = state.view === "table";
      els.table.hidden = !showTable;
      els.chart.style.display = showTable ? "none" : "";
      if (!showTable) chart.resize();
    }

    syncSelects();
    draw();
    onRerender(draw);
    if (els.note) {
      els.note.textContent = `${d.years[0]}–${d.years[d.years.length - 1]} annual averages. ${d.meta.method} Sources: ${d.meta.sources.join("; ")}.`;
    }
  };
})();
