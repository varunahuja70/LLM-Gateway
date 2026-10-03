import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, getCsrfToken, setCsrfToken } from "../src/lib/api";

describe("api helper", () => {
  beforeEach(() => {
    setCsrfToken(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    setCsrfToken(null);
    vi.restoreAllMocks();
  });

  describe("CSRF token handling", () => {
    it("sets and gets CSRF token via memory", () => {
      expect(getCsrfToken()).toBeNull();
      setCsrfToken("test-csrf-123");
      expect(getCsrfToken()).toBe("test-csrf-123");
    });
  });

  describe("ApiError class", () => {
    it("constructs ApiError with status, message, and optional payload", () => {
      const err = new ApiError(404, "Not Found", { detail: "Project missing" });
      expect(err).toBeInstanceOf(Error);
      expect(err.name).toBe("ApiError");
      expect(err.status).toBe(404);
      expect(err.message).toBe("Not Found");
      expect(err.data).toEqual({ detail: "Project missing" });
    });
  });

  describe("api request methods", () => {
    it("performs GET request and parses JSON response", async () => {
      const mockData = { id: "p1", name: "Project One" };
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response(JSON.stringify(mockData), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const res = await api.get<{ id: string; name: string }>("/admin/projects");
      expect(res).toEqual(mockData);
      expect(fetchSpy).toHaveBeenCalledWith(
        "/admin/projects",
        expect.objectContaining({
          method: "GET",
          credentials: "include",
        })
      );
    });

    it("attaches CSRF header on POST mutating requests when token is present", async () => {
      setCsrfToken("csrf-token-abc");
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response(JSON.stringify({ success: true }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      await api.post("/admin/projects", { name: "New Project" });
      expect(fetchSpy).toHaveBeenCalled();
      const callArgs = fetchSpy.mock.calls[0];
      const headers = callArgs[1]?.headers as Headers;
      expect(headers.get("X-CSRF-Token")).toBe("csrf-token-abc");
      expect(headers.get("Content-Type")).toBe("application/json");
    });

    it("handles 204 No Content returning empty object", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response(null, { status: 204 })
      );

      const res = await api.delete("/admin/projects/p1");
      expect(res).toEqual({});
    });

    it("throws ApiError with detail message on HTTP failure", async () => {
      vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Project quota exceeded" }), {
          status: 400,
          headers: { "Content-Type": "application/json" },
        })
      );

      await expect(api.get("/admin/projects")).rejects.toThrow("Project quota exceeded");
    });
  });
});
