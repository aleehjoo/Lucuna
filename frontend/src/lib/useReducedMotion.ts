"use client";

import { useEffect, useState } from "react";

// Shared by every chart in src/components/charts — Recharts elements take an
// `isAnimationActive` prop; this hook is the single source of truth for that
// boolean so each chart honors `prefers-reduced-motion` without re-deriving
// the media query itself. SSR/test-safe: `window.matchMedia` is absent in
// some jsdom configs and during server rendering, so this defaults to "false"
// (animate) until proven otherwise on the client, never throws either way.
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);

    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
