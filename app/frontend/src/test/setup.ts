import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";

// jsdom has no ResizeObserver; Fluent UI's MessageBar uses it for layout.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

// findBy*/waitFor wait 1 s by default; on a loaded dev box Fluent UI renders can take longer.
configure({ asyncUtilTimeout: 5000 });
