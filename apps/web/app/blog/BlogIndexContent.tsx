"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { atelierFraunces, atelierNaskhArabic, atelierSansArabic } from "@/components/atelier-kit/fonts";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono, Plate } from "@/components/atelier-kit/primitives";
import { BLOG_COVERS } from "@/components/illustrations/EditorialInk";
import { POSTS } from "@/lib/blog/posts";
import { BlogMasthead, BLOG_SCOPED_CSS } from "./BlogMasthead";

const SERIF = ATELIER_FONT.serif;

export function BlogIndexContent() {
  const { language } = useLanguage();
  const isAr = language === "ar";
  const arrow = isAr ? "←" : "→";

  return (
    <div
      className={`rblog-root ${isAr ? "rblog-ar" : ""} min-h-screen overflow-x-hidden ${atelierFraunces.variable} ${atelierNaskhArabic.variable} ${atelierSansArabic.variable}`}
      dir={isAr ? "rtl" : "ltr"}
      lang={language}
      style={{ background: C.bg, color: C.ink, fontFamily: ATELIER_FONT.body }}
    >
      <style dangerouslySetInnerHTML={{ __html: BLOG_SCOPED_CSS }} />
      <BlogMasthead />

      <main className="max-w-6xl mx-auto px-5 sm:px-8 pt-14 sm:pt-20 pb-24">
        <p className="flex items-center gap-2.5 mb-8">
          <span className="rblog-pulse w-2 h-2 rounded-full flex-shrink-0" style={{ background: C.red }} aria-hidden="true" />
          <Mono style={{ color: C.ink70, letterSpacing: "0.2em" }}>
            {isAr ? "الأدلّة المهنيّة — دفتر ريكو" : "Career Guides — the Rico notebook"}
          </Mono>
        </p>

        <h1
          className="font-normal tracking-[-0.02em] text-[2.4rem] leading-[1.02] sm:text-[3.6rem] sm:leading-[0.98] max-w-3xl"
          style={{ fontFamily: SERIF, color: C.ink }}
        >
          {isAr ? "أدلةٌ عمليّة لسوق العمل في الإمارات." : "Practical guides for the UAE job market."}
        </h1>

        <p className="mt-6 max-w-xl text-[1.02rem] leading-relaxed" style={{ color: C.ink70 }}>
          {isAr
            ? "أدلة في كتابة السيرة الذاتية، والبحث عن وظيفة، والاستعداد للمقابلات — محدّثة ومكتوبة خصيصاً لسوق دبي وأبوظبي وسائر الإمارات، بالعربية والإنجليزية."
            : "CV writing, job searching, and interview preparation — up-to-date advice specific to Dubai, Abu Dhabi, and the wider Emirates, in English and Arabic."}
        </p>

        <div className="mt-14 grid gap-6">
          {POSTS.map((post, idx) => (
            <Link key={post.slug} href={`/blog/${post.slug}`} className="rblog-card block group">
              <Plate className="p-6 sm:p-8">
                <div className="flex items-baseline justify-between gap-4 mb-3">
                  <Mono style={{ color: C.ink55, letterSpacing: "0.18em" }}>
                    {isAr ? `دليل ٠${idx + 1}` : `Guide 0${idx + 1}`}
                  </Mono>
                  <Mono style={{ color: C.ink55, letterSpacing: "0.18em" }}>
                    {isAr ? `${post.readingMinutes} دقائق قراءة` : `${post.readingMinutes} min read`}
                  </Mono>
                </div>
                <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:gap-8">
                  <div className="min-w-0 flex-1">
                    <h2
                      className="rblog-title text-[1.45rem] sm:text-[1.8rem] leading-snug font-medium"
                      style={{ fontFamily: SERIF, color: C.ink }}
                    >
                      {isAr ? post.title.ar : post.title.en}
                    </h2>
                    <p className="mt-3 max-w-2xl text-[0.95rem] leading-relaxed" style={{ color: C.ink70 }}>
                      {isAr ? post.description.ar : post.description.en}
                    </p>
                    <p className="mt-5">
                      <Mono style={{ color: C.red, letterSpacing: "0.18em" }}>
                        {isAr ? `اقرأ الدليل ${arrow}` : `Read the guide ${arrow}`}
                      </Mono>
                    </p>
                  </div>
                  {BLOG_COVERS[post.slug] && (
                    <div
                      className="hidden sm:block w-56 shrink-0 transition-transform duration-300 ease-out group-hover:-translate-y-1 motion-reduce:transition-none motion-reduce:group-hover:translate-y-0"
                      style={{ color: C.ink }}
                      aria-hidden="true"
                    >
                      {BLOG_COVERS[post.slug]({ className: "w-full h-auto" })}
                    </div>
                  )}
                </div>
              </Plate>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
