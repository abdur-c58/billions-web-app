"use client";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { WHISPER_MODEL_OPTIONS, type WhisperModel } from "@/lib/whisper";

type WhisperModelSelectProps = {
  value: WhisperModel;
  onValueChange: (value: WhisperModel) => void;
  disabled?: boolean;
  className?: string;
  id?: string;
};

export function WhisperModelSelect({
  value,
  onValueChange,
  disabled = false,
  className,
  id = "whisper-model",
}: WhisperModelSelectProps) {
  return (
    <div className={cn("flex min-w-[200px] flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-xs font-medium text-[var(--muted)]">
        Whisper model
      </label>
      <Select<WhisperModel>
        value={value}
        onValueChange={(next) => {
          if (next) onValueChange(next);
        }}
        items={WHISPER_MODEL_OPTIONS.map((option) => ({
          value: option.value,
          label: option.label,
        }))}
        disabled={disabled}
      >
        <SelectTrigger
          id={id}
          className="min-w-[200px]"
          aria-label="Whisper model"
          disabled={disabled}
        >
          <SelectValue placeholder="Choose model" />
        </SelectTrigger>
        <SelectContent className="min-w-[280px]">
          {WHISPER_MODEL_OPTIONS.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              <span className="font-medium">{option.label}</span>
              <span className="ml-1.5 text-[var(--muted)]">· {option.description}</span>
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
