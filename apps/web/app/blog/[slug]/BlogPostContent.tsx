"use client";

import Link from "next/link";
import { useLanguage } from "@/contexts/LanguageContext";
import { atelierFraunces, atelierNaskhArabic, atelierSansArabic } from "@/components/atelier-kit/fonts";
import { ATELIER as C, ATELIER_FONT } from "@/components/atelier-kit/tokens";
import { Mono, Plate } from "@/components/atelier-kit/primitives";
import { BLOG_COVERS } from "@/components/illustrations/EditorialInk";
import { getPostBySlug } from "@/lib/blog/posts";
import { BlogMasthead, BLOG_SCOPED_CSS } from "../BlogMasthead";

const SERIF = ATELIER_FONT.serif;

export function BlogPostContent({ slug }: { slug: string }) {
  const { language } = useLanguage();
  const isAr = language === "ar";
  const post = getPostBySlug(slug);

  if (!post) return null;

  const lang = isAr ? "ar" : "en";
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
        <article className="max-w-3xl">
          <p className="flex items-center gap-2.5 mb-8">
            <span className="rblog-pulse w-2 h-2 rounded-full flex-shrink-0" style={{ background: C.red }} aria-hidden="true" />
            <Mono style={{ color: C.ink70, letterSpacing: "0.2em" }}>
              {isAr ? "دليلٌ مهنيّ" : "Career Guide"}
            </Mono>
          </p>

          <h1
            className="font-normal tracking-[-0.02em] text-[2.1rem] leading-[1.08] sm:text-[3rem] sm:leading-[1.04]"
            style={{ fontFamily: SERIF, color: C.ink }}
          >
            {post.title[lang]}
          </h1>

          <div className="mt-5 flex items-center gap-4">
            <Mono style={{ color: C.ink55, letterSpacing: "0.18em" }}>
              {isAr ? `${post.readingMinutes} دقائق قراءة` : `${post.readingMinutes} min read`}
            </Mono>
            <span className="h-px flex-1" style={{ background: C.hair }} aria-hidden="true" />
          </div>

          {BLOG_COVERS[post.slug] && (
            <div className="mt-9 max-w-md" style={{ color: C.ink }} aria-hidden="true">
              {BLOG_COVERS[post.slug]({ className: "w-full h-auto" })}
            </div>
          )}

          <div className="mt-9 space-y-4 text-[1.02rem] leading-relaxed" style={{ color: C.ink70 }}>
            {post.intro[lang].map((paragraph, idx) => (
              <p key={`intro-${idx}`}>{paragraph}</p>
            ))}
          </div>

          <div className="mt-12 space-y-12">
            {post.sections.map((section, sIdx) => (
              <section key={`section-${sIdx}`}>
                <h2
                  className="mb-4 text-[1.35rem] sm:text-[1.6rem] leading-snug font-medium"
                  style={{ fontFamily: SERIF, color: C.ink }}
                >
                  {section.heading[lang]}
                </h2>
                <div className="space-y-3 text-[0.98rem] leading-relaxed" style={{ color: C.ink70 }}>
                  {section.paragraphs?.[lang]?.map((paragraph, pIdx) => (
                    <p key={`p-${sIdx}-${pIdx}`}>{paragraph}</p>
                  ))}
                  {section.bullets && (
                    <ul className="ms-5 list-disc space-y-2.5" style={{ color: C.ink70 }}>
                      {section.bullets[lang].map((bullet, bIdx) => (
                        <li key={`b-${sIdx}-${bIdx}`}>{bullet}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </section>
            ))}
          </div>

          <div className="mt-16">
            <Plate className="p-7 sm:p-9">
              <Mono style={{ color: C.ink55, letterSpacing: "0.18em" }}>
                {isAr ? "الخطوة التالية" : "Next step"}
              </Mono>
              <p
                className="mt-3 text-[1.25rem] sm:text-[1.45rem] leading-snug font-medium"
                style={{ fontFamily: SERIF, color: C.ink }}
              >
                {isAr
                  ? "دَع ريكو يتولّى البحث والمطابقة والمتابعة نيابةً عنك."
                  : "Let Rico handle the searching, matching, and tracking for you."}
              </p>
              <div className="mt-6">
                <Link
                  href="/signup"
                  className="rblog-cta inline-flex items-center gap-2.5 px-6 py-3.5 rounded-full text-sm font-semibold"
                  style={{ background: C.ink, color: C.panel }}
                >
                  {isAr ? `أنشئ حسابك المجانيّ ${arrow}` : `Create your free account ${arrow}`}
                </Link>
              </div>
            </Plate>
          </div>

          <p className="mt-10">
            <Link href="/blog" className="rblog-nav">
              <Mono style={{ color: C.ink70, letterSpacing: "0.16em" }}>
                {isAr ? "→ كل الأدلّة" : "← All guides"}
              </Mono>
            </Link>
          </p>
        </article>
      </main>
    </div>
  );
}
