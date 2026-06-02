import { render as rtlRender, type RenderOptions } from "@testing-library/react";
import type { ReactElement } from "react";
import { LanguageProvider } from "@/contexts/LanguageContext";

// Shared test renderer that wraps the UI in the providers required by pages
// and components. Many components call useLanguage(), which throws when no
// LanguageProvider is present, so every test render must include it.
//
// Use the `wrapper` option (not a manual JSX wrap) so the `rerender` returned
// by Testing Library keeps the provider in place across re-renders.
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return rtlRender(ui, { wrapper: LanguageProvider, ...options });
}
