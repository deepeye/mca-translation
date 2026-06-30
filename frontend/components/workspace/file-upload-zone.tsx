"use client";

import { useRef, useState } from "react";
import { Upload, FileText, X, LoaderCircle } from "lucide-react";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { apiClient } from "@/lib/api-client";

const ALLOWED_TYPES = [".txt", ".docx", ".pdf"];
const MAX_SIZE = 10 * 1024 * 1024; // 10 MB

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileUploadZone() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounter = useRef(0);

  const upload = useWorkspaceStore((s) => s.upload);
  const setText = useWorkspaceStore((s) => s.setText);
  const setUploadState = useWorkspaceStore((s) => s.setUploadState);
  const clearUpload = useWorkspaceStore((s) => s.clearUpload);

  function validateAndStart(file: File) {
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_TYPES.includes(ext as any)) {
      setUploadState({
        file,
        fileName: file.name,
        fileSize: file.size,
        uploadError: `不支持 ${ext} 格式，仅支持 ${ALLOWED_TYPES.join("、")}`,
      });
      return;
    }
    if (file.size > MAX_SIZE) {
      setUploadState({
        file,
        fileName: file.name,
        fileSize: file.size,
        uploadError: `文件过大（${formatSize(file.size)}），最大 10 MB`,
      });
      return;
    }

    setUploadState({
      file,
      fileName: file.name,
      fileSize: file.size,
      isUploading: true,
      uploadError: null,
    });

    uploadFile(file);
  }

  async function uploadFile(file: File) {
    try {
      const result = await apiClient.uploadFile(file);
      setUploadState({
        fileId: result.file_id,
        isUploading: false,
        uploadError: null,
      });
      setText(result.text_content);
    } catch (err: any) {
      setUploadState({
        isUploading: false,
        uploadError: err.message || "上传失败，请重试",
      });
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) validateAndStart(file);
    // Reset so the same file can be re-selected
    e.target.value = "";
  }

  function handleDragEnter(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current++;
    if (!isDragOver) setIsDragOver(true);
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    dragCounter.current--;
    if (dragCounter.current <= 0) {
      dragCounter.current = 0;
      setIsDragOver(false);
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    dragCounter.current = 0;
    const file = e.dataTransfer.files?.[0];
    if (file) validateAndStart(file);
  }

  function handleBrowse() {
    inputRef.current?.click();
  }

  function handleRemove() {
    clearUpload();
  }

  // Uploading state
  if (upload.isUploading) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        <LoaderCircle className="size-5 animate-spin text-teal" />
        <span className="flex-1 truncate">{upload.fileName}</span>
        <span className="text-xs">{formatSize(upload.fileSize || 0)}</span>
      </div>
    );
  }

  // Uploaded state
  if (upload.fileName) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-teal/30 bg-teal-lightest/30 px-4 py-3 text-sm">
        <FileText className="size-5 shrink-0 text-teal" />
        <span className="flex-1 truncate text-foreground">{upload.fileName}</span>
        <span className="text-xs text-muted-foreground">{formatSize(upload.fileSize || 0)}</span>
        <button
          onClick={handleRemove}
          className="ml-1 flex-size-5 cursor-pointer items-center justify-center rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          aria-label="移除文件"
        >
          <X className="size-4" />
        </button>
      </div>
    );
  }

  // Error state
  if (upload.uploadError) {
    return (
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
        <div className="flex items-start gap-2">
          <span className="mt-0.5 shrink-0 text-destructive">⚠</span>
          <div className="flex-1">
            <p className="text-destructive">{upload.uploadError}</p>
            <button
              onClick={handleBrowse}
              className="mt-1 cursor-pointer text-xs text-muted-foreground underline underline-offset-2 transition-colors hover:text-foreground"
            >
              重试
            </button>
          </div>
          <button
            onClick={handleRemove}
            className="flex shrink-0 cursor-pointer items-center justify-center rounded p-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="关闭"
          >
            <X className="size-4" />
          </button>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept=".txt,.docx,.pdf"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>
    );
  }

  // Default: drop zone
  return (
    <>
      <div
        role="button"
        tabIndex={0}
        aria-label="上传文件以提取文本"
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleBrowse}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            handleBrowse();
          }
        }}
        className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-lg border-2 border-dashed px-4 py-6 text-sm transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
          isDragOver
            ? "border-teal bg-teal-lightest/40"
            : "border-border bg-transparent hover:border-teal/50 hover:bg-teal-lightest/20"
        }`}
      >
        <Upload className="size-6 text-muted-foreground" />
        <p className="text-muted-foreground">
          <span className="text-foreground underline underline-offset-2">点击上传</span>
          <span>&nbsp;或拖放文件至此</span>
        </p>
        <p className="text-xs text-muted-foreground">
          支持 .txt .docx .pdf，最大 10 MB
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.docx,.pdf"
        onChange={handleFileChange}
        className="hidden"
      />
    </>
  );
}
