"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";

interface HelpContentProps {
  content: string;
}

export function HelpContent({ content }: HelpContentProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeSlug]}
      components={{
        h1: ({ children }) => <h1 className="mb-6 text-3xl font-bold text-foreground">{children}</h1>,
        // 转发 rehype-slug 生成的 id，使左侧目录锚点 <a href="#id"> 能定位到标题
        h2: ({ children, id }) => (
          <h2 id={id} className="mb-4 mt-8 border-b border-border pb-2 text-2xl font-semibold text-foreground">
            {children}
          </h2>
        ),
        h3: ({ children, id }) => (
          <h3 id={id} className="mb-3 mt-6 text-xl font-medium text-foreground">{children}</h3>
        ),
        p: ({ children }) => <p className="mb-4 leading-relaxed text-foreground">{children}</p>,
        ul: ({ children }) => <ul className="mb-4 list-disc pl-6 text-foreground">{children}</ul>,
        ol: ({ children }) => <ol className="mb-4 list-decimal pl-6 text-foreground">{children}</ol>,
        li: ({ children }) => <li className="mb-1">{children}</li>,
        a: ({ href, children }) => (
          <a href={href} className="text-teal hover:text-teal-dark hover:underline">
            {children}
          </a>
        ),
        code: ({ children }) => (
          <code className="rounded bg-muted px-1 py-0.5 font-mono text-sm text-foreground">
            {children}
          </code>
        ),
        pre: ({ children }) => (
          <pre className="mb-4 overflow-x-auto rounded-lg bg-muted p-4 font-mono text-sm">
            {children}
          </pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="mb-4 border-l-4 border-teal pl-4 italic text-muted-foreground">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <table className="mb-4 w-full border-collapse border border-border text-sm">
            {children}
          </table>
        ),
        thead: ({ children }) => <thead className="bg-muted">{children}</thead>,
        th: ({ children }) => (
          <th className="border border-border px-3 py-2 text-left font-semibold">{children}</th>
        ),
        td: ({ children }) => <td className="border border-border px-3 py-2">{children}</td>,
        img: ({ src, alt }) => (
          <img
            src={src}
            alt={alt}
            className="mb-4 max-w-full rounded-lg border border-border"
          />
        ),
        hr: () => <hr className="my-8 border-border" />,
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
