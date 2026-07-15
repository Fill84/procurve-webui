// Registers jest-dom matchers (toBeDisabled, toBeEnabled, ...) with vitest's
// expect, and unmounts rendered trees between tests (React Testing Library
// only auto-registers its afterEach cleanup when test globals are enabled,
// which this project keeps off). Loaded via `test.setupFiles`.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
});
