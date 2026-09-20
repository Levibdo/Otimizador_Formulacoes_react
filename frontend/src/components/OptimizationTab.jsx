import React, { useEffect, useMemo, useState } from "react";
import { executarOtimizacaoProjeto, getMetaData, listarMateriasPrimas, listarProjetos, otimizarFormula } from "../api/api";
import { mensagemErroApi, mensagemStatusRegulatorio } from "../utils/regulatory-ui.mjs";

const campo = "border rounded px-3 py-2";

export default function OptimizationTab({ setTab }) {
  const [modo, setModo] = useState("projeto");
  const [projetos, setProjetos] = useState([]), [projetoId, setProjetoId] = useState("");
  const [materias, setMaterias] = useState([]), [candidatas, setCandidatas] = useState([]);
  const [limites, setLimites] = useState({});
  const [dataReferencia, setDataReferencia] = useState(new Date().toISOString().slice(0, 10));
  const [executando, setExecutando] = useState(false), [mensagem, setMensagem] = useState("");
  const [mpsLegadas, setMpsLegadas] = useState([]), [nutrientes, setNutrientes] = useState([]);
  const [matriz, setMatriz] = useState({}), [restricoes, setRestricoes] = useState([]), [custoMax, setCustoMax] = useState(9999);

  useEffect(() => {
    Promise.all([listarProjetos(), listarMateriasPrimas(), getMetaData()]).then(([ps, ms, meta]) => {
      const ativos = ps.filter((p) => p.status === "ATIVO"), mpsAtivas = ms.filter((mp) => mp.ativa);
      setProjetos(ativos); setProjetoId(String(ativos[0]?.id || "")); setMaterias(mpsAtivas); setCandidatas(mpsAtivas.map((mp) => mp.id));
      setMpsLegadas(meta.materias_primas || []); setNutrientes(meta.nutrientes || []); setMatriz(meta.matriz || {});
    }).catch((erro) => setMensagem(mensagemErroApi(erro, "Não foi possível carregar os dados para otimização.")));
  }, []);
  const projeto = useMemo(() => projetos.find((p) => String(p.id) === projetoId), [projetos, projetoId]);
  const alternarCandidata = (id) => setCandidatas((a) => a.includes(id) ? a.filter((x) => x !== id) : [...a, id]);
  const alterarLimite = (id, chave, valor) => setLimites((a) => ({ ...a, [id]: { ...(a[id] || {}), [chave]: valor } }));
  const limparResultadoAnterior = () => localStorage.removeItem("ultima_otimizacao");
  const alterarModo = (novoModo) => {
    if (novoModo !== modo) limparResultadoAnterior();
    setModo(novoModo);
    setMensagem("");
  };
  const alterarProjeto = (novoProjetoId) => {
    if (novoProjetoId !== projetoId) limparResultadoAnterior();
    setProjetoId(novoProjetoId);
    setMensagem("");
  };

  const executarProjeto = async () => {
    if (!projetoId) return setMensagem("Selecione um projeto ativo.");
    if (!candidatas.length) return setMensagem("Selecione ao menos uma matéria-prima candidata.");
    let limitesTecnicos;
    try {
      limitesTecnicos = candidatas.flatMap((id) => {
        const item = limites[id] || {}, vazioMin = item.minimo === "" || item.minimo == null, vazioMax = item.maximo === "" || item.maximo == null;
        if (vazioMin && vazioMax) return [];
        const minimo = vazioMin ? null : Number(item.minimo), maximo = vazioMax ? null : Number(item.maximo);
        if (minimo != null && maximo != null && minimo > maximo) throw new Error("O mínimo técnico não pode superar o máximo.");
        return [{ materia_prima_id: id, minimo, maximo }];
      });
    } catch (erro) { return setMensagem(erro.message); }
    setExecutando(true); setMensagem("Executando otimização com os dados oficiais do PostgreSQL...");
    try {
      const resultado = await executarOtimizacaoProjeto(Number(projetoId), { materias_primas_ids: candidatas, limites_tecnicos: limitesTecnicos, data_referencia: dataReferencia });
      localStorage.setItem("ultima_otimizacao", JSON.stringify({ ...resultado, modo_otimizacao: "server-side", projeto_id: Number(projetoId), projeto_codigo: projeto?.codigo, conferencia_nutricional: resultado.composicao }));
      setMensagem(mensagemStatusRegulatorio(resultado.status)); setTab("resultados");
    } catch (erro) { setMensagem(mensagemErroApi(erro, "Não foi possível executar a otimização do projeto.")); }
    finally { setExecutando(false); }
  };

  const adicionarRestricao = (tipo) => {
    const itens = tipo === "MP" ? mpsLegadas : nutrientes;
    if (itens.length) setRestricoes((a) => [...a, { id: Date.now(), item: itens[0], tipo: tipo === "MP" ? "<=" : ">=", valor: 0, tipo_item: tipo }]);
  };
  const executarLegado = async () => {
    const metas = {}, limitesMp = {};
    restricoes.forEach((r) => { const destino = r.tipo_item === "Nutriente" ? metas : limitesMp; if (!destino[r.item]) destino[r.item] = [null, null]; if (r.tipo === ">=") destino[r.item][0] = Number(r.valor); if (r.tipo === "<=") destino[r.item][1] = Number(r.valor); if (r.tipo === "=") destino[r.item] = [Number(r.valor), Number(r.valor)]; });
    setExecutando(true); setMensagem("Executando simulação manual legada...");
    try { const resultado = await otimizarFormula({ metas, restricoes: limitesMp, custo_max: custoMax, matriz }); localStorage.setItem("ultima_otimizacao", JSON.stringify({ ...resultado, modo_otimizacao: "legado", contexto_otimizacao: { metas, restricoes: limitesMp, custo_max: custoMax, matriz } })); setTab("resultados"); }
    catch (erro) { setMensagem(mensagemErroApi(erro, "Não foi possível executar a simulação manual.")); }
    finally { setExecutando(false); }
  };

  return <div className="max-w-6xl mx-auto space-y-4">
    <div className="bg-white p-5 rounded shadow"><h2 className="text-lg font-semibold">Otimização</h2><div className="grid md:grid-cols-2 gap-3 mt-4" role="radiogroup" aria-label="Modo de otimização">
      <button role="radio" aria-checked={modo === "projeto"} onClick={() => alterarModo("projeto")} className={`text-left p-4 border-2 rounded ${modo === 'projeto' ? 'border-blue-600 bg-blue-50' : 'border-gray-200'}`}><strong>Otimização do projeto</strong><span className="block text-sm text-gray-600">Recomendado. Usa cadastros oficiais e avalia as regras aplicáveis.</span></button>
      <button role="radio" aria-checked={modo === "legado"} onClick={() => alterarModo("legado")} className={`text-left p-4 border-2 rounded ${modo === 'legado' ? 'border-amber-600 bg-amber-50' : 'border-gray-200'}`}><strong>Simulação manual legada</strong><span className="block text-sm text-gray-600">Não realiza avaliação regulatória. Matriz e limites são informados pela tela.</span></button>
    </div>{mensagem && <p role="status" className="mt-4 p-3 bg-gray-50 border rounded text-sm">{mensagem}</p>}</div>
    {modo === "projeto" ? <>
      <div className="bg-white p-5 rounded shadow grid md:grid-cols-2 gap-4"><label className="text-sm"><span className="font-medium block mb-1">Projeto ativo</span><select className={`${campo} w-full`} value={projetoId} onChange={(e) => alterarProjeto(e.target.value)}><option value="">Selecione</option>{projetos.map((p) => <option key={p.id} value={p.id}>{p.codigo} — {p.nome}</option>)}</select></label><label className="text-sm"><span className="font-medium block mb-1">Data de referência</span><input type="date" className={`${campo} w-full`} value={dataReferencia} onChange={(e) => setDataReferencia(e.target.value)} /></label><div className="md:col-span-2 p-3 rounded bg-blue-50 text-sm">Categoria: <strong>{projeto?.categoria_produto_id ? "Categoria regulatória vinculada" : "Sem categoria — o resultado será sem avaliação regulatória"}</strong></div></div>
      <div className="bg-white p-5 rounded shadow"><div className="flex flex-wrap justify-between gap-2"><div><h3 className="font-semibold">Matérias-primas candidatas</h3><p className="text-sm text-gray-600">Preços e composições são carregados pelo servidor.</p></div><div className="flex gap-2"><button className="px-3 py-1 bg-gray-100 rounded" onClick={() => setCandidatas(materias.map((mp)=>mp.id))}>Selecionar todas</button><button className="px-3 py-1 bg-gray-100 rounded" onClick={() => setCandidatas([])}>Limpar</button></div></div><div className="mt-4 space-y-2">{materias.map((mp) => <div key={mp.id} className="grid md:grid-cols-12 gap-2 items-center border rounded p-3"><label className="md:col-span-6 flex gap-2 items-center"><input type="checkbox" checked={candidatas.includes(mp.id)} onChange={() => alternarCandidata(mp.id)} /><span>{mp.codigo} — {mp.nome}</span></label><label className="md:col-span-3 text-sm">Mínimo técnico (%)<input type="number" min="0" max="100" disabled={!candidatas.includes(mp.id)} className={`${campo} w-full`} value={limites[mp.id]?.minimo ?? ""} onChange={(e)=>alterarLimite(mp.id,'minimo',e.target.value)}/></label><label className="md:col-span-3 text-sm">Máximo técnico (%)<input type="number" min="0" max="100" disabled={!candidatas.includes(mp.id)} className={`${campo} w-full`} value={limites[mp.id]?.maximo ?? ""} onChange={(e)=>alterarLimite(mp.id,'maximo',e.target.value)}/></label></div>)}</div><button disabled={executando || !projetoId || !candidatas.length} onClick={executarProjeto} className="mt-4 bg-blue-600 disabled:bg-blue-300 text-white px-4 py-2 rounded">{executando ? "Executando..." : "Otimizar projeto"}</button></div>
    </> : <div className="bg-white p-5 rounded shadow space-y-4 border-t-4 border-amber-500"><div><h3 className="font-semibold">Simulação manual legada</h3><p className="text-sm text-amber-800">Este modo não aplica regras regulatórias e não produz declaração de conformidade.</p></div><label className="text-sm">Custo máximo (R$/kg)<input type="number" className={`${campo} ml-2`} value={custoMax} onChange={(e)=>setCustoMax(Number(e.target.value))}/></label><div className="flex gap-2"><button className="px-3 py-1 bg-gray-100 rounded" onClick={()=>adicionarRestricao('MP')}>+ Limite de MP</button><button className="px-3 py-1 bg-gray-100 rounded" onClick={()=>adicionarRestricao('Nutriente')}>+ Meta nutricional</button></div><div className="space-y-2">{restricoes.map((r,i)=><div key={r.id} className="grid md:grid-cols-5 gap-2"><select aria-label="Item da restrição" className={campo} value={r.item} onChange={(e)=>setRestricoes((a)=>a.map((x,j)=>j===i?{...x,item:e.target.value}:x))}>{(r.tipo_item==='MP'?mpsLegadas:nutrientes).map(x=><option key={x}>{x}</option>)}</select><select aria-label="Operador" className={campo} value={r.tipo} onChange={(e)=>setRestricoes((a)=>a.map((x,j)=>j===i?{...x,tipo:e.target.value}:x))}><option>&lt;=</option><option>&gt;=</option><option>=</option></select><input aria-label="Valor" type="number" className={campo} value={r.valor} onChange={(e)=>setRestricoes((a)=>a.map((x,j)=>j===i?{...x,valor:e.target.value}:x))}/><button className="text-red-700" onClick={()=>setRestricoes((a)=>a.filter((_,j)=>j!==i))}>Remover</button></div>)}</div><button disabled={executando} onClick={executarLegado} className="bg-amber-600 disabled:bg-amber-300 text-white px-4 py-2 rounded">{executando ? "Executando..." : "Executar simulação manual"}</button></div>}
  </div>;
}
