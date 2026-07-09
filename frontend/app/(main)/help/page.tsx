import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { HelpContent } from "@/components/help/help-content";
import { ScrollToTopButton } from "@/components/help/scroll-to-top-button";
import { loadUserManual, extractHeadings } from "@/lib/help";

export default async function HelpPage() {
  const rawContent = await loadUserManual();
  const headings = extractHeadings(rawContent);

  return (
    <div>
      {/* 顶部标题栏：返回链接 + 页面标题，跨全宽 */}
      <div className="flex items-center gap-4 border-b border-border bg-card px-6 py-3">
        <Link
          href="/workspace"
          className="flex items-center gap-1 text-sm text-teal hover:text-teal-dark"
        >
          <ArrowLeft className="h-4 w-4" />
          返回工作台
        </Link>
        <h1 className="text-base font-semibold text-foreground">CulturalBridge 使用手册</h1>
      </div>
      <div className="flex">
        <aside className="sticky top-0 h-fit max-h-screen w-64 shrink-0 overflow-y-auto border-r border-border bg-card p-4">
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
            <HelpContent content={rawContent} />
          </div>
          <ScrollToTopButton />
        </main>
      </div>
    </div>
  );
}
