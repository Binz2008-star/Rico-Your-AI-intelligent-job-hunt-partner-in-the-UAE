"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

const md: Components = {
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  ),
  h1: ({ children }) => (
    <h1 className="text-[16px] font-bold mb-2 mt-4 first:mt-0 text-[var(--rico-fg-1)]">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-[15px] font-bold mb-2 mt-3 first:mt-0 text-[var(--rico-fg-1)]">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-[14px] font-semibold mb-1 mt-3 first:mt-0 text-[var(--rico-fg-1)]">
      {children}
    </h3>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-[var(--rico-fg-1)]">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic opacity-80">{children}</em>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 pl-4 space-y-0.5 list-disc list-outside">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 pl-4 space-y-0.5 list-decimal list-outside">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  // react-markdown v8 passes `inline` boolean to distinguish inline vs block code
  code: ({ inline, className, children, ...props }: any) => {
    if (inline) {
      return (
        <code
          className="px-1.5 py-0.5 rounded text-[12px] font-mono bg-[rgba(255,255,255,0.08)] text-[var(--rico-fg-1)] border border-[rgba(255,255,255,0.07)]"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code
        className={`font-mono text-[12px] text-[var(--rico-fg-2)] block ${className ?? ""}`}
        {...props}
      >
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mb-3 mt-1 rounded-lg bg-[rgba(0,0,0,0.45)] border border-[rgba(255,255,255,0.06)] p-3 overflow-x-auto text-[12px] leading-relaxed">
      {children}
    </pre>
  ),
  a: ({ href, children }) => {
    const safe = href && (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:"))
      ? href
      : "#";
    return (
      <a
        href={safe}
        target="_blank"
        rel="noopener noreferrer"
        className="text-[var(--rico-primary)] underline underline-offset-2 hover:opacity-75 transition-opacity"
      >
        {children}
      </a>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-[var(--rico-primary-container)] pl-3 my-2 opacity-75 italic">
      {children}
    </blockquote>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-[rgba(255,255,255,0.07)]">
      <table className="w-full text-[13px] border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-[rgba(255,255,255,0.04)]">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b border-[rgba(255,255,255,0.06)] last:border-b-0">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-semibold text-[var(--rico-fg-1)] border-r border-[rgba(255,255,255,0.06)] last:border-r-0 whitespace-nowrap">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-[var(--rico-fg-2)] border-r border-[rgba(255,255,255,0.06)] last:border-r-0">
      {children}
    </td>
  ),
  hr: () => <hr className="my-3 border-[rgba(255,255,255,0.08)]" />,
};

interface RicoMarkdownContentProps {
  children: string;
}

export function RicoMarkdownContent({ children }: RicoMarkdownContentProps) {
  return (
    <div className="whitespace-normal text-[14px] leading-relaxed text-[var(--rico-fg-2)]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={md} skipHtml>
        {children}
      </ReactMarkdown>
    </div>
  );
}
