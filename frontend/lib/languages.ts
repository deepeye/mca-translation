// 手工镜像自 backend/app/constants/languages.py — 修改后请同步两端。

export interface LanguageInfo {
  code: string;
  labelZh: string;
  nameEn: string;
  script: string;
  direction: "ltr" | "rtl";
  affinitySphere: string | null;
}

export const LANGUAGES: LanguageInfo[] = [
  { code: "en-GB", labelZh: "英语(英)", nameEn: "English", script: "Latn", direction: "ltr", affinitySphere: "western_english" },
  { code: "de-DE", labelZh: "德语", nameEn: "German", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "ja-JP", labelZh: "日语", nameEn: "Japanese", script: "Jpan", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "es-ES", labelZh: "西班牙语", nameEn: "Spanish", script: "Latn", direction: "ltr", affinitySphere: "latin_american" },
  { code: "fr-FR", labelZh: "法语", nameEn: "French", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "ru-RU", labelZh: "俄语", nameEn: "Russian", script: "Cyrl", direction: "ltr", affinitySphere: "russian_sphere" },
  { code: "ar", labelZh: "阿拉伯语", nameEn: "Arabic", script: "Arab", direction: "rtl", affinitySphere: "islamic_middle_east" },
  { code: "ko-KR", labelZh: "韩语", nameEn: "Korean", script: "Hang", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "pt-BR", labelZh: "葡萄牙语(巴)", nameEn: "Portuguese", script: "Latn", direction: "ltr", affinitySphere: "latin_american" },
  { code: "sw-KE", labelZh: "斯瓦希里语", nameEn: "Swahili", script: "Latn", direction: "ltr", affinitySphere: "african" },
  { code: "it-IT", labelZh: "意大利语", nameEn: "Italian", script: "Latn", direction: "ltr", affinitySphere: "european_continental" },
  { code: "kk-KZ", labelZh: "哈萨克语", nameEn: "Kazakh", script: "Cyrl", direction: "ltr", affinitySphere: "russian_sphere" },
  { code: "th-TH", labelZh: "泰语", nameEn: "Thai", script: "Thai", direction: "ltr", affinitySphere: null },
  { code: "ms-MY", labelZh: "马来语", nameEn: "Malay", script: "Latn", direction: "ltr", affinitySphere: null },
  { code: "el-GR", labelZh: "希腊语", nameEn: "Greek", script: "Grek", direction: "ltr", affinitySphere: "european_continental" },
  { code: "vi-VN", labelZh: "越南语", nameEn: "Vietnamese", script: "Latn", direction: "ltr", affinitySphere: "east_asian_confucian" },
  { code: "ur-PK", labelZh: "乌尔都语", nameEn: "Urdu", script: "Arab", direction: "rtl", affinitySphere: "south_asian" },
  { code: "hi-IN", labelZh: "印地语", nameEn: "Hindi", script: "Deva", direction: "ltr", affinitySphere: "south_asian" },
];

export const LANGUAGE_LABELS: Record<string, string> = Object.fromEntries(
  LANGUAGES.map((l) => [l.code, l.labelZh]),
);

export function affinitySphereFor(code: string): string | null {
  return LANGUAGES.find((l) => l.code === code)?.affinitySphere ?? null;
}
