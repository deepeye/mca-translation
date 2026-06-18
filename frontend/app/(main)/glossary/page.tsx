"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface GlossaryEntry {
  id: string;
  source_term: string;
  term_type: string;
  translations: Record<string, { preferred: string; alternatives: string[]; notes: string }>;
  risk_notes: string;
  applicable_genres: string[];
}

export default function GlossaryPage() {
  const [systemEntries, setSystemEntries] = useState<GlossaryEntry[]>([]);
  const [userEntries, setUserEntries] = useState<GlossaryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [newTerm, setNewTerm] = useState("");
  const [newTranslation, setNewTranslation] = useState("");

  async function loadEntries() {
    setLoading(true);
    try {
      const [sys, usr] = await Promise.all([
        apiClient.listGlossaryEntries(search),
        apiClient.listUserGlossaryEntries(search),
      ]);
      setSystemEntries(sys || []);
      setUserEntries(usr || []);
    } catch (err) {
      console.error("Failed to load glossary:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadEntries();
  }, [search]);

  async function handleAddUserEntry() {
    if (!newTerm.trim() || !newTranslation.trim()) return;
    try {
      await apiClient.createUserGlossaryEntry({
        source_term: newTerm.trim(),
        term_type: "user_defined",
        translations: {
          "en-GB": {
            preferred: newTranslation.trim(),
            alternatives: [],
            notes: "",
          },
        },
      });
      setNewTerm("");
      setNewTranslation("");
      loadEntries();
    } catch (err) {
      console.error("Failed to add entry:", err);
    }
  }

  async function handleDeleteUserEntry(id: string) {
    try {
      await apiClient.deleteUserGlossaryEntry(id);
      loadEntries();
    } catch (err) {
      console.error("Failed to delete entry:", err);
    }
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="mb-6 text-2xl font-bold">术语库</h1>

      <div className="mb-6 flex gap-2">
        <Input
          placeholder="搜索术语..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-sm"
        />
        {loading && <span className="text-sm text-muted-foreground">加载中...</span>}
      </div>

      <div className="mb-8 rounded-lg border border-border bg-white p-4">
        <h2 className="mb-4 text-lg font-semibold">添加自定义术语</h2>
        <div className="flex gap-2">
          <Input
            placeholder="中文术语"
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
          />
          <Input
            placeholder="英语译法"
            value={newTranslation}
            onChange={(e) => setNewTranslation(e.target.value)}
          />
          <Button onClick={handleAddUserEntry} className="bg-teal hover:bg-teal-light text-white">
            添加
          </Button>
        </div>
      </div>

      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold">用户自定义术语</h2>
        {userEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无自定义术语</p>
        ) : (
          <div className="space-y-2">
            {userEntries.map((entry) => (
              <div key={entry.id} className="flex items-center justify-between rounded border border-border p-3">
                <div>
                  <span className="font-medium">{entry.source_term}</span>
                  {entry.translations["en-GB"] && (
                    <span className="ml-2 text-sm text-teal-700">
                      → {entry.translations["en-GB"].preferred}
                    </span>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleDeleteUserEntry(entry.id)}
                  className="text-red-500 hover:text-red-700"
                >
                  删除
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">系统知识库</h2>
        {systemEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">系统知识库为空</p>
        ) : (
          <div className="space-y-2">
            {systemEntries.map((entry) => (
              <div key={entry.id} className="rounded border border-border p-3">
                <span className="font-medium">{entry.source_term}</span>
                <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                  {entry.term_type}
                </span>
                {entry.translations["en-GB"] && (
                  <div className="mt-1 text-sm text-teal-700">
                    英语：{entry.translations["en-GB"].preferred}
                  </div>
                )}
                {entry.risk_notes && (
                  <div className="mt-1 text-xs text-orange-600">⚠ {entry.risk_notes}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
