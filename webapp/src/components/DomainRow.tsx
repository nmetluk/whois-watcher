/* eslint-disable @typescript-eslint/no-explicit-any */
import React from 'react'; import { Icon } from './Icon'; import { statusOf, puckText, daysText } from '../lib/domain'; import { GroupTag } from './GroupTag';
export const DomainRow: React.FC<any> = ({d, onOpen, selMode, selected, onToggleSel}) => {
  const s = statusOf(d);
  return <div className={"tg-drow" + (selected ? " sel" : "")} onClick={() => onOpen(d)}>
    {selMode && <div className="tg-drow-check" onClick={e=>{e.stopPropagation(); onToggleSel?.(d.id)}}><Icon name="check" /></div>}
    <div className="tg-puck" style={{background:s.dot+'22', color:s.dot}}>{puckText(d)}</div>
    <div className="tg-drow-main">
      <div className="tg-drow-name">{d.unicode}{d.notify && !d.notify.expiry && !d.isWishlist && <Icon name="notifications_off" />}</div>
      <div className="tg-drow-sub"><span>{d.registrar||'—'}</span><span>·</span><span>{daysText(d)}</span></div>
    </div>
    <div className="tg-drow-right">
      <div style={{fontSize:12,fontWeight:700,color:s.dot}}>{d.health != null ? d.health : ''}</div>
      <div className="tg-mini-tags">
        {d.subCount > 0 && <span className="tg-mini-tag" style={{background:'var(--pv-muted)',color:'var(--pv-fg-muted)'}}>{d.subCount} подд.</span>}
        {d.groups?.[0] && <GroupTag id={d.groups[0]} sm/>}
      </div>
    </div>
  </div>;
};
