// Carries the Context Pack's posture into the UI (Frontend PRD §11: "every
// analysis result restates 'treat as a hypothesis, not a finding'"). Shown on
// every analysis RESULT surface — SearchResult, Niche Dashboard, Category
// Sweep — once there's an actual result to caveat. Quiet and identity-
// consistent: a single muted line, not a colored alert box, so it reads as
// the product's stance rather than a warning.
export function HypothesisBanner({ className = "" }: { className?: string }) {
  return (
    <p
      role="note"
      className={`text-xs text-[var(--muted)] ${className}`}
    >
      Treat each candidate as a hypothesis, not a finding &mdash; verify
      before you act on it.
    </p>
  );
}
