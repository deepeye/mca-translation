const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

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
