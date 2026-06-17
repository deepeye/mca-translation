import type { Genre, Strategy } from "@/stores/workspace-store";

/**
 * 直译参考策略的标识。选中该策略 = 纯直译模式,不做文化适配。
 */
export const LITERAL_MODE_STRATEGY: Strategy = "literal_reference";

/**
 * 是否处于纯直译模式。该模式下禁用文化圈/受众选择器,且后端请求
 * 会把 cultural_sphere / audience_type 传 null(后端跳过 preprocess,
 * 不注入 <cultural_constraints> 块,system prompt 自洽)。
 */
export function isLiteralMode(strategy: Strategy): boolean {
  return strategy === LITERAL_MODE_STRATEGY;
}

/**
 * 给定当前策略,返回被禁用的文体。
 * 规则:literal_reference 与 brand(品牌传播)互斥——
 * "最小化适配" 与品牌文体所需的创意本地化方向相反。
 */
export function getDisabledGenres(strategy: Strategy): Genre[] {
  return isLiteralMode(strategy) ? ["brand"] : [];
}

/**
 * 给定当前文体,返回被禁用的策略(规则 1 的反向)。
 * brand 文体下不可选 literal_reference。
 */
export function getDisabledStrategies(genre: Genre): Strategy[] {
  return genre === "brand" ? ["literal_reference"] : [];
}
