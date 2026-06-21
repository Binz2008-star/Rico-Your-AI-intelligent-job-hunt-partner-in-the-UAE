"use client";

import { useRef } from "react";

export interface KeywordTagInputProps {
    tags: string[];
    onChange: (next: string[]) => void;
    placeholder?: string;
    hint?: string;
    disabled?: boolean;
    label?: string;
}

/**
 * Controlled chip/tag input for keyword arrays.
 * No per-field save/cancel — parent owns persistence via onChange.
 * Enter or comma commits the typed token; Backspace removes the last chip.
 */
export function KeywordTagInput({
    tags,
    onChange,
    placeholder = "Add keyword…",
    hint,
    disabled = false,
    label,
}: KeywordTagInputProps) {
    const inputRef = useRef<HTMLInputElement>(null);

    const commit = (raw: string) => {
        const trimmed = raw.trim().replace(/,+$/, "").trim();
        if (trimmed && !tags.includes(trimmed)) {
            onChange([...tags, trimmed]);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        const val = e.currentTarget.value;
        if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            commit(val);
            e.currentTarget.value = "";
        } else if (e.key === "Backspace" && !val && tags.length > 0) {
            onChange(tags.slice(0, -1));
        }
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
        if (e.target.value.trim()) {
            commit(e.target.value);
            e.target.value = "";
        }
    };

    const removeTag = (tag: string) => {
        onChange(tags.filter((t) => t !== tag));
        inputRef.current?.focus();
    };

    return (
        <div className="flex flex-col gap-1">
            <div
                role="group"
                aria-label={label}
                className="flex min-h-[42px] flex-wrap gap-1.5 rounded-lg border border-border-soft bg-surface-glass px-3 py-2 transition focus-within:border-rico-accent cursor-text"
                onClick={() => inputRef.current?.focus()}
            >
                {tags.map((tag) => (
                    <span
                        key={tag}
                        className="inline-flex items-center gap-1 rounded-md bg-surface-elevated px-2 py-0.5 text-xs text-text-primary"
                    >
                        {tag}
                        <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); removeTag(tag); }}
                            disabled={disabled}
                            aria-label={`Remove ${tag}`}
                            className="text-text-tertiary transition-colors hover:text-red-400 disabled:opacity-40"
                        >
                            ×
                        </button>
                    </span>
                ))}
                <input
                    ref={inputRef}
                    type="text"
                    disabled={disabled}
                    aria-label={label}
                    placeholder={tags.length === 0 ? placeholder : "Add more…"}
                    className="min-w-[120px] flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-tertiary disabled:opacity-50"
                    onKeyDown={handleKeyDown}
                    onBlur={handleBlur}
                />
            </div>
            {hint && (
                <p className="text-[10px] text-text-tertiary">{hint}</p>
            )}
        </div>
    );
}
