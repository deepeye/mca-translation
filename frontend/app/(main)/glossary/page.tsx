"use client";

import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LANGUAGE_LABELS } from "@/lib/languages";
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

interface TranslationFormEntry {
  preferred: string;
  alternatives: string[];
  notes: string;
}

interface EntryForm {
  source_term: string;
  term_type: string;
  risk_notes: string;
  applicable_genres: string[];
  translations: Record<string, TranslationFormEntry>;
}

const USER_PAGE_SIZE = 10;

export default function GlossaryPage() {
  const [systemEntries, setSystemEntries] = useState<GlossaryEntry[]>([]);
  const [userEntries, setUserEntries] = useState<GlossaryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  // Create form state
  const [form, setForm] = useState<EntryForm>({
    source_term: "",
    term_type: "user_defined",
    risk_notes: "",
    applicable_genres: [],
    translations: {
      "en-GB": { preferred: "", alternatives: [], notes: "" },
    },
  });
  const [showLangDropdown, setShowLangDropdown] = useState(false);
  const [addLangCode, setAddLangCode] = useState("de-DE");

  // Edit form state
  const [editingEntryId, setEditingEntryId] = useState<string | null>(null);
  const [editingForm, setEditingForm] = useState<EntryForm | null>(null);
  const [showEditLangDropdown, setShowEditLangDropdown] = useState(false);
  const [editAddLangCode, setEditAddLangCode] = useState("de-DE");
  const [autoFilling, setAutoFilling] = useState(false);

  // Validation
  const [formError, setFormError] = useState("");

  // Auto-fill feedback
  const [autoFillMsg, setAutoFillMsg] = useState<string | null>(null);

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

  // ---- Helpers ----

  function getPreferredTranslation(entry: GlossaryEntry): string | null {
    if (entry.translations["en-GB"]?.preferred) {
      return entry.translations["en-GB"].preferred;
    }
    for (const [, t] of Object.entries(entry.translations)) {
      if (t.preferred) return t.preferred;
    }
    return null;
  }

  function getFilledCount(entry: GlossaryEntry): number {
    return Object.entries(entry.translations).filter(
      ([code, t]) => code !== "en-GB" && (t.preferred || t.alternatives.length > 0 || t.notes),
    ).length;
  }

  function getFilledLanguageLabels(entry: GlossaryEntry): string {
    return Object.entries(entry.translations)
      .filter(([code, t]) => code !== "en-GB" && (t.preferred || t.alternatives.length > 0 || t.notes))
      .map(([code]) => LANGUAGE_LABELS[code] || code)
      .join(", ");
  }

  function getNextAvailable(existing: Record<string, unknown>): string {
    return Object.keys(LANGUAGE_LABELS).find((c) => !existing[c]) || "de-DE";
  }

  // ---- Create form handlers ----

  function handleAddLanguage() {
    if (form.translations[addLangCode]) return;
    setForm((f) => ({
      ...f,
      translations: {
        ...f.translations,
        [addLangCode]: { preferred: "", alternatives: [], notes: "" },
      },
    }));
    setAddLangCode(getNextAvailable({ ...form.translations, [addLangCode]: true }));
    // keep dropdown open so user can add more
  }

  function handleRemoveLanguage(code: string) {
    if (code === "en-GB") return;
    setForm((f) => ({
      ...f,
      translations: Object.fromEntries(Object.entries(f.translations).filter(([c]) => c !== code)),
    }));
  }

  async function handleSaveNew() {
    if (!form.source_term.trim()) return;
    const hasTranslation = Object.values(form.translations).some((t) => t.preferred.trim());
    if (!hasTranslation) {
      setFormError("请至少填写一种译法的首选译法");
      return;
    }
    setFormError("");
    try {
      await apiClient.createUserGlossaryEntry({
        source_term: form.source_term.trim(),
        term_type: form.term_type,
        translations: form.translations,
        risk_notes: form.risk_notes,
        applicable_genres: form.applicable_genres,
      });
      setForm({
        source_term: "",
        term_type: "user_defined",
        risk_notes: "",
        applicable_genres: [],
        translations: { "en-GB": { preferred: "", alternatives: [], notes: "" } },
      });
      setShowLangDropdown(false);
      setAddLangCode("de-DE");
      setUserOffset(0);
      loadEntries();
    } catch (err) {
      console.error("Failed to save entry:", err);
    }
  }

  // ---- Edit form handlers ----

  function startEdit(entry: GlossaryEntry) {
    setEditingEntryId(entry.id);
    setEditingForm({
      source_term: entry.source_term,
      term_type: entry.term_type,
      risk_notes: entry.risk_notes,
      applicable_genres: entry.applicable_genres,
      translations: { ...entry.translations },
    });
    setShowEditLangDropdown(false);
    setEditAddLangCode("de-DE");
  }

  function cancelEdit() {
    setEditingEntryId(null);
    setEditingForm(null);
    setShowEditLangDropdown(false);
    setAutoFilling(false);
  }

  function handleEditAddLanguage() {
    if (!editingForm || editingForm.translations[editAddLangCode]) return;
    setEditingForm((f) =>
      f
        ? {
            ...f,
            translations: {
              ...f.translations,
              [editAddLangCode]: { preferred: "", alternatives: [], notes: "" },
            },
          }
        : null,
    );
    setEditAddLangCode(
      getNextAvailable({ ...(editingForm?.translations || {}), [editAddLangCode]: true }),
    );
  }

  function handleEditRemoveLanguage(code: string) {
    if (code === "en-GB" || !editingForm) return;
    setEditingForm((f) =>
      f
        ? {
            ...f,
            translations: Object.fromEntries(Object.entries(f.translations).filter(([c]) => c !== code)),
          }
        : null,
    );
  }

  function updateEditTranslation(
    code: string,
    updates: Partial<{ preferred: string; alternatives: string[]; notes: string }>,
  ) {
    if (!editingForm) return;
    setEditingForm((f) =>
      f
        ? {
            ...f,
            translations: {
              ...f.translations,
              [code]: { ...f.translations[code], ...updates },
            },
          }
        : null,
    );
  }

  async function handleSaveEdit() {
    if (!editingEntryId || !editingForm) return;
    const hasTranslation = Object.values(editingForm.translations).some((t) => t.preferred.trim());
    if (!hasTranslation) return;
    try {
      await apiClient.updateUserGlossaryEntry(editingEntryId, {
        source_term: editingForm.source_term.trim(),
        translations: editingForm.translations,
        risk_notes: editingForm.risk_notes.trim(),
      });
      cancelEdit();
      loadEntries();
    } catch (err) {
      console.error("Failed to update entry:", err);
    }
  }

  async function handleAutoFill() {
    if (!editingEntryId) return;
    setAutoFilling(true);
    setAutoFillMsg(null);
    try {
      const result = await apiClient.autoFillUserGlossaryEntry(editingEntryId);
      const filled = result.filled_languages?.length || 0;
      const skipped = result.skipped?.length || 0;
      setAutoFillMsg(`已补齐 ${filled} 种译法${skipped > 0 ? ` · 跳过 ${skipped} 种` : ""}`);
      cancelEdit();
      loadEntries();
    } catch (err) {
      console.error("Auto-fill failed:", err);
      setAutoFillMsg("自动补齐失败，请稍后重试");
    } finally {
      setAutoFilling(false);
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

  function renderSystemEntryCard(entry: GlossaryEntry) {
    return (
      <div key={entry.id} className="rounded border border-border p-3">
        <span className="font-medium">{entry.source_term}</span>
        {(() => {
          const pref = getPreferredTranslation(entry);
          if (pref) {
            return <span className="ml-2 text-sm text-teal-700">→ {pref}</span>;
          }
          return null;
        })()}
        {(() => {
          const count = getFilledCount(entry);
          if (count > 0) {
            return (
              <span
                className="ml-2 inline-flex items-center rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700"
                title={getFilledLanguageLabels(entry)}
              >
                +{count}
              </span>
            );
          }
          return null;
        })()}
        {entry.risk_notes && (
          <div className="mt-1 text-xs text-orange-600">⚠ {entry.risk_notes}</div>
        )}
      </div>
    );
  }

  // ---- Render helpers ----

  function renderCompactEditor(
    translations: Record<string, TranslationFormEntry>,
    onChange: (code: string, updates: Partial<TranslationFormEntry>) => void,
    onRemove: (code: string) => void,
  ) {
    const order = ["en-GB", ...Object.keys(translations).filter((c) => c !== "en-GB")];
    return (
      <div className="space-y-3">
        {order.map((code) => (
          <div key={code} className="rounded border border-border p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium">{LANGUAGE_LABELS[code] || code}</span>
              {code !== "en-GB" && (
                <button
                  type="button"
                  onClick={() => onRemove(code)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  移除
                </button>
              )}
            </div>
            <div className="space-y-2">
              <Input
                placeholder="首选译法"
                value={translations[code].preferred}
                onChange={(e) => onChange(code, { preferred: e.target.value })}
              />
              <Input
                placeholder="备选译法（逗号分隔）"
                value={translations[code].alternatives.join(", ")}
                onChange={(e) =>
                  onChange(code, {
                    alternatives: e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  })
                }
              />
              <Input
                placeholder="备注（可选）"
                value={translations[code].notes}
                onChange={(e) => onChange(code, { notes: e.target.value })}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }

  function renderAddLangSection(
    translations: Record<string, unknown>,
    showDropdown: boolean,
    langCode: string,
    onToggle: () => void,
    onSetLangCode: (code: string) => void,
    onAdd: () => void,
    onCancel: () => void,
  ) {
    const available = Object.entries(LANGUAGE_LABELS).filter(([code]) => !translations[code]);
    if (available.length === 0) return null;

    if (!showDropdown) {
      return (
        <Button onClick={onToggle} variant="outline" size="sm" className="mt-3">
          + 添加译法
        </Button>
      );
    }

    return (
      <div className="mt-3 flex items-center gap-2">
        <select
          value={langCode}
          onChange={(e) => onSetLangCode(e.target.value)}
          className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
        >
          {available.map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
        <Button onClick={onAdd} size="sm">
          添加
        </Button>
        <Button onClick={onCancel} variant="ghost" size="sm">
          取消
        </Button>
      </div>
    );
  }

  // ---- Render ----

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

      {autoFillMsg && (
        <div className="mb-4 rounded-md bg-teal-50 p-3 text-sm text-teal-800">{autoFillMsg}</div>
      )}

      {/* ---- Create form ---- */}
      <div className="mb-8 rounded-lg border border-border bg-white p-4">
        <h2 className="mb-4 text-lg font-semibold">添加自定义术语</h2>

        <div className="mb-3">
          <Input
            placeholder="中文术语"
            value={form.source_term}
            onChange={(e) => setForm((f) => ({ ...f, source_term: e.target.value }))}
          />
        </div>

        {renderCompactEditor(form.translations, (code, updates) => {
          setForm((f) => ({
            ...f,
            translations: {
              ...f.translations,
              [code]: { ...f.translations[code], ...updates },
            },
          }));
        }, handleRemoveLanguage)}

        {renderAddLangSection(
          form.translations,
          showLangDropdown,
          addLangCode,
          () => setShowLangDropdown(true),
          setAddLangCode,
          handleAddLanguage,
          () => setShowLangDropdown(false),
        )}

        {formError && <p className="mt-2 text-xs text-red-500">{formError}</p>}

        <div className="mt-4 flex gap-2">
          <Button onClick={handleSaveNew} className="bg-teal hover:bg-teal-light text-white">
            保存术语
          </Button>
        </div>
      </div>

      {/* ---- User entries ---- */}
      <div className="mb-8">
        <h2 className="mb-4 text-lg font-semibold">用户自定义术语</h2>
        {userEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">暂无自定义术语</p>
        ) : (
          <>
            <div className="space-y-2">
              {userEntries.map((entry) => (
                <div key={entry.id} className="rounded border border-border p-3">
                  {editingEntryId === entry.id && editingForm ? (
                    /* ---- Inline edit mode ---- */
                    <div className="space-y-2">
                      <Input
                        value={editingForm.source_term}
                        onChange={(e) =>
                          setEditingForm((f) => (f ? { ...f, source_term: e.target.value } : null))
                        }
                        placeholder="中文术语"
                      />
                      {renderCompactEditor(editingForm.translations, updateEditTranslation, handleEditRemoveLanguage)}
                      {renderAddLangSection(
                        editingForm.translations,
                        showEditLangDropdown,
                        editAddLangCode,
                        () => setShowEditLangDropdown(true),
                        setEditAddLangCode,
                        handleEditAddLanguage,
                        () => setShowEditLangDropdown(false),
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button onClick={handleSaveEdit} size="sm" className="bg-teal hover:bg-teal-light text-white">
                          保存
                        </Button>
                        <Button variant="outline" size="sm" onClick={cancelEdit}>
                          取消
                        </Button>
                        <Button
                          onClick={handleAutoFill}
                          disabled={autoFilling}
                          variant="outline"
                          size="sm"
                        >
                          {autoFilling ? "补齐中..." : "✨ 一键补齐其余译法 (LLM)"}
                        </Button>
                      </div>
                    </div>
                  ) : (
                    /* ---- Display mode ---- */
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-medium">{entry.source_term}</span>
                        <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
                          {SYSTEM_GLOSSARY_TERM_TYPE_LABELS[entry.term_type] || DEFAULT_TERM_TYPE_LABEL}
                        </span>
                        {(() => {
                          const pref = getPreferredTranslation(entry);
                          if (pref) {
                            return <span className="ml-2 text-sm text-teal-700">→ {pref}</span>;
                          }
                          return null;
                        })()}
                        {(() => {
                          const count = getFilledCount(entry);
                          if (count > 0) {
                            return (
                              <span
                                className="ml-2 inline-flex items-center rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-700"
                                title={getFilledLanguageLabels(entry)}
                              >
                                +{count}
                              </span>
                            );
                          }
                          return null;
                        })()}
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

      {/* ---- System glossary ---- */}
      <div>
        <div className="mb-4">
          <h2 className="text-lg font-semibold">
            系统知识库
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              共 {systemEntries.length} 条
            </span>
          </h2>
        </div>
        {systemEntries.length === 0 ? (
          <p className="text-sm text-muted-foreground">系统知识库为空</p>
        ) : (
          <div className="space-y-2">
            {groupedSystemEntries.flatMap(([, entries]) =>
              entries.map((entry) => renderSystemEntryCard(entry)),
            )}
          </div>
        )}
      </div>
    </div>
  );
}
