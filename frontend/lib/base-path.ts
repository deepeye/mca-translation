// 应用前缀:prod=/mca,dev 留空。由 NEXT_PUBLIC_BASE_PATH 构建期注入,
// 作为 basePath / API / WS / login 跳转前缀的唯一真相源。
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

// 登录跳转路径。window.location.href 是浏览器原生 API,不受 Next.js basePath 自动加前缀,需手动拼接。
export function loginPath(basePath: string = BASE_PATH): string {
  return `${basePath}/login`;
}
