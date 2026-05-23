"use client";

import { cn } from "@/lib/utils";
import { TextareaHTMLAttributes, forwardRef, useCallback, useEffect, useRef } from "react";

interface RicoCommandInputProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  placeholder?: string;
}

export const RicoCommandInput = forwardRef<HTMLTextAreaElement, RicoCommandInputProps>(
  ({ placeholder = "Type a command...", className, onChange, ...props }, ref) => {
    const innerRef = useRef<HTMLTextAreaElement>(null);

    // Merge forwarded ref with inner ref so we can read scrollHeight
    const setRefs = useCallback(
      (node: HTMLTextAreaElement | null) => {
        (innerRef as React.MutableRefObject<HTMLTextAreaElement | null>).current = node;
        if (typeof ref === "function") {
          ref(node);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLTextAreaElement | null>).current = node;
        }
      },
      [ref]
    );

    const autoResize = useCallback(() => {
      const el = innerRef.current;
      if (!el) return;
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
    }, []);

    // Resize whenever the controlled value changes (e.g. cleared after send)
    useEffect(() => {
      autoResize();
    }, [props.value, autoResize]);

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        autoResize();
        onChange?.(e);
      },
      [autoResize, onChange]
    );

    return (
      <textarea
        ref={setRefs}
        rows={1}
        placeholder={placeholder}
        onChange={handleChange}
        className={cn(
          "w-full",
          "resize-none min-h-[46px] max-h-[200px]",
          "bg-[rgba(255,255,255,0.04)]",
          "border border-[var(--rico-border-soft)]",
          "rounded-[var(--r-lg)]",
          "text-[14px]",
          "px-3.5 py-3",
          "text-[var(--rico-fg-1)]",
          "placeholder:text-[var(--rico-fg-4)]",
          "outline-none",
          "overflow-y-auto",
          "transition-colors duration-[var(--dur-state)] ease-[var(--ease-out)]",
          "focus:border-[var(--rico-primary-container)]",
          className
        )}
        {...props}
      />
    );
  }
);

RicoCommandInput.displayName = "RicoCommandInput";
