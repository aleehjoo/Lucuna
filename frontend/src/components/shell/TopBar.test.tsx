import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { api } from "@/lib/api";
import { TopBar } from "./TopBar";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("TopBar health indicator", () => {
  it("shows the warming-up state when models_ready is false", async () => {
    vi.spyOn(api, "get").mockImplementation((path: string) => {
      if (path === "/health") {
        return Promise.resolve({ status: "warming", models_ready: false });
      }
      return Promise.resolve([]);
    });

    renderWithClient(<TopBar />);

    await waitFor(() =>
      expect(
        screen.getByText(/warming up the analysis engine/i),
      ).toBeInTheDocument(),
    );
  });

  it("shows the ready state when models_ready is true", async () => {
    vi.spyOn(api, "get").mockImplementation((path: string) => {
      if (path === "/health") {
        return Promise.resolve({ status: "ok", models_ready: true });
      }
      return Promise.resolve([]);
    });

    renderWithClient(<TopBar />);

    await waitFor(() =>
      expect(screen.getByText(/engine ready/i)).toBeInTheDocument(),
    );
  });
});
