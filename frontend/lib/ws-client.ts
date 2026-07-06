// 未注入时从当前页 host 推导，走 nginx 同源代理（生产）；dev 由 .env.local 注入 ws://localhost:8000
const WS_BASE =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined" ? `ws://${window.location.host}` : "");

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
