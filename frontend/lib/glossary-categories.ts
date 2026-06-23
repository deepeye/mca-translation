export const SYSTEM_GLOSSARY_TERM_TYPE_LABELS: Record<string, string> = {
  political_discourse: "政治话语",
  institution_event: "机构会议",
  texts_documents: "文本文献",
  historical_culture: "历史文化",
  cultural_site: "文化地标",
  food_cuisine: "饮食特产",
  material_craft_medicine: "工艺医药物产",
  geography_place: "地理地点",
  other_specialized: "其他专名",
  cultural_metaphor: "文化隐喻",
  idiom: "成语习语",
};

export const SYSTEM_GLOSSARY_TERM_TYPE_ORDER = [
  "political_discourse",
  "institution_event",
  "texts_documents",
  "historical_culture",
  "cultural_site",
  "food_cuisine",
  "material_craft_medicine",
  "geography_place",
  "other_specialized",
  "cultural_metaphor",
  "idiom",
] as const;

export const TERM_TYPE_BADGE_CLASS: Record<string, string> = {
  political_discourse: "bg-blue-100 text-blue-700",
  institution_event: "bg-violet-100 text-violet-700",
  texts_documents: "bg-slate-100 text-slate-700",
  historical_culture: "bg-amber-100 text-amber-700",
  cultural_site: "bg-emerald-100 text-emerald-700",
  food_cuisine: "bg-rose-100 text-rose-700",
  material_craft_medicine: "bg-cyan-100 text-cyan-700",
  geography_place: "bg-green-100 text-green-700",
  other_specialized: "bg-zinc-100 text-zinc-700",
  cultural_metaphor: "bg-orange-100 text-orange-700",
  idiom: "bg-orange-100 text-orange-700",
};

export const DEFAULT_TERM_TYPE_LABEL = "其他专名";
export const DEFAULT_TERM_TYPE_BADGE_CLASS = "bg-zinc-100 text-zinc-700";
