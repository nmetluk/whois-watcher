import React, { useState } from 'react';
import { Icon } from '../components/Icon';
import { fetchAlerts, markAlertsRead } from '../lib/api';
export const AlertsScreen: React.FC<any> = ({ onOpenDomain, toast }) => {
  const [filter, setFilter] = useState('all');
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string|null>(null);
  const load = React.useCallback(() => { setLoading(true); setErr(null); fetchAlerts().then(d=>{setData(d);}).catch(()=> {setErr('Не удалось загрузить алерты'); setData(null); }).finally(()=>setLoading(false)); }, []);
  React.useEffect(() => { load(); }, [load]);
  const types = [{id:'all',label:'Все'},{id:'unread',label:'Непрочитанные'},{id:'expiry',label:'Сроки'},{id:'ssl',label:'SSL'},{id:'changes',label:'Изменения'}];
  const items = (data && data.items) || [];
  const unread = (data && data.unreadCount) || 0;
  const filtered = items.filter((a:any)=>{ if(filter==='all')return true; if(filter==='unread')return a.unread!==false; return true; });
  const markAll = async () => { if (!items.length) return; try { await markAlertsRead(items.map((x:any)=>x.id)); toast('Отмечено прочитанным'); setData((d:any)=>({...d, unreadCount:0, items:(d.items||[]).map((x:any)=>({...x,unread:false})) })); } catch { toast('Ошибка'); } };
  return <><div className="tg-search-sticky" style={{paddingBottom:6}}><div className="tg-chips" style={{paddingTop:0,marginTop:0}}>{types.map(t=><button key={t.id} className={"tg-chip2"+(filter===t.id?" active":"")} onClick={()=>setFilter(t.id)}>{t.label}{t.id==='unread'&&unread>0&&<span className="tg-chip-n">{unread}</span>}</button>)}</div></div>{unread>0 && <div style={{display:'flex',justifyContent:'flex-end',padding:'8px 14px'}}><button className="pv-btn pv-btn-sm pv-btn-ghost" onClick={markAll}>Прочитать все</button></div>}{loading?<div className="tg-pad">Загрузка...</div>:err?<div className="tg-pad"><div className="tg-card">⚠️ {err}<button className="pv-btn" style={{marginTop:8}} onClick={load}>Повторить</button></div></div>:filtered.length===0?<div className="tg-empty2"><Icon name="notifications_off" /><b>Уведомлений нет</b></div>:filtered.map((a:any,i:number)=><div key={i} className={"tg-alert"+(a.unread?" unread":"")} onClick={()=>onOpenDomain({id:a.id||1})}><div className={"tg-alert-ico "+(a.sev||'info')}><Icon name={a.icon||'info'} /></div><div className="tg-alert-main"><div className="tg-alert-dom">{a.domain}</div><div className="tg-alert-txt">{a.text}</div><div className="tg-alert-when">{a.at||a.when}</div></div><Icon name="chevron_right" style={{color:'var(--pv-fg-subtle)',alignSelf:'center'}} /></div>)}</>;
};
