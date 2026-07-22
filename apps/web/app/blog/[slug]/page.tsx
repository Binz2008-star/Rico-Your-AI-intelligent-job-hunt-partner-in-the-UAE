import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Script from "next/script";
import { POSTS, getPostBySlug } from "@/lib/blog/posts";
import { BlogPostContent } from "./BlogPostContent";

const SITE_URL = "https://ricohunt.com";

interface BlogPostPageProps {
  params: { slug: string };
}

export function generateStaticParams() {
  return POSTS.map((post) => ({ slug: post.slug }));
}

export function generateMetadata({ params }: BlogPostPageProps): Metadata {
  const post = getPostBySlug(params.slug);
  if (!post) return {};

  return {
    title: post.title.en,
    description: post.description.en,
    keywords: post.keywords,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      title: post.title.en,
      description: post.description.en,
      url: `${SITE_URL}/blog/${post.slug}`,
      type: "article",
      publishedTime: post.datePublished,
      modifiedTime: post.dateModified,
      siteName: "Rico Hunt",
    },
    twitter: {
      card: "summary_large_image",
      title: post.title.en,
      description: post.description.en,
    },
  };
}

export default function BlogPostPage({ params }: BlogPostPageProps) {
  const post = getPostBySlug(params.slug);
  if (!post) notFound();

  const articleJsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    "@id": `${SITE_URL}/blog/${post.slug}#article`,
    headline: post.title.en,
    alternativeHeadline: post.title.ar,
    description: post.description.en,
    datePublished: post.datePublished,
    dateModified: post.dateModified,
    inLanguage: ["en", "ar"],
    author: {
      "@type": "Organization",
      name: "Rico Hunt",
      url: SITE_URL,
    },
    publisher: { "@id": `${SITE_URL}/#organization` },
    mainEntityOfPage: `${SITE_URL}/blog/${post.slug}`,
    keywords: post.keywords.join(", "),
  };

  return (
    <>
      <Script
        id={`json-ld-article-${post.slug}`}
        type="application/ld+json"
        strategy="beforeInteractive"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleJsonLd) }}
      />
      <BlogPostContent slug={post.slug} />
    </>
  );
}
