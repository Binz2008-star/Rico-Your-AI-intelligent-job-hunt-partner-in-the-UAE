import type { Metadata } from "next";
import { JsonLd } from "@/components/seo/JsonLd";
import { FAQContent } from "./FAQContent";

export const metadata: Metadata = {
  title: "FAQ | Rico Hunt",
  description: "Frequently asked questions about Rico Hunt — where jobs come from, how AI matching works, what data we store, and how applications are handled.",
};

// FAQPage structured data — mirrors the questions rendered in FAQContent so
// Google can surface rich results. Answers are concise, faithful summaries.
const faqStructuredData = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: [
    {
      "@type": "Question",
      name: "Where do the jobs on Rico Hunt come from?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Rico Hunt sources live job listings using the JSearch API (powered by RapidAPI), which aggregates real-time job data from major job boards active in the UAE and GCC — including LinkedIn, Indeed, Glassdoor, and Bayt. Listings are filtered and scored against your CV and career profile.",
      },
    },
    {
      "@type": "Question",
      name: "Does Rico guarantee I will get a job?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. Rico Hunt is a job search tool — not an employment agency, recruiter, or placement service. We help you discover relevant roles, manage applications, and improve your strategy, but interview and offer outcomes depend entirely on the employer.",
      },
    },
    {
      "@type": "Question",
      name: "Are the job listings verified or accurate?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Rico Hunt displays job data from third-party providers and cannot independently verify the accuracy, availability, or legitimacy of every posting. Always verify job details directly — employer, role, salary, location, visa requirements, and application process — before applying.",
      },
    },
    {
      "@type": "Question",
      name: "Can Rico's AI make mistakes?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Yes. Rico uses AI for CV analysis, job matching, and career guidance. AI outputs can contain errors or outdated information, and match scores are estimates — not guarantees of fit. Use AI insights as one input among many and review roles yourself.",
      },
    },
    {
      "@type": "Question",
      name: "Will Rico apply to jobs without my permission?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. Rico Hunt never submits a job application on your behalf without your explicit confirmation. Every application action requires your approval before it proceeds.",
      },
    },
    {
      "@type": "Question",
      name: "Is Rico Hunt a recruitment agency?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "No. Rico Hunt is a software platform, not an employer, staffing agency, or recruitment agency. We do not represent employers, negotiate offers, or place candidates — we are a tool to help you run your own job search more effectively.",
      },
    },
    {
      "@type": "Question",
      name: "What data does Rico store about me?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Rico may store your account details, uploaded CV, parsed CV content, career preferences, chat messages, and job activity to personalise your experience and power job matching. We do not sell your personal data, and you can request deletion at any time by emailing info@ricohunt.com.",
      },
    },
    {
      "@type": "Question",
      name: "Who operates Rico Hunt?",
      acceptedAnswer: {
        "@type": "Answer",
        text: "Rico Hunt is operated by Eco Technology Environment Protection Services L.L.C, a company registered in the United Arab Emirates. For questions or support, contact info@ricohunt.com or message us on WhatsApp.",
      },
    },
  ],
};

export default function FAQPage() {
  return (
    <>
      <JsonLd data={faqStructuredData} />
      <FAQContent />
    </>
  );
}
