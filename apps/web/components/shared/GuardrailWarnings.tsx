import type { MatchingGuardrailWarning } from "@/types";

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
}: {
  warnings: unknown[] | undefined;
  language: Language;
}) {
  const normalized = normalizeWarnings(warnings);
  if (normalized.length === 0) return null;

  return (
    <div
      role="alert"
      className="rounded-lg border border-amber-400/30 bg-amber-400/10 p-3 text-start"
    >
      <ul className="flex flex-col gap-2">
        {normalized.map((warning, index) => {
          const message = localizedText(warning, language, "message");
          const suggestion = localizedText(warning, language, "suggestion");

          return (
            <li key={`${warning.code}-${warning.field}-${index}`} className="text-xs leading-5">
              <p className="font-semibold text-amber-100">{message}</p>
              {suggestion && <p className="mt-0.5 text-amber-50/80">{suggestion}</p>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
