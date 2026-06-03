import React, { useCallback, useEffect, useState } from 'react';
import { DomainRow } from '../components/DomainRow';
import { fetchPortfolio } from '../lib/api';
import type { WebAppDomain } from '../lib/api';
const FILTERS = [{id:'all',label:'Все'},{id:'soon',label:'Истекающие'},{id:'crit',label:'Критичные'},{id:'problem',label:'С проблемами'},{id:'expired',label:'Истёкшие'},{id:'nodata',label:'Без данных'},{id:'silent',label:'Без уведомлений'},{id:'wish',label:'Wishlist'}];
export const ListScreen: React.FC<any> = ({ onOpenDomain, toast }) => {
  const [st, setSt] = useState({query:'', filter:'all', sort:'expiry'});
  const [domains, setDomains] = useState<WebAppDomain[]>([]);
  const [loading, setLoading] = useState(false);
  const load = useCallback(async () => { setLoading(true); try { const res = await fetchPortfolio({filter:st.filter, q:st.query, sort:st.sort, limit:50}); setDomains(res.items || []); } catch { setDomains([{id:1,name:'demo.ru',unicode:'demo.ru',noData:false,isWishlist:false,daysLeft:5,health:70,subCount:1,groups:[],notify:{expiry:true,ns:true,registrar:true,status:true},flags:[],cost:0,registrar:'Demo'} as any]); toast('Демо'); } finally { setLoading(false); } }, [st.filter, st.query, st.sort, toast]);
  useEffect(() => { load(); }, [load]);
  return <><div className="tg-search-sticky"><input className="tg-search" placeholder="Поиск..." value={st.query} onChange={e=>setSt(s=>({...s,query:e.target.value}))} /></div><div className="tg-filters">{FILTERS.map(f => <button key={f.id} className={`tg-chip ${st.filter===f.id?'active':''}`} onClick={()=>setSt(s=>({...s,filter:f.id}))}>{f.label}</button>)}</div>{loading && <div className="tg-pad">Загрузка...</div>}{domains.map(d => <DomainRow key={d.id} d={d} onOpen={onOpenDomain} />)}</>;
};
