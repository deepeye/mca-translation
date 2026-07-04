const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface JobListItem {
  id: string;
  status: string;
  genre: string;
  target_languages: string[];
  source_text: string | null;
  created_at: string;
}

export interface DecisionLogEntry {
  id: string;
  job_id: string;
  result_id: string;
  // 决策阶段：preprocess / cultural_detect / glossary / translate / risk / suggestion / acceptance
  stage:
    | "preprocess"
    | "cultural_detect"
    | "glossary"
    | "translate"
    | "risk"
    | "suggestion"
    | "acceptance";
  decision_type: string;
  source_phrase: string | null;
  target_phrase: string | null;
  decision: string;
  reasoning: string;
  confidence: "high" | "medium" | "low" | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

// 接受度评分（audience acceptance scoring）
export type AudienceBaseline = "policy_media" | "academic" | "social_media";

export interface DimensionScores {
  audience: number;
  cultural: number;
  naturalness: number;
  risk: number;
}

export interface AcceptanceScorePayload {
  total_score: number;            // -1 失败
  dimensions: DimensionScores;
  confidence: number;
  top3_risk_indices: number[];
  audience_baseline: AudienceBaseline;
}

// 文化负载词识别结果（输入期 LLM 识别，带文本偏移）
export interface CulturalTermResult {
  term: string;
  offset: number;
  length: number;
  culture_gap: "low" | "medium" | "high";
  adaptation_strategy: string;
  suggested_rendering: string;
  reason: string;
  term_type: string;
}

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

  async put(path: string, body: unknown) {
    const res = await this.request(path, { method: "PUT", body: JSON.stringify(body) });
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

  // 输入期 LLM 文化负载词识别（隐喻/政治话语），返回带文本偏移的转译建议
  async detectCulturalTerms(body: {
    text: string;
    cultural_sphere: string;
    audience_type: string;
    genre: string;
  }): Promise<{ terms: CulturalTermResult[] }> {
    return this.post("/api/glossary/detect-cultural", body);
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

  async autoFillUserGlossaryEntry(id: string): Promise<{
    entry: Record<string, unknown>;
    filled_languages: string[];
    skipped: { code: string; reason: string }[];
  }> {
    return this.post(`/api/glossary/user-entries/${id}/auto-fill`, {});
  }

  async updateUserGlossaryEntry(id: string, body: {
    source_term?: string;
    term_type?: string;
    translations?: Record<string, { preferred: string; alternatives: string[]; notes: string }>;
    risk_notes?: string;
    applicable_genres?: string[];
  }) {
    return this.put(`/api/glossary/user-entries/${id}`, body);
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

  async exportDocx(data: {
    source_text: string;
    translated_text: string;
    risk_annotations: Array<{
      phrase: string;
      risk_level: string;
      risk_type?: string;
      explanation?: string;
    }>;
    language: string;
  }): Promise<Blob> {
    const res = await fetch(`${API_BASE}/api/export/docx`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.getToken()}`,
      },
      body: JSON.stringify(data),
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
      throw new Error(body.detail || `Export error: ${res.status}`);
    }
    return res.blob();
  }

  async listJobs(params?: { genre?: string; status?: string }): Promise<JobListItem[]> {
    const searchParams = new URLSearchParams();
    if (params?.genre) searchParams.set("genre", params.genre);
    if (params?.status) searchParams.set("status", params.status);
    const qs = searchParams.toString();
    return this.get(`/api/jobs${qs ? `?${qs}` : ""}`);
  }

  async getResultDecisions(resultId: string): Promise<DecisionLogEntry[]> {
    return this.get(`/api/results/${resultId}/decisions`);
  }

  async getJobDecisions(jobId: string): Promise<DecisionLogEntry[]> {
    return this.get(`/api/jobs/${jobId}/decisions`);
  }

  async postAcceptanceScore(
    jobId: string,
    body: { lang: string; audience_baseline: AudienceBaseline },
  ): Promise<AcceptanceScorePayload> {
    return this.post(`/api/jobs/${jobId}/acceptance-score`, body);
  }

  async postAcceptanceScoreDelta(
    jobId: string,
    body: { lang: string; risk_index: number },
  ): Promise<AcceptanceScorePayload> {
    return this.post(`/api/jobs/${jobId}/acceptance-score/delta`, body);
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
