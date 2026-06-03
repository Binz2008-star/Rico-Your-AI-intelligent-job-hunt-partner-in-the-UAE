import { cn } from "@/lib/utils";
import { forwardRef, type ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "ghost" | "teal" | "danger" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
    variant?: ButtonVariant;
    size?: ButtonSize;
    loading?: boolean;
}

const variants: Record<ButtonVariant, string> = {
    primary:
        "bg-magenta text-white shadow-[0_4px_16px_rgba(255,45,142,0.28)] hover:bg-magenta-hover hover:-translate-y-px hover:scale-105 active:scale-95",
    ghost:
        "bg-surface-glass text-white border border-border-soft hover:bg-surface-subtle hover:border-border-medium hover:scale-105 active:scale-95",
    teal:
        "bg-cyan-soft text-cyan border border-cyan-dim hover:bg-cyan-dim hover:scale-105 active:scale-95",
    danger:
        "bg-rico-red/10 text-rico-red border border-rico-red/20 hover:bg-rico-red/18 hover:scale-105 active:scale-95",
    outline:
        "border border-border-medium text-text-secondary hover:border-border-strong hover:text-white hover:scale-105 active:scale-95",
};

const sizes: Record<ButtonSize, string> = {
    sm: "px-3 py-1.5 text-xs rounded-lg gap-1.5",
    md: "px-4 py-2 text-sm rounded-[10px] gap-2",
    lg: "px-6 py-3 text-[15px] rounded-xl gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
    (
        {
            className,
            variant = "primary",
            size = "md",
            loading = false,
            disabled,
            children,
            ...props
        },
        ref
    ) => (
        <button
            ref={ref}
            className={cn(
                "inline-flex items-center justify-center font-semibold transition-all duration-150 select-none",
                "disabled:opacity-40 disabled:cursor-not-allowed disabled:transform-none",
                variants[variant],
                sizes[size],
                className
            )}
            disabled={disabled || loading}
            {...props}
        >
            {loading && (
                <svg
                    className="animate-spin h-3.5 w-3.5 flex-shrink-0"
                    viewBox="0 0 24 24"
                    fill="none"
                >
                    <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                    />
                    <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                    />
                </svg>
            )}
            {children}
        </button>
    )
);
Button.displayName = "Button";
