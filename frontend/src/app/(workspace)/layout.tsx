import { LeftNav } from "@/components/shell/LeftNav";
import { TopBar } from "@/components/shell/TopBar";

// Composes the persistent GCP-console-like shell — top bar + left nav — on
// the --paper canvas. Wraps every route under the (workspace) group (a route
// group: it does not add a URL segment).
export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col bg-[var(--paper)]">
      <TopBar />
      <div className="flex flex-1">
        <LeftNav />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}
