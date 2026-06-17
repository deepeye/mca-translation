"use client";

import { useReviewStore } from "@/stores/review-store";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";

const AVAILABLE_LANGUAGES = [
  { code: "en-GB", label: "英语(英)" },
  { code: "de-DE", label: "德语" },
  { code: "ja-JP", label: "日语" },
  { code: "es-ES", label: "西班牙语" },
  { code: "fr-FR", label: "法语" },
];

const GENRES = [
  { value: "political", label: "政治话语" },
  { value: "news", label: "新闻稿" },
  { value: "policy", label: "政策文件" },
  { value: "brand", label: "品牌传播" },
];

const SPHERES = [
  { value: "western_english", label: "欧美英语圈" },
  { value: "european_continental", label: "欧洲大陆" },
  { value: "islamic_middle_east", label: "伊斯兰中东" },
  { value: "east_asian_confucian", label: "东亚儒家" },
  { value: "latin_american", label: "拉美" },
  { value: "russian_sphere", label: "俄语圈" },
  { value: "south_asian", label: "南亚" },
  { value: "african", label: "非洲" },
];

const AUDIENCES = [
  { value: "general_public", label: "公众" },
  { value: "media", label: "媒体" },
  { value: "government", label: "政府" },
  { value: "academic", label: "学术" },
  { value: "business", label: "企业" },
  { value: "diaspora_chinese", label: "海外华人" },
];

export function ReviewInputPanel() {
  const store = useReviewStore();

  async function handleSubmit() {
    if (!store.translatedText.trim()) return;
    if (store.mode === "dual" && !store.sourceText.trim()) return;

    store.setIsLoading(true);
    store.setError(null);
    store.setResult(null);

    try {
      const data = await apiClient.postReview({
        mode: store.mode,
        source_text: store.mode === "dual" ? store.sourceText : undefined,
        translated_text: store.translatedText,
        target_language: store.targetLanguage,
        genre: store.genre,
        cultural_sphere: store.culturalSphere,
        audience_type: store.audienceType,
      });
      store.setResult(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "审校请求失败";
      store.setError(message);
    } finally {
      store.setIsLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-3 rounded-md border border-border bg-white p-4">
      <h2 className="text-sm font-semibold text-foreground">审校输入</h2>

      {/* Mode selector */}
      <div className="flex gap-3 text-xs">
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="review-mode"
            checked={store.mode === "dual"}
            onChange={() => store.setMode("dual")}
            className="h-3.5 w-3.5 accent-teal"
          />
          <span>对照审校</span>
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="radio"
            name="review-mode"
            checked={store.mode === "single"}
            onChange={() => store.setMode("single")}
            className="h-3.5 w-3.5 accent-teal"
          />
          <span>独立诊断</span>
        </label>
      </div>

      {/* Source text */}
      <div className={store.mode === "single" ? "hidden" : "flex flex-col gap-1"}>
        <label className="text-xs font-medium text-muted-foreground">原文（中文）</label>
        <textarea
          value={store.sourceText}
          onChange={(e) => store.setSourceText(e.target.value)}
          placeholder="粘贴中文原文..."
          className="h-32 resize-none rounded-md border border-border bg-white p-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-teal focus:outline-none"
        />
      </div>

      {/* Translated text */}
      <div className="flex flex-col gap-1">
        <label className="text-xs font-medium text-muted-foreground">译文（目标语言）</label>
        <textarea
          value={store.translatedText}
          onChange={(e) => store.setTranslatedText(e.target.value)}
          placeholder="粘贴外文译文..."
          className="h-40 resize-none rounded-md border border-border bg-white p-2.5 text-sm leading-relaxed text-foreground placeholder:text-muted-foreground focus:border-teal focus:outline-none"
        />
      </div>

      {/* Parameters */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">目标语言</span>
          <select
            value={store.targetLanguage}
            onChange={(e) => store.setTargetLanguage(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {AVAILABLE_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">文体</span>
          <select
            value={store.genre}
            onChange={(e) => store.setGenre(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {GENRES.map((g) => (
              <option key={g.value} value={g.value}>{g.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">文化圈</span>
          <select
            value={store.culturalSphere}
            onChange={(e) => store.setCulturalSphere(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {SPHERES.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-muted-foreground shrink-0">受众</span>
          <select
            value={store.audienceType}
            onChange={(e) => store.setAudienceType(e.target.value)}
            className="rounded border border-border bg-white px-2 py-1 text-xs text-foreground"
          >
            {AUDIENCES.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Error */}
      {store.error && (
        <div className="rounded bg-red-50 px-3 py-2 text-xs text-red-600">
          {store.error}
        </div>
      )}

      {/* Submit */}
      <Button
        onClick={handleSubmit}
        disabled={store.isLoading || !store.translatedText.trim()}
        className="mt-auto h-9 text-sm"
      >
        {store.isLoading ? "审校中..." : "开始审校"}
      </Button>
    </div>
  );
}
