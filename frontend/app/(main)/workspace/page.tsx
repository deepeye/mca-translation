import { InputPanel } from "@/components/workspace/input-panel";
import { OutputPanel } from "@/components/workspace/output-panel";

export default function WorkspacePage() {
  return (
    <div className="flex h-[calc(100vh-3.5rem)] gap-0">
      <div className="w-[42%] border-r border-border p-4">
        <InputPanel />
      </div>
      <div className="w-[58%] p-4">
        <OutputPanel />
      </div>
    </div>
  );
}
