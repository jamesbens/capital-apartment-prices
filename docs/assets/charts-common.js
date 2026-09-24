/* Shared helpers for the portfolio charts (ECharts). */
(function (global) {
  function css(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function theme() {
    return {
      ink: css("--ink"), ink2: css("--ink-2"), muted: css("--muted"),
      grid: css("--grid"), axis: css("--axis"), surface: css("--surface"),
      s1: css("--series-1"), s2: css("--series-2"),
      smaFast: css("--sma-fast"), smaSlow: css("--sma-slow"),
      entry: css("--entry"), exit: css("--exit"),
      font: getComputedStyle(document.body).fontFamily,
    };
  }

  /** Try each URL in order: the live project feed first, the bundled snapshot second. */
  async function fetchFirst(urls) {
    let lastErr;
    // In a local preview the live feeds are cross-origin; go straight to the bundled snapshot.
    const local = /^(localhost|127\.0\.0\.1)$/.test(location.hostname) || location.protocol === "file:";
    if (local) urls = urls.filter((u) => !/^https?:/.test(u));
    for (const url of urls) {
      try {
        const res = await fetch(url, { cache: "no-cache" });
        if (!res.ok) throw new Error(res.status + " " + url);
        return { data: await res.json(), url };
      } catch (err) { lastErr = err; }
    }
    throw lastErr;
  }

  function tooltipBase(t) {
    return {
      backgroundColor: t.surface, borderColor: t.axis, borderWidth: 1, padding: [10, 12],
      textStyle: { color: t.ink, fontFamily: t.font, fontSize: 13 },
      extraCssText: "border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.25);",
    };
  }

  /** Re-render every registered chart when the theme flips or the viewport changes. */
  const renderers = [];
  function onRerender(fn) { renderers.push(fn); }
  function rerenderAll() { renderers.forEach((fn) => fn()); }
  new MutationObserver(rerenderAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rerenderAll);

  const fmt = {
    num: (v, d = 0) => (v == null ? "–" : v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d })),
    pct: (v, d = 1) => (v == null ? "–" : (v * 100).toFixed(d) + "%"),
    date: (s) => new Date(s + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }),
  };

  global.PortfolioCharts = { css, theme, fetchFirst, tooltipBase, onRerender, fmt };
})(window);
