"use client";

import { ChevronUp } from "lucide-react";

export function ScrollToTopButton() {
  return (
    <button
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className="fixed bottom-6 right-6 flex items-center gap-1 rounded-full bg-teal px-3 py-2 text-sm text-white shadow-lg hover:bg-teal-dark"
    >
      <ChevronUp className="h-4 w-4" />
      回到顶部
    </button>
  );
}
