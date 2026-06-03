/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react'; import { Icon } from './Icon'; import { statusOf, puckText, daysText } from '../lib/domain'; import { GroupTag } from './GroupTag';
export const DomainRow: React.FC<any> = ({d, onOpen, selMode, selected, onToggleSel}) => {
  const s = statusOf(d);
  return <div className="tg-drow" onClick={() => onOpen(d)}>
    {selMode && <div onClick={e=>{e.stopPropagation(); onToggleSel?.(d.id)}} style={{width:22,height:22,borderRadius:'50%',border:selected?'2px solid var(--pv-accent)':'2px solid var(--pv-border)', background:selected?'var(--pv-accent-soft)':'transparent', marginRight:8}}>{selected && <Icon name="check" style={{fontSize:14}}/>}</div>}
    <div className="tg-puck" style={{background:s.dot+'22', color:s.dot}}>{puckText(d)}</div>
    <div className="tg-drow-info"><div className="tg-drow-name">{d.unicode}</div><div className="tg-drow-sub">{d.registrar||'—'} · {daysText(d)}</div></div>
    <div style={{textAlign:'right'}}><div>{d.health}</div><div style={{fontSize:10,color:'var(--pv-fg-subtle)'}}>{d.subCount} подд.</div>{d.groups?.[0] && <GroupTag id={d.groups[0]} sm/>}</div>
  </div>;
};
