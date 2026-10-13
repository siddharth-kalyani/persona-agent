import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver; Fluent UI's MessageBar uses it for layout.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
