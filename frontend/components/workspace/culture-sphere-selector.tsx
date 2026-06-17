"use client";

import { CulturalSphere, useWorkspaceStore } from "@/stores/workspace-store";
import { isLiteralMode } from "@/lib/translation-conflicts";

const SPHERES: { value: CulturalSphere; label: string; tip: string }[] = [
  { value: "western_english", label: "欧美英语圈", tip: "美国、英国、加拿大、澳大利亚" },
  { value: "european_continental", label: "欧洲大陆", tip: "德国、法国、意大利、北欧" },
  { value: "islamic_middle_east", label: "伊斯兰中东", tip: "沙特、阿联酋、伊朗、埃及" },
  { value: "east_asian_confucian", label: "东亚儒家", tip: "日本、韩国" },
  { value: "latin_american", label: "拉美", tip: "巴西、墨西哥、阿根廷" },
  { value: "russian_sphere", label: "俄语圈", tip: "俄罗斯、中亚" },
  { value: "south_asian", label: "南亚", tip: "印度、巴基斯坦、孟加拉" },
  { value: "african", label: "非洲", tip: "南非、尼日利亚、肯尼亚" },
];

export function CultureSphereSelector() {
  const sphere = useWorkspaceStore((s) => s.input.culturalSphere);
  const strategy = useWorkspaceStore((s) => s.input.strategy);
  const setSphere = useWorkspaceStore((s) => s.setCulturalSphere);
  const current = SPHERES.find((s) => s.value === sphere) ?? SPHERES[0];
  const literalMode = isLiteralMode(strategy);

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <span className="shrink-0">文化圈</span>
      <div className={`flex items-center gap-2 ${literalMode ? "opacity-50 pointer-events-none" : ""}`}>
        <select
          value={sphere}
          onChange={(e) => setSphere(e.target.value as CulturalSphere)}
          title={current.tip}
          className="cursor-pointer rounded border border-border bg-white px-2 py-1 text-xs text-foreground transition-all duration-200 active:scale-[0.95]"
        >
          {SPHERES.map((s) => (
            <option key={s.value} value={s.value} title={s.tip}>
              {s.label}
            </option>
          ))}
        </select>
        <span className="text-[11px] text-muted-foreground/70">{current.tip}</span>
      </div>
      {literalMode && (
        <span className="text-[11px] text-muted-foreground">直译参考模式下不进行文化适配</span>
      )}
    </div>
  );
}
