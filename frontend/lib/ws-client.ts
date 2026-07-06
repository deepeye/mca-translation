import { BASE_PATH } from "@/lib/base-path";

// 纯函数:推导 WebSocket 基址,便于单测协议/前缀逻辑。
// - wsUrl 注入时优先(dev 直连后端);否则按页面协议选 wss/ws,并拼 BASE_PATH。
export function buildWsBase(
  wsUrl: string | undefined,
  protocol: string,
  host: string,
  basePath: string = BASE_PATH,
): string {
  if (wsUrl) return wsUrl;
  if (!protocol || !host) return "";
  const scheme = protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${host}${basePath}`;
}

// 未注入时从当前页 host 推导,走 nginx 同源代理(生产);dev 由 .env.local 注入 ws://localhost:8000
const WS_BASE =
  typeof window !== "undefined"
    ? buildWsBase(process.env.NEXT_PUBLIC_WS_URL, window.location.protocol, window.location.host)
    : process.env.NEXT_PUBLIC_WS_URL || "";

export class WsClient {
  private ws: WebSocket | null = null;

  connect(jobId: string, onMessage: (data: unknown) => void) {
    this.disconnect();
    this.ws = new WebSocket(`${WS_BASE}/api/ws/jobs/${jobId}`);
    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch { /* ignore non-JSON */ }
    };
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WsClient();
