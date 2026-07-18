/**
 * HowItWorks.tsx
 *
 * Three-step workflow section.
 * Static copy only — no network calls, no dynamic data.
 */

export default function HowItWorks() {
  const steps = [
    {
      n: "01",
      title: "Upload your CV",
      body:
        "Rico parses your experience, infers seniority and salary band, and keeps your profile current — one upload, no repeated forms.",
    },
    {
      n: "02",
      title: "See what fits — and why",
      body:
        "Ranked roles arrive with fit scores and plain-language reasons. The explanation is the product, not supporting copy.",
    },
    {
      n: "03",
      title: "Track every move",
      body:
        "Saved, opened, applied, follow-up, interview — all in one place. You approve every outbound action before it happens.",
    },
  ];

  return (
    <section
      id="how-it-works"
      aria-labelledby="hiw-heading"
      className="py-16 md:py-24"
    >
      <div className="container mx-auto px-4 max-w-[1120px]">
        <div className="mb-10">
          <h2
            id="hiw-heading"
            className="font-display text-[clamp(2rem,3.8vw,3.25rem)] leading-[1] tracking-[-0.04em] mb-3"
          >
            Three steps. No noise.
          </h2>
          <p className="text-muted-foreground max-w-[60ch]">
            Keep the original Rico value prop, but deliver it with product
            confidence and honest hierarchy.
          </p>
        </div>

        <ol className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((step) => (
            <li
              key={step.n}
              className="rounded-[24px] border border-white/10 bg-white/[0.04] p-6"
            >
              <div
                aria-hidden="true"
                className="w-10 h-10 rounded-full border border-[#21d19a]/18 bg-[#21d19a]/[0.08] grid place-items-center text-[#37ddB0] font-extrabold text-sm mb-4"
              >
                {step.n}
              </div>
              <h3 className="font-semibold text-base leading-tight mb-2">
                {step.title}
              </h3>
              <p className="text-muted-foreground text-sm">{step.body}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
