import { Mic, Type } from "lucide-react";
import { cn } from "../lib/utils";

export type AppMode = "text" | "voice";

export function ModeSwitch({
  mode,
  disabled,
  onChange,
}: {
  mode: AppMode;
  disabled?: boolean;
  onChange: (mode: AppMode) => void;
}) {
  return (
    <div
      data-testid="mode-switch-shell"
      className="rounded-[1.4rem] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.9),rgba(249,248,246,0.8))] p-2 shadow-[0_24px_46px_-32px_rgba(15,23,42,0.24),inset_0_1px_0_rgba(255,255,255,0.9)] backdrop-blur-xl xl:w-[5.4rem] xl:rounded-l-none xl:border-l-0 xl:shadow-[0_22px_42px_-28px_rgba(15,23,42,0.28),inset_0_1px_0_rgba(255,255,255,0.92)]"
    >
      <div className="px-2 pb-2 pt-1 text-center xl:px-1">
        <div className="text-[0.68rem] font-bold uppercase tracking-[0.2em] text-[#6a746d]">
          Mode
        </div>
        <p className="mt-1 text-sm text-[#5b655f] xl:hidden">
          Switch between live voice control and direct text prompting.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2 xl:grid-cols-1">
        <button
          data-testid="mode-switch-text"
          type="button"
          disabled={disabled}
          onClick={() => onChange("text")}
          className={cn(
            "inline-flex min-h-14 items-center justify-center gap-2 rounded-[1rem] px-4 py-3 text-sm font-semibold transition xl:min-h-[5rem] xl:flex-col xl:rounded-l-none xl:px-2 xl:py-4 xl:text-[0.76rem]",
            mode === "text"
              ? "bg-[#1c211f] text-white shadow-[0_16px_32px_-20px_rgba(15,23,42,0.34)]"
              : "bg-white/55 text-[#46504a] hover:bg-white",
            disabled && "cursor-wait opacity-70",
          )}
        >
          <Type className="size-4" />
          <span>Text Mode</span>
        </button>
        <button
          data-testid="mode-switch-voice"
          type="button"
          disabled={disabled}
          onClick={() => onChange("voice")}
          className={cn(
            "inline-flex min-h-14 items-center justify-center gap-2 rounded-[1rem] px-4 py-3 text-sm font-semibold transition xl:min-h-[5rem] xl:flex-col xl:rounded-l-none xl:px-2 xl:py-4 xl:text-[0.76rem]",
            mode === "voice"
              ? "bg-[#1c211f] text-white shadow-[0_16px_32px_-20px_rgba(15,23,42,0.34)]"
              : "bg-white/55 text-[#46504a] hover:bg-white",
            disabled && "cursor-wait opacity-70",
          )}
        >
          <Mic className="size-4" />
          <span>Voice Mode</span>
        </button>
      </div>
    </div>
  );
}
