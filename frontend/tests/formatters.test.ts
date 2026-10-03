import { describe, expect, it } from "vitest";
import {
  formatLatency,
  formatMicroUsd,
  formatPercent,
  formatTokens,
} from "../src/lib/formatters";

describe("formatters", () => {
  describe("formatMicroUsd", () => {
    it("returns 'unpriced' for null and undefined", () => {
      expect(formatMicroUsd(null)).toBe("unpriced");
      expect(formatMicroUsd(undefined)).toBe("unpriced");
    });

    it("formats zero micro-USD as $0.00", () => {
      expect(formatMicroUsd(0)).toBe("$0.00");
    });

    it("formats >= $1.00 with standard two decimals", () => {
      expect(formatMicroUsd(1_000_000)).toBe("$1.00");
      expect(formatMicroUsd(2_500_000)).toBe("$2.50");
      expect(formatMicroUsd(12_345_678)).toBe("$12.35");
    });

    it("formats < $1.00 with precision up to 6 decimals without trailing zeroes", () => {
      expect(formatMicroUsd(1_500)).toBe("$0.0015");
      expect(formatMicroUsd(250)).toBe("$0.00025");
      expect(formatMicroUsd(50_000)).toBe("$0.05");
      expect(formatMicroUsd(1)).toBe("$0.000001");
    });
  });

  describe("formatLatency", () => {
    it("returns dash for null and undefined", () => {
      expect(formatLatency(null)).toBe("—");
      expect(formatLatency(undefined)).toBe("—");
    });

    it("formats < 1000 ms as milliseconds", () => {
      expect(formatLatency(150)).toBe("150 ms");
      expect(formatLatency(999.4)).toBe("999 ms");
      expect(formatLatency(0)).toBe("0 ms");
    });

    it("formats >= 1000 ms as seconds with two decimals", () => {
      expect(formatLatency(1000)).toBe("1.00 s");
      expect(formatLatency(1540)).toBe("1.54 s");
      expect(formatLatency(5200)).toBe("5.20 s");
    });
  });

  describe("formatTokens", () => {
    it("formats integers with commas", () => {
      expect(formatTokens(0)).toBe("0");
      expect(formatTokens(1234)).toBe("1,234");
      expect(formatTokens(1500000)).toBe("1,500,000");
      expect(formatTokens(null)).toBe("0");
      expect(formatTokens(undefined)).toBe("0");
    });
  });

  describe("formatPercent", () => {
    it("formats ratios as percentages with one decimal", () => {
      expect(formatPercent(0)).toBe("0.0%");
      expect(formatPercent(0.052)).toBe("5.2%");
      expect(formatPercent(0.1234)).toBe("12.3%");
      expect(formatPercent(1)).toBe("100.0%");
      expect(formatPercent(null)).toBe("0.0%");
    });
  });
});
