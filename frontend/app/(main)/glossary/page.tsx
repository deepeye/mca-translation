"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DEFAULT_TERM_TYPE_LABEL,
  SYSTEM_GLOSSARY_TERM_TYPE_LABELS,
  SYSTEM_GLOSSARY_TERM_TYPE_ORDER,
} from "@/lib/glossary-categories";

interface GlossaryEntry {
  id: string;
  source_term: string;
  term_type: string;
  translations: Record<string, { preferred: string; alternatives: string[]; notes: string }>;
  risk_notes: string;
  applicable_genres: string[];
}

interface EditingEntry {
  id: string;
  source_term: string;
  translation: string;
  risk_notes: string;
}

const USER_PAGE_SIZE = 10;

export default function GlossaryPage() {
  const [systemEntries, setSystemEntries] = useState<GlossaryEntry[]>([]);
  const [userEntries, setUserEntries] = useState<GlossaryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [newTerm, setNewTerm] = useState("");
  const [newTranslation, setNewTranslation] = useState("");

  // User entries pagination
  const [userOffset, setUserOffset] = useState(0);
  const [hasMoreUser, setHasMoreUser] = useState(false);

  async function loadEntries() {
    setLoading(true);
    try {
      const [sys, usr] = await Promise.all([
        apiClient.listGlossaryEntries(search),
        apiClient.listUserGlossaryEntries(search, userOffset, USER_PAGE_SIZE),
      ]);
      setSystemEntries(sys || []);
      setUserEntries(usr || []);
      setHasMoreUser((usr || []).length >= USER_PAGE_SIZE);
    } catch (err) {
      console.error("Failed to load glossary:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setUserOffset(0);
  }, [search]);

  useEffect(() => {
    loadEntries();
  }, [search, userOffset]);

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
      setUserOffset(0);
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

  const userPageNum = Math.floor(userOffset / USER_PAGE_SIZE) + 1;
  const [editingEntry, setEditingEntry] = useState<EditingEntry | null>(null);

  function startEdit(entry: GlossaryEntry) {
    setEditingEntry({
      id: entry.id,
      source_term: entry.source_term,
      translation: entry.translations["en-GB"]?.preferred || "",
      risk_notes: entry.risk_notes || "",
    });
  }

  function cancelEdit() {
    setEditingEntry(null);
  }

  async function handleEditSave() {
    if (!editingEntry) return;
    try {
      await apiClient.updateUserGlossaryEntry(editingEntry.id, {
        source_term: editingEntry.source_term.trim(),
        translations: {
          "en-GB": {
            preferred: editingEntry.translation.trim(),
            alternatives: [],
            notes: "",
          },
        },
        risk_notes: editingEntry.risk_notes.trim(),
      });
      setEditingEntry(null);
      loadEntries();
    } catch (err) {
      console.error("Failed to update entry:", err);
    }
  }
  const groupedSystemEntries = Object.entries(
    systemEntries.reduce<Record<string, GlossaryEntry[]>>((groups, entry) => {
      const key = entry.term_type || "other_specialized";
      groups[key] = groups[key] ? [...groups[key], entry] : [entry];
      return groups;
    }, {}),
  ).sort(([a], [b]) => {
    const aIndex = SYSTEM_GLOSSARY_TERM_TYPE_ORDER.indexOf(a as (typeof SYSTEM_GLOSSARY_TERM_TYPE_ORDER)[number]);
    const bIndex = SYSTEM_GLOSSARY_TERM_TYPE_ORDER.indexOf(b as (typeof SYSTEM_GLOSSARY_TERM_TYPE_ORDER)[number]);
    return (aIndex === -1 ? Number.MAX_SAFE_INTEGER : aIndex) - (bIndex === -1 ? Number.MAX_SAFE_INTEGER : bIndex);
  });

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
          <>
            <div className="space-y-2">
              {userEntries.map((entry) => (
                <div key={entry.id} className="rounded border border-border p-3">
                  {editingEntry?.id === entry.id ? (
                    /* Inline edit mode */
                    <div className="space-y-2">
                      <Input
                        value={editingEntry.source_term}
                        onChange={(e) => setEditingEntry({ ...editingEntry, source_term: e.target.value })}
                        placeholder="中文术语"
                      />
                      <Input
                        value={editingEntry.translation}
                        onChange={(e) => setEditingEntry({ ...editingEntry, translation: e.target.value })}
                        placeholder="英语译法"
                      />
                      <Input
                        value={editingEntry.risk_notes}
                        onChange={(e) => setEditingEntry({ ...editingEntry, risk_notes: e.target.value })}
                        placeholder="风险备注（可选）"
                      />
                      <div className="flex gap-2">
                        <Button onClick={handleEditSave} size="sm" className="bg-teal hover:bg-teal-light text-white">
                          保存
                        </Button>
                        <Button onClick={cancelEdit} variant="outline" size="sm">
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    /* Display mode */
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-medium">{entry.source_term}</span>
                        {entry.translations["en-GB"] && (
                          <span className="ml-2 text-sm text-teal-700">
                            → {entry.translations["en-GB"].preferred}
                          </span>
                        )}
                        {entry.risk_notes && (
                          <span className="ml-2 text-xs text-orange-600">⚠ {entry.risk_notes}</span>
                        )}
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => startEdit(entry)}
                          className="text-muted-foreground hover:text-foreground"
                        >
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteUserEntry(entry.id)}
                          className="text-red-500 hover:text-red-700"
                        >
                          删除
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="mt-4 flex items-center justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUserOffset((p) => Math.max(0, p - USER_PAGE_SIZE))}
                disabled={userOffset === 0}
              >
                上一页
              </Button>
              <span className="text-sm text-muted-foreground">第 {userPageNum} 页</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setUserOffset((p) => p + USER_PAGE_SIZE)}
                disabled={!hasMoreUser}
              >
                下一页
              </Button>
            </div>
          </>
        )}
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">系统知识库</h2>
        {systemEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">系统知识库为空</p>
        ) : (
          <div className="space-y-6">
            {groupedSystemEntries.map(([termType, entries]) => (
              <section key={termType}>
                <h3 className="mb-3 text-base font-semibold text-teal-800">
                  {SYSTEM_GLOSSARY_TERM_TYPE_LABELS[termType] || DEFAULT_TERM_TYPE_LABEL}
                </h3>
                <div className="space-y-2">
                  {entries.map((entry) => (
                    <div key={entry.id} className="rounded border border-border p-3">
                      <span className="font-medium">{entry.source_term}</span>
                      <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                        {SYSTEM_GLOSSARY_TERM_TYPE_LABELS[entry.term_type] || DEFAULT_TERM_TYPE_LABEL}
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
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
