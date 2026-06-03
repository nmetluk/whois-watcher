/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react'; import { Icon } from './Icon';
export const IRow: React.FC<any> = ({icon,label,value,mono,children}) => <div className="tg-irow"><div className="tg-ir-ico">{icon&&<Icon name={icon}/>}</div><div className="tg-ir-label">{label}</div><div className={"tg-ir-val"+(mono?' mono':'')}>{value}</div>{children}</div>;
