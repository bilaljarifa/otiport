import type { ButtonHTMLAttributes } from "react";
import { buttonClass, type ButtonVariant } from "./buttonStyles";

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button className={buttonClass(variant, className)} {...props} />;
}
