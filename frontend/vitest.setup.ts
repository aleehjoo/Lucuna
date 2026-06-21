import "@testing-library/jest-dom/vitest";

// jsdom doesn't implement ResizeObserver, but Recharts' ResponsiveContainer
// (used by every chart in src/components/charts) requires it to measure its
// container and size the underlying SVG. Without this stub, charts render at
// 0x0 in tests — not broken, just untestable. This is a no-op observer: it
// never fires a resize callback, so charts fall back to whatever layout box
// jsdom's getBoundingClientRect reports (stubbed to a fixed non-zero size
// below), which is enough for assertions on chart content (e.g. bar labels,
// axis ticks) to work.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// jsdom's layout engine always reports 0x0 for getBoundingClientRect/offset*,
// since it doesn't actually lay out CSS. Recharts' ResponsiveContainer reads
// these to size its SVG, so without a stub every chart measures 0 width and
// silently renders nothing (no error, just an empty container) — exactly the
// failure mode this fix avoids. Fixed dimensions are arbitrary but generous
// enough that no chart's content gets clipped in tests.
//
// Recharts ALSO uses getBoundingClientRect on a hidden offscreen <span> (see
// recharts/lib/util/DOMUtils.js::measureTextWithDOM) to measure axis tick
// label text width — if that reuses the same 800x600 stub, every label
// "measures" as 800px wide and Recharts drops ticks it thinks won't fit. So
// the stub must special-case the measurement span and return a small,
// content-aware size instead, while everything else (chart containers) gets
// the generous fixed size above.
const MEASUREMENT_SPAN_ID = "recharts_measurement_span";

Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
  configurable: true,
  value: function getBoundingClientRect(this: HTMLElement) {
    if (this.id === MEASUREMENT_SPAN_ID) {
      const text = this.textContent ?? "";
      return {
        width: text.length * 7,
        height: 14,
        top: 0,
        left: 0,
        bottom: 14,
        right: text.length * 7,
        x: 0,
        y: 0,
        toJSON() {},
      };
    }
    return {
      width: 800,
      height: 600,
      top: 0,
      left: 0,
      bottom: 600,
      right: 800,
      x: 0,
      y: 0,
      toJSON() {},
    };
  },
});
Object.defineProperty(HTMLElement.prototype, "offsetWidth", {
  configurable: true,
  get: () => 800,
});
Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
  configurable: true,
  get: () => 600,
});

// jsdom has no `window.matchMedia`. Every chart in src/components/charts
// reads `prefers-reduced-motion` via useReducedMotion (src/lib/useReducedMotion.ts)
// to decide `isAnimationActive`. Without a stub, that hook silently no-ops
// (matchMedia is undefined) and charts default to animated — and Recharts
// 3.8.1's enter animation does not resolve synchronously under jsdom/React 19
// in this test environment (verified empirically: an animated <Bar> renders
// an empty <g class="recharts-inactive-bar"> with no <rect>/<path> child at
// assertion time, even with explicit pixel width/height and no
// ResponsiveContainer involved — disabling animation makes the same bar
// render its rect with correct, data-driven geometry immediately). Reporting
// `prefers-reduced-motion: reduce` here makes every chart's tests exercise
// the (real, shipped) reduced-motion path deterministically, which is also
// the more accessibility-faithful default for a test environment.
window.matchMedia =
  window.matchMedia ??
  ((query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  }));
