"use client";

import * as React from "react";
import { Select as SelectPrimitive } from "@base-ui/react/select";
import { CheckIcon, ChevronDownIcon } from "lucide-react";
import { cn } from "@/lib/utils";

function Select<Value>(props: SelectPrimitive.Root.Props<Value, false>) {
  return <SelectPrimitive.Root {...props} />;
}

function SelectGroup(props: SelectPrimitive.Group.Props) {
  return <SelectPrimitive.Group {...props} />;
}

function SelectValue(props: SelectPrimitive.Value.Props) {
  return <SelectPrimitive.Value {...props} />;
}

function SelectTrigger({
  className,
  children,
  ...props
}: SelectPrimitive.Trigger.Props) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "glow-control flex h-10 w-full items-center justify-between gap-2 rounded-[10px] px-3 py-2 text-sm text-[var(--foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      {children}
      <SelectPrimitive.Icon className="text-[var(--muted)]">
        <ChevronDownIcon className="h-4 w-4 shrink-0 opacity-70" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectContent({
  className,
  children,
  ...props
}: SelectPrimitive.Popup.Props) {
  return (
    <SelectPrimitive.Portal>
      <SelectPrimitive.Positioner sideOffset={8} alignItemWithTrigger={false}>
        <SelectPrimitive.Popup
          className={cn(
            "z-50 max-h-72 min-w-[var(--anchor-width)] overflow-hidden rounded-[10px] border border-[var(--border)] bg-[var(--surface-raised)] p-1 text-[var(--foreground)] shadow-lg",
            className,
          )}
          {...props}
        >
          <SelectPrimitive.List className="overflow-auto">{children}</SelectPrimitive.List>
        </SelectPrimitive.Popup>
      </SelectPrimitive.Positioner>
    </SelectPrimitive.Portal>
  );
}

function SelectLabel(props: SelectPrimitive.Label.Props) {
  return (
    <SelectPrimitive.Label
      className="px-2 py-1.5 text-xs font-medium text-[var(--muted)]"
      {...props}
    />
  );
}

function SelectItem({
  className,
  children,
  ...props
}: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-[8px] py-2 pl-8 pr-3 text-sm outline-none data-highlighted:bg-white/10 data-disabled:pointer-events-none data-disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SelectPrimitive.ItemIndicator className="absolute left-2 flex size-4 items-center justify-center">
        <CheckIcon className="h-4 w-4" />
      </SelectPrimitive.ItemIndicator>
      <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
    </SelectPrimitive.Item>
  );
}

export {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
};
