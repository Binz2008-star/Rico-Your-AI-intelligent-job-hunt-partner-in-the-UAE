/**
 * TrustBar.tsx
 *
 * Static trust signal bar — English + Arabic pill copy.
 * No live counters, no logos, no testimonials.
 */

export default function TrustBar() {
  const signals = [
    { en: "English + Arabic", ar: "عربي + إنجليزي" },
    { en: "You approve every action", ar: "أنت توافق على كل إجراء" },
    { en: "Built for the UAE market", ar: "مصمم لسوق الإمارات" },
    { en: "No CV sold or shared", ar: "لا يُباع سيرتك أو يُشارَك" },
  ];

  return (
    <section
      aria-label="Trust signals"
      className="py-10 border-y border-white/8"
    >
      <div className="container mx-auto px-4 max-w-[1120px]">
        <ul
          className="flex flex-wrap justify-center gap-3"
          role="list"
        >
          {signals.map((s) => (
            <li
              key={s.en}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/[0.04] text-sm text-muted-foreground"
            >
              <span>{s.en}</span>
              <span aria-hidden="true" className="text-white/20">·</span>
              {/* RTL Arabic label */}
              <span dir="rtl" lang="ar" className="text-white/50 text-xs">
                {s.ar}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
