const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== "undefined") {
      localStorage.setItem("token", token);
    }
  }

  getToken(): string | null {
    if (this.token) return this.token;
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("token");
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== "undefined") {
      localStorage.removeItem("token");
    }
  }

  private async request(path: string, options: RequestInit = {}) {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `API error: ${res.status}`);
    }
    return res;
  }

  async post(path: string, body: unknown) {
    const res = await this.request(path, { method: "POST", body: JSON.stringify(body) });
    return res.json();
  }

  async postReview(body: {
    mode: "dual" | "single";
    source_text?: string;
    translated_text: string;
    target_language: string;
    cultural_sphere?: string;
    audience_type?: string;
  }) {
    return this.post("/api/reviews", body);
  }

  async detectTerms(text: string) {
    return this.post("/api/glossary/detect", { text });
  }

  async listGlossaryEntries(q?: string) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/api/glossary/entries${query}`);
  }

  async createGlossaryEntry(body: {
    source_term: string;
    term_type: string;
    translations: Record<string, { preferred: string; alternatives: string[]; notes: string }>;
    risk_notes?: string;
    applicable_genres?: string[];
  }) {
    return this.post("/api/glossary/entries", body);
  }

  async deleteGlossaryEntry(id: string) {
    return this.delete(`/api/glossary/entries/${id}`);
  }

  async listUserGlossaryEntries(q?: string, offset?: number, limit?: number) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (offset !== undefined) params.set("offset", String(offset));
    if (limit !== undefined) params.set("limit", String(limit));
    const query = params.toString() ? `?${params.toString()}` : "";
    return this.get(`/api/glossary/user-entries${query}`);
  }

  async createUserGlossaryEntry(body: {
    source_term: string;
    term_type: string;
    translations: Record<string, { preferred: string; alternatives: string[]; notes: string }>;
    risk_notes?: string;
    applicable_genres?: string[];
  }) {
    return this.post("/api/glossary/user-entries", body);
  }

  async deleteUserGlossaryEntry(id: string) {
    return this.delete(`/api/glossary/user-entries/${id}`);
  }

  async uploadFile(file: File): Promise<{
    file_id: string;
    filename: string;
    size: number;
    text_content: string;
  }> {
    const formData = new FormData();
    formData.append("file", file);

    const headers: Record<string, string> = {};
    const token = this.getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    // Do NOT set Content-Type: fetch auto-sets with boundary for FormData

    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      headers,
      body: formData,
    });
    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Unauthorized");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload error: ${res.status}`);
    }
    return res.json();
  }

  async get(path: string) {
    const res = await this.request(path, { method: "GET" });
    return res.json();
  }

  async delete(path: string) {
    await this.request(path, { method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
