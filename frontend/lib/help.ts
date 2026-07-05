import { readFile } from "fs/promises";
import path from "path";
import Slugger from "github-slugger";

const MANUAL_PATH = path.join(process.cwd(), "public", "USER_MANUAL.md");

export async function loadUserManual(): Promise<string> {
  return readFile(MANUAL_PATH, "utf-8");
}

export function transformImagePaths(content: string): string {
  return content.replace(/\.\/help\//g, "/help/");
}

export interface Heading {
  level: number;
  text: string;
  id: string;
}

export function extractHeadings(content: string): Heading[] {
  const headings: Heading[] = [];
  const slugger = new Slugger();
  const lines = content.split("\n");

  for (const line of lines) {
    const match = line.match(/^(#{2,3})\s+(.+)$/);
    if (!match) continue;

    const level = match[1].length;
    const text = match[2].trim();
    // 使用 Slugger 实例生成唯一 id（重复标题自动追加 -1, -2 后缀）
    // 折叠连续短横线，使 "接受 / 忽略" 生成 "接受-忽略" 而非 "接受--忽略"
    const id = slugger.slug(text).replace(/-+/g, "-");

    headings.push({ level, text, id });
  }

  return headings;
}
