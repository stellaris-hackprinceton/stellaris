"use client";
import { IconButton } from "./Button";
import { MoonIcon, SunIcon, SystemThemeIcon } from "./icons";
import { setThemePreference, useThemePreference, type ThemePreference } from "./theme";

const ORDER: ThemePreference[] = ["system", "light", "dark"];
const NAME: Record<ThemePreference, string> = { system: "System", light: "Light", dark: "Dark" };
const ICON = { system: <SystemThemeIcon />, light: <SunIcon />, dark: <MoonIcon /> };

/** One compact control: System → Light → Dark. The label states the current mode and the next one. */
export function ThemeToggle({ className }: { className?: string }) {
  const preference = useThemePreference();
  const next = ORDER[(ORDER.indexOf(preference) + 1) % ORDER.length];
  return (
    <IconButton
      className={className}
      label={`Theme: ${NAME[preference]}. Switch to ${NAME[next]}`}
      icon={ICON[preference]}
      onClick={() => setThemePreference(next)}
    />
  );
}
