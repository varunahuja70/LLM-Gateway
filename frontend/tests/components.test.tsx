import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CodeSnippet } from "../src/components/shared/CodeSnippet";
import { EmptyState } from "../src/components/shared/EmptyState";
import { ErrorState } from "../src/components/shared/ErrorState";
import { KpiCard } from "../src/components/shared/KpiCard";

describe("Foundation Components", () => {
  describe("KpiCard", () => {
    it("renders title, value, and subtitle", () => {
      render(
        <KpiCard
          title="Total Spend"
          value="$12.45"
          subtitle="Past 7 days"
        />
      );
      expect(screen.getByText("Total Spend")).toBeDefined();
      expect(screen.getByText("$12.45")).toBeDefined();
      expect(screen.getByText("Past 7 days")).toBeDefined();
    });

    it("renders loading skeleton when loading=true", () => {
      const { container } = render(
        <KpiCard title="Total Spend" value="$12.45" loading={true} />
      );
      expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
      expect(screen.queryByText("$12.45")).toBeNull();
    });
  });

  describe("EmptyState", () => {
    it("renders title, description and action", () => {
      render(
        <EmptyState
          title="No projects found"
          description="Create your first project to start routing LLM traffic."
          action={<button>Create Project</button>}
        />
      );
      expect(screen.getByText("No projects found")).toBeDefined();
      expect(
        screen.getByText("Create your first project to start routing LLM traffic.")
      ).toBeDefined();
      expect(screen.getByRole("button", { name: "Create Project" })).toBeDefined();
    });
  });

  describe("ErrorState", () => {
    it("renders error message and retry button", () => {
      let retried = false;
      render(
        <ErrorState
          title="Connection failed"
          message="Could not reach the admin server."
          requestId="req_12345"
          onRetry={() => {
            retried = true;
          }}
        />
      );
      expect(screen.getByText("Connection failed")).toBeDefined();
      expect(screen.getByText("Could not reach the admin server.")).toBeDefined();
      expect(screen.getByText(/req_12345/)).toBeDefined();

      const retryBtn = screen.getByRole("button", { name: /try again/i });
      retryBtn.click();
      expect(retried).toBe(true);
    });
  });

  describe("CodeSnippet", () => {
    it("renders code snippet text", () => {
      render(<CodeSnippet code='curl -X POST https://example.com' language="bash" />);
      expect(screen.getByText(/curl -X POST https:\/\/example.com/)).toBeDefined();
    });
  });
});
