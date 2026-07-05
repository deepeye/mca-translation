import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { HelpContent } from "@/components/help/help-content";
import { ScrollToTopButton } from "@/components/help/scroll-to-top-button";
import { loadUserManual, transformImagePaths, extractHeadings } from "@/lib/help";

export default async function HelpPage() {
  const rawContent = await loadUserManual();
  const content = transformImagePaths(rawContent);
  const headings = extractHeadings(rawContent);

  return (
    <div className="flex">
      <aside className="sticky top-0 h-fit max-h-screen w-64 shrink-0 overflow-y-auto border-r border-border bg-card p-4">
        <div className="mb-4 flex items-center gap-2">
          <Link
            href="/workspace"
            className="flex items-center gap-1 text-sm text-teal hover:text-teal-dark"
          >
            <ArrowLeft className="h-4 w-4" />
            返回工作台
          </Link>
        </div>
        <h2 className="mb-3 text-sm font-semibold text-muted-foreground">目录</h2>
        <nav className="space-y-1">
          {headings.map((h) => (
            <a
              key={h.id}
              href={`#${h.id}`}
              className={`block rounded px-2 py-1 text-sm hover:bg-muted ${
                h.level === 3 ? "pl-5 text-muted-foreground" : "font-medium text-foreground"
              }`}
            >
              {h.text}
            </a>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8">
        <div className="mx-auto max-w-3xl">
          <HelpContent content={content} />
        </div>
        <ScrollToTopButton />
      </main>
    </div>
  );
}
