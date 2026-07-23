import { cn } from "@/lib/utils";
import type { MatchingGuardrailWarning } from "@/types";
import type { WorkspacePalette } from "../workspace/theme";

type Language = "en" | "ar";

function normalizeWarnings(warnings: unknown[] | undefined): MatchingGuardrailWarning[] {
  if (!Array.isArray(warnings)) return [];
  const normalized: MatchingGuardrailWarning[] = [];

  warnings.forEach((warning) => {
    if (typeof warning === "string") {
      normalized.push({
        code: "legacy_warning",
        field: "matching",
        message: warning,
      });
      return;
    }

    if (warning && typeof warning === "object") {
      const candidate = warning as Partial<MatchingGuardrailWarning>;
      if (typeof candidate.message === "string" && candidate.message.trim()) {
        normalized.push({
          code: candidate.code ?? "matching_warning",
          field: candidate.field ?? "matching",
          severity: candidate.severity ?? "warning",
          message: candidate.message,
          suggestion: candidate.suggestion,
          message_ar: candidate.message_ar,
          suggestion_ar: candidate.suggestion_ar,
        });
      }
    }
  });

  return normalized;
}

function localizedText(
  warning: MatchingGuardrailWarning,
  language: Language,
  key: "message" | "suggestion",
) {
  const arabicKey = key === "message" ? "message_ar" : "suggestion_ar";
  if (language === "ar" && warning[arabicKey]) return warning[arabicKey];
  return warning[key];
}

export function GuardrailWarnings({
  warnings,
  language,
  palette,
}: {
  warnings: unknown[] | undefined;
  language: Language;
  palette?: WorkspacePalette;
}) {
  const normalized = normalizeWarnings(warnings);
  if (normalized.length === 0) return null;

  const usesPalette = palette != null;

  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg p-3 text-start",
        !usesPalette && "border border-amber-400/30 bg-amber-400/10"
      )}
      style={
        usesPalette
          ? {
            backgroundColor: `color-mix(in srgb, ${palette.red} 10%, ${palette.panel})`,
            borderWidth: 1,
            borderStyle: "solid",
            borderColor: `color-mix(in srgb, ${palette.red} 35%, transparent)`,
          }
          : undefined
      }
    >
      <ul className="flex flex-col gap-2">
        {normalized.map((warning, index) => {
          const message = localizedText(warning, language, "message");
          const suggestion = localizedText(warning, language, "suggestion");

          return (
            <li key={`${warning.code}-${warning.field}-${index}`} className="text-xs leading-5">
              <p
                className={cn("font-semibold", !usesPalette && "text-amber-100")}
                style={usesPalette ? { color: palette.red } : undefined}
              >
                {message}
              </p>
              {suggestion && (
                <p
                  className={cn("mt-0.5", !usesPalette && "text-amber-50/80")}
                  style={usesPalette ? { color: palette.ink55 } : undefined}
                >
                  {suggestion}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
