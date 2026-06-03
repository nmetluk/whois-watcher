import React from 'react';
interface IconProps { name: string; className?: string; style?: React.CSSProperties; onClick?: (e: React.MouseEvent) => void; }
export const Icon: React.FC<IconProps> = ({ name, className, style, onClick }) => (
  <span className={"material-symbols-rounded" + (className ? " " + className : "")} style={style} onClick={onClick} aria-hidden>{name}</span>
);
