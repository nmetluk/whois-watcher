/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useState } from 'react';
import { Ring } from '../components/Ring';
import { statusOf, daysText } from '../lib/domain';

export const DomainScreen: React.FC<any> = ({ d, onBack, toast }) => {
  const [tab, setTab] = useState('overview');
  const s = statusOf(d);
  return <>
    <div className="tg-ctabs">
      {['overview','whois','ssl','dns','email','subs'].map(t => <button key={t} className={'tg-ctab '+(tab===t?'active':'')} onClick={()=>setTab(t)}>{t}</button>)}
    </div>
    <div className="tg-pad">
      {tab==='overview' && <>
        <div className="tg-card"><Ring value={d.health} size={72} /><div>{daysText(d)}</div><div>Статус: {s.label}</div></div>
        <button className="pv-btn" onClick={()=>toast('Toggle (stub)')}>Тоггл уведомлений (UI)</button>
      </>}
      {tab!=='overview' && <div className="tg-card">Вкладка {tab} (stub, данные из /domain API)</div>}
    </div>
    <button onClick={onBack}>Назад</button>
  </>;
};
