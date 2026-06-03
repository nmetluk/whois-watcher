import React from "react";

interface IconProps {
  name: string;
  className?: string;
}

export const Icon: React.FC<IconProps> = ({ name, className }) => (
  <span className={`material-symbols-rounded ${className || ""}`.trim()} aria-hidden>
    {name}
  </span>
);
