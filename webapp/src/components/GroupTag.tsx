import React from 'react'; import { Icon } from './Icon';
const avatarHue = (c?:string) => ({a0:'#9c4bb5',a1:'#3498db'}[c||''] || '#9aa1a8');
export const GroupTag: React.FC<{id:string; sm?:boolean}> = ({id,sm}) => <span className="tg-mini-tag" style={{background:avatarHue()+'22',color:avatarHue(),fontSize:sm?10:11}}><Icon name="label" style={{fontSize:11}}/>{id}</span>;
