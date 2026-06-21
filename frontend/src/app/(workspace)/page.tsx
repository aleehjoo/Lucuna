import { redirect } from "next/navigation";

// "/" is not a real surface — the Projects home (W6) is. This replaces the
// W5 design-preview landing: a Server Component redirect means "/" never
// renders its own markup (no flash of placeholder content) before landing
// on /projects, which owns the index UI (grid, onboarding empty state, etc).
export default function Home() {
  redirect("/projects");
}
