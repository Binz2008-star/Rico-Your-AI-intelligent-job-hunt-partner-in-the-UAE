"use client";

import { useTheme } from "@/contexts/ThemeContext";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();

  const themes: { value: "dark" | "light" | "system"; label: string; icon: string }[] = [
    { value: "dark", label: "Dark", icon: "dark_mode" },
    { value: "light", label: "Light", icon: "light_mode" },
    { value: "system", label: "System", icon: "desktop_windows" },
  ];

  return (
    <div className="flex items-center gap-2">
      {themes.map((t) => (
        <button
          key={t.value}
          onClick={() => setTheme(t.value)}
          className={`relative flex items-center justify-center w-10 h-10 rounded-lg transition-all ${
            theme === t.value
              ? "bg-magenta/20 text-magenta border border-magenta/30"
              : "bg-white/5 text-text-muted border border-white/10 hover:bg-white/10"
          }`}
          title={t.label}
        >
          <span className="text-lg">{t.icon}</span>
          {theme === t.value && (
            <span className="absolute -top-1 -right-1 w-2 h-2 bg-magenta rounded-full" />
          )}
        </button>
      ))}
    </div>
  );
}
