/* eslint-disable @typescript-eslint/no-explicit-any */
import React, { useCallback, useEffect, useState } from 'react';
import { DomainRow } from '../components/DomainRow';
import { fetchPortfolio } from '../lib/api';
import type { WebAppDomain } from '../lib/api';

const FILTERS = [{id:'all',label:'Все'},{id:'soon',label:'Истекающие'},{id:'crit',label:'Критичные'},{id:'problem',label:'С проблемами'},{id:'expired',label:'Истёкшие'},{id:'nodata',label:'Без данных'},{id:'silent',label:'Без уведомлений'},{id:'wish',label:'Wishlist'}];

export const ListScreen: React.FC<any> = ({ onOpenDomain, toast }) => {
  const [st, setSt] = useState({query:'', filter:'all', sort:'expiry', selMode:false, sel:new Set<number>()});
  const [domains, setDomains] = useState<WebAppDomain[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (reset=true) => {
    setLoading(true);
    try {
      const res = await fetchPortfolio({filter:st.filter, q:st.query, sort:st.sort, limit:50, offset: reset?0:domains.length});
      if (reset) setDomains(res.items); else setDomains(d => [...d, ...res.items]);
      setTotal(res.total);
    } catch {
      setDomains([{id:1,name:'demo.ru',unicode:'demo.ru',noData:false,isWishlist:false,daysLeft:5,health:70,subCount:1,groups:[],notify:{expiry:true,ns:true,registrar:true,status:true},flags:[],cost:0,registrar:'Demo'} as any]);
      setTotal(1);
      toast('Демо (API недоступен)');
    } finally { setLoading(false); }
  }, [st.filter, st.query, st.sort, domains.length, toast]);

  useEffect(() => { void load(true); }, [st.filter, st.query, st.sort, load]); // eslint-disable-line react-hooks/set-state-in-effect

  const toggleSel = (id:number) => { setSt(s => { const n = new Set(s.sel); if (n.has(id)) n.delete(id); else n.add(id); return {...s, sel:n}; }); };

  return <>
    <div className="tg-search-sticky"><input className="tg-search" placeholder="Поиск..." value={st.query} onChange={e=>setSt(s=>({...s,query:e.target.value}))} /></div>
    <div className="tg-filters">{FILTERS.map(f => <button key={f.id} className={`tg-chip ${st.filter===f.id?'active':''}`} onClick={()=>setSt(s=>({...s,filter:f.id}))}>{f.label}</button>)}</div>
    <div style={{padding:'0 12px'}}><button onClick={()=>setSt(s=>({...s,selMode:!s.selMode}))}>{st.selMode?'Готово':'Выбрать'}</button></div>
    {domains.map(d => <DomainRow key={d.id} d={d} onOpen={onOpenDomain} selMode={st.selMode} selected={st.sel.has(d.id)} onToggleSel={toggleSel} />)}
    {loading && <div className="tg-pad">Загрузка...</div>}
    <button onClick={()=>load(false)} disabled={loading || domains.length>=total}>Ещё</button>
  </>;
};
