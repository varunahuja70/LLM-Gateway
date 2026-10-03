import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FallbackChainEditor } from "../src/components/projects/FallbackChainEditor";

describe("FallbackChainEditor", () => {
  it("renders existing models in sequence", () => {
    const chain = ["openai/gpt-4o", "anthropic/claude-3-5-sonnet"];
    render(<FallbackChainEditor chain={chain} onChange={() => {}} />);

    expect(screen.getByText("openai/gpt-4o")).toBeDefined();
    expect(screen.getByText("anthropic/claude-3-5-sonnet")).toBeDefined();
    expect(screen.getByText("Primary Fallback")).toBeDefined();
  });

  it("adds a valid new model to the chain", () => {
    let updatedChain: string[] = [];
    const chain = ["openai/gpt-4o"];
    render(
      <FallbackChainEditor
        chain={chain}
        onChange={(next) => {
          updatedChain = next;
        }}
      />
    );

    const input = screen.getByPlaceholderText(/provider\/model/i);
    fireEvent.change(input, { target: { value: "anthropic/claude-3-5-haiku" } });

    const addBtn = screen.getByRole("button", { name: /add model/i });
    fireEvent.click(addBtn);

    expect(updatedChain).toEqual(["openai/gpt-4o", "anthropic/claude-3-5-haiku"]);
  });

  it("rejects models without provider prefix", () => {
    let called = false;
    render(
      <FallbackChainEditor
        chain={[]}
        onChange={() => {
          called = true;
        }}
      />
    );

    const input = screen.getByPlaceholderText(/provider\/model/i);
    fireEvent.change(input, { target: { value: "just-model-name" } });

    const addBtn = screen.getByRole("button", { name: /add model/i });
    fireEvent.click(addBtn);

    expect(called).toBe(false);
    expect(
      screen.getByText(/Model name must include provider prefix/i)
    ).toBeDefined();
  });

  it("handles remove and reorder", () => {
    let updatedChain: string[] = [];
    const chain = ["openai/gpt-4o", "anthropic/claude-3-5-haiku"];
    render(
      <FallbackChainEditor
        chain={chain}
        onChange={(next) => {
          updatedChain = next;
        }}
      />
    );

    // Remove first
    const removeBtn = screen.getByRole("button", { name: /remove openai\/gpt-4o/i });
    fireEvent.click(removeBtn);
    expect(updatedChain).toEqual(["anthropic/claude-3-5-haiku"]);
  });
});
