"use client";

import { useLanguage } from "@/contexts/LanguageContext";
import Link from "next/link";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { AuraGlow } from "@/components/ui/AuraGlow";
import { POSTS } from "@/lib/blog/posts";

export function BlogIndexContent() {
  const { language, setLanguage } = useLanguage();
  const isAr = language === "ar";

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
          <Link href="/about" className="text-sm text-text-secondary transition-colors hover:text-white">
            {isAr ? "من نحن" : "About"}
          </Link>
          <Link href="/signup" className="text-sm font-semibold text-[#f5a623] transition-colors hover:text-white">
            {isAr ? "ابدأ مجاناً" : "Start free"}
          </Link>
        </nav>
      </header>

      <main className="relative z-10 mx-auto max-w-4xl px-5 py-16 md:px-10">
        <div className="mb-10">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-[#f5a623]">
            {isAr ? "أدلة مهنية" : "Career Guides"}
          </p>
          <h1 className="mb-4 text-3xl font-semibold text-white md:text-4xl">
            {isAr
              ? "أدلة عملية لسوق العمل في الإمارات"
              : "Practical guides for the UAE job market"}
          </h1>
          <p className="max-w-2xl text-base leading-7 text-text-secondary">
            {isAr
              ? "كتابة السيرة الذاتية، البحث عن وظيفة، والاستعداد للمقابلات — نصائح محدثة ومخصصة لدبي وأبوظبي وسائر الإمارات."
              : "CV writing, job searching, and interview preparation — up-to-date advice specific to Dubai, Abu Dhabi, and the wider Emirates."}
          </p>
        </div>

        <div className="space-y-6">
          {POSTS.map((post) => (
            <Link key={post.slug} href={`/blog/${post.slug}`} className="block group">
              <GlassPanel className="rounded-2xl border border-white/10 p-6 transition-colors group-hover:border-[#f5a623]/40 md:p-8">
                <h2 className="mb-2 text-xl font-semibold text-white transition-colors group-hover:text-[#f5a623]">
                  {isAr ? post.title.ar : post.title.en}
                </h2>
                <p className="mb-4 text-sm leading-6 text-text-secondary">
                  {isAr ? post.description.ar : post.description.en}
                </p>
                <p className="text-xs font-semibold uppercase tracking-widest text-text-tertiary">
                  {isAr
                    ? `${post.readingMinutes} دقائق قراءة`
                    : `${post.readingMinutes} min read`}
                </p>
              </GlassPanel>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
