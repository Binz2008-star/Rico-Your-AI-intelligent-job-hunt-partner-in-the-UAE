/**
 * FeaturesSection.tsx
 *
 * 3-column bento of product differentiators.
 * No testimonials, no logo walls, no live counters.
 */

export default function FeaturesSection() {
  const features = [
    {
      kicker: "Interactive hero",
      title: "Prompt-led, not banner-led.",
      body:
        "The hero reacts to prompts, swaps role cards, and demonstrates reasoning over your profile live — borrowed from Perplexity's interaction grammar, mapped to UAE job-search.",
      foot: "Motion proves usefulness",
    },
    {
      kicker: "Agent framing",
      title: "Execution competence, not just matching.",
      body:
        "Rico reads, matches, explains, organises, and iterates — the same agent confidence as a software-engineer AI, redirected to the career workflow.",
      foot: "Competence over decoration",
    },
    {
      kicker: "Trust layer",
      title: "You stay in control, visibly.",
      body:
        "Approval-bound actions, bilingual output, and privacy-first design aren't hidden in the FAQ — they surface as product-native constraints and copy throughout the UI.",
      foot: "High-trust by design",
    },
  ];

  return (
    <section
      id="features"
      aria-labelledby="features-heading"
      className="py-16 md:py-24"
    >
      <div className="container mx-auto px-4 max-w-[1120px]">
        <div className="mb-10">
          <h2
            id="features-heading"
            className="font-display text-[clamp(2rem,3.8vw,3.25rem)] leading-[1] tracking-[-0.04em] mb-3"
          >
            Designed like a product, not a marketing page.
          </h2>
          <p className="text-muted-foreground max-w-[60ch]">
            The redesign borrows the confidence of Perplexity Pro's interactive
            hero and the execution framing of Devin — pivoted to Rico's purpose.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {features.map((f) => (
            <article
              key={f.kicker}
              className="rounded-[24px] border border-white/10 bg-white/[0.04] p-6 flex flex-col justify-between min-h-[260px]"
            >
              <div>
                <p className="text-[11px] font-bold uppercase tracking-widest text-[#37ddB0] mb-3">
                  {f.kicker}
                </p>
                <h3 className="font-semibold text-[1.25rem] leading-tight tracking-tight mb-3">
                  {f.title}
                </h3>
                <p className="text-muted-foreground text-sm">{f.body}</p>
              </div>
              <p className="mt-6 text-[11px] font-bold uppercase tracking-widest text-muted-foreground/60">
                {f.foot}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
