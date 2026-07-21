"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { getPostBySlug } from "@/lib/blog/posts";

export function BlogPostContent({ slug }: { slug: string }) {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";
  const post = getPostBySlug(slug);

  if (!post) return null;

  const lang = isAr ? "ar" : "en";

  return (
    <div dir={isAr ? "rtl" : "ltr"} className="relative min-h-screen overflow-x-hidden bg-[#0a0a1a]">
      <AuraGlow aria-hidden="true" variant="magenta" position="top-left" />
      <AuraGlow aria-hidden="true" variant="cyan" position="bottom-right" />

      <header className="relative z-10 flex items-center justify-between border-b border-border-subtle bg-black/50 px-5 py-4 backdrop-blur-xl md:px-10">
        <Link href="/" className="flex items-center gap-2 text-lg font-black tracking-tight text-white">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#f5a623] text-[#0a0a1a] text-sm font-black shadow-[0_0_28px_rgba(245,166,35,0.28)]">
            R
          </span>
          <span>Rico<span className="text-[#f5a623]"> Hunt</span></span>
        </Link>
        <nav className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setLanguage(isAr ? "en" : "ar")}
            aria-label={isAr ? "Switch to English" : "Switch to Arabic"}
            className="text-[12px] font-semibold px-2.5 py-1 rounded-lg border border-border-subtle text-text-secondary hover:text-white hover:border-[#f5a623]/50 transition-colors"
          >
            {isAr ? "EN" : "عربي"}
          </button>
          <Link href="/blog" className="text-sm text-text-secondary transition-colors hover:text-white">
            {isAr ? "كل الأدلة" : "All guides"}
          </Link>
          <Link href="/signup" className="text-sm font-semibold text-[#f5a623] transition-colors hover:text-white">
            {isAr ? "ابدأ مجاناً" : "Start free"}
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <GlassPanel className="rounded-2xl border border-white/10 p-8 md:p-12">
          <article>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
              {isAr ? "دليل مهني" : "Career Guide"}
            </p>
            <h1 className="mb-3 text-3xl font-semibold leading-tight text-white md:text-4xl">
              {post.title[lang]}
            </h1>
            <p className="mb-8 text-xs font-semibold uppercase tracking-widest text-text-tertiary">
              {isAr
                ? `${post.readingMinutes} دقائق قراءة`
                : `${post.readingMinutes} min read`}
            </p>

            <div className="mb-10 space-y-3 text-base leading-7 text-text-secondary">
              {post.intro[lang].map((paragraph, idx) => (
                <p key={`intro-${idx}`}>{paragraph}</p>
              ))}
            </div>

            <div className="space-y-10 text-sm leading-7 text-text-secondary">
              {post.sections.map((section, sIdx) => (
                <section key={`section-${sIdx}`}>
                  <h2 className="mb-3 text-lg font-semibold text-white">
                    {section.heading[lang]}
                  </h2>
                  {section.paragraphs?.[lang]?.map((paragraph, pIdx) => (
                    <p key={`p-${sIdx}-${pIdx}`} className={pIdx > 0 ? "mt-3" : undefined}>
                      {paragraph}
                    </p>
                  ))}
                  {section.bullets && (
                    <ul className="ms-4 mt-3 list-disc space-y-2">
                      {section.bullets[lang].map((bullet, bIdx) => (
                        <li key={`b-${sIdx}-${bIdx}`}>{bullet}</li>
                      ))}
                    </ul>
                  )}
                </section>
              ))}
            </div>

            <div className="mt-12 rounded-2xl border border-[#f5a623]/25 bg-[#f5a623]/[0.06] p-6 text-center">
              <p className="mb-4 text-base font-semibold text-white">
                {isAr
                  ? "دع ريكو يتولى البحث والمطابقة والمتابعة عنك"
                  : "Let Rico handle the searching, matching, and tracking for you"}
              </p>
              <Link
                href="/signup"
                className="inline-block rounded-xl bg-[#f5a623] px-6 py-3 text-sm font-bold text-[#0a0a1a] transition-transform hover:scale-105"
              >
                {isAr ? "أنشئ حسابك المجاني" : "Create your free account"}
              </Link>
            </div>
          </article>
        </GlassPanel>
      </main>
    </div>
  );
}
