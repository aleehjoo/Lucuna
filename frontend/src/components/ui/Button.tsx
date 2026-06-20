import { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "ghost" | "danger";
const styles: Record<Variant, string> = {
  primary: "bg-[var(--ultramarine)] text-white hover:opacity-90",
  ghost: "bg-transparent text-[var(--ink)] border border-[var(--border)] hover:bg-[color-mix(in_srgb,var(--ink)_5%,transparent)]",
  danger: "bg-[var(--oxblood)] text-white hover:opacity-90",
};

export function Button({ variant = "primary", className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`inline-flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-50 ${styles[variant]} ${className}`}
      {...rest}
    />
  );
}
