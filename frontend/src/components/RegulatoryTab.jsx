import React, { useEffect, useMemo, useState } from "react";
import {
  ativarComposicaoRegulatoria, ativarRegraRegulatoria, atualizarCategoriaProduto,
  atualizarComponenteRegulatorio, criarCategoriaProduto, criarComponenteRegulatorio,
  criarComposicaoRegulatoria, criarRegraRegulatoria, listarCategoriasProduto,
  listarComponentesRegulatorios, listarComposicoesRegulatorias, listarMateriasPrimas,
  listarRegrasRegulatorias, obterDiagnosticoCategoria, revisarRegraRegulatoria,
} from "../api/api";
import { mensagemErroApi, validarComposicao, validarRegra } from "../utils/regulatory-ui.mjs";

const hoje = () => new Date().toISOString().slice(0, 10);
const input = "border rounded px-3 py-2 w-full";
const botao = "px-3 py-2 rounded text-sm font-medium disabled:opacity-50";

function Campo({ label, children }) {
  return <label className="text-sm space-y-1"><span className="block font-medium">{label}</span>{children}</label>;
}

export default function RegulatoryTab() {
  const [secao, setSecao] = useState("categorias");
  const [categorias, setCategorias] = useState([]);
  const [componentes, setComponentes] = useState([]);
  const [mps, setMps] = useState([]);
  const [regras, setRegras] = useState([]);
  const [composicoes, setComposicoes] = useState([]);
  const [mpSelecionada, setMpSelecionada] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [diagnostico, setDiagnostico] = useState(null);
  const [categoriaForm, setCategoriaForm] = useState({ codigo: "", nome: "", descricao: "" });
  const [componenteForm, setComponenteForm] = useState({ codigo: "", nome: "", descricao: "" });
  const [composicaoForm, setComposicaoForm] = useState({ componente_id: "", situacao: "DESCONHECIDO", concentracao: "", fonte: "", observacao: "", data_referencia: hoje() });
  const [regraForm, setRegraForm] = useState({ categoria_id: "", tipo_alvo: "MATERIA_PRIMA", materia_prima_id: "", componente_id: "", tratamento: "PERMITIDA", minimo: "", maximo: "", justificativa: "", referencia_normativa: "", vigencia_inicio: "", vigencia_fim: "" });
  const [revisando, setRevisando] = useState(null);

  const carregar = async () => {
    try {
      const [cats, comps, materias, regs] = await Promise.all([
        listarCategoriasProduto(), listarComponentesRegulatorios(), listarMateriasPrimas(), listarRegrasRegulatorias(),
      ]);
      setCategorias(cats); setComponentes(comps); setMps(materias); setRegras(regs);
      setRegraForm((f) => ({ ...f, categoria_id: f.categoria_id || String(cats.find((c) => c.codigo === "FORMULA_ENTERAL_PO")?.id || cats[0]?.id || ""), materia_prima_id: f.materia_prima_id || String(materias[0]?.id || ""), componente_id: f.componente_id || String(comps[0]?.id || "") }));
      setMpSelecionada((atual) => atual || String(materias[0]?.id || ""));
      setComposicaoForm((f) => ({ ...f, componente_id: f.componente_id || String(comps[0]?.id || "") }));
    } catch (erro) { setMensagem(mensagemErroApi(erro, "Não foi possível carregar os cadastros regulatórios.")); }
  };

  useEffect(() => { carregar(); }, []);
  useEffect(() => {
    if (!mpSelecionada) { setComposicoes([]); return; }
    listarComposicoesRegulatorias(mpSelecionada).then(setComposicoes).catch((erro) => setMensagem(mensagemErroApi(erro)));
  }, [mpSelecionada]);

  const executar = async (operacao, sucesso) => {
    setOcupado(true); setMensagem("");
    try { await operacao(); setMensagem(sucesso); await carregar(); if (mpSelecionada) setComposicoes(await listarComposicoesRegulatorias(mpSelecionada)); }
    catch (erro) { setMensagem(mensagemErroApi(erro)); }
    finally { setOcupado(false); }
  };

  const nomes = useMemo(() => ({
    mp: Object.fromEntries(mps.map((item) => [item.id, `${item.codigo} — ${item.nome}`])),
    componente: Object.fromEntries(componentes.map((item) => [item.id, `${item.codigo} — ${item.nome}`])),
    categoria: Object.fromEntries(categorias.map((item) => [item.id, item.nome])),
  }), [mps, componentes, categorias]);

  const salvarComposicao = () => {
    const erro = validarComposicao(composicaoForm);
    if (erro || !mpSelecionada || !composicaoForm.componente_id) { setMensagem(erro || "Selecione matéria-prima e componente."); return; }
    const payload = { ...composicaoForm, componente_id: Number(composicaoForm.componente_id), concentracao: composicaoForm.concentracao === "" ? null : Number(composicaoForm.concentracao), fonte: composicaoForm.fonte.trim() || null, observacao: composicaoForm.observacao.trim() || null };
    executar(async () => { await criarComposicaoRegulatoria(mpSelecionada, payload); setComposicoes(await listarComposicoesRegulatorias(mpSelecionada)); }, "Composição registrada sem presumir valores ausentes.");
  };

  const payloadRegra = () => ({
    categoria_id: Number(regraForm.categoria_id), tipo_alvo: regraForm.tipo_alvo,
    materia_prima_id: regraForm.tipo_alvo === "MATERIA_PRIMA" ? Number(regraForm.materia_prima_id) : null,
    componente_id: regraForm.tipo_alvo === "COMPONENTE" ? Number(regraForm.componente_id) : null,
    tratamento: regraForm.tratamento,
    minimo: regraForm.tratamento === "PROIBIDA" ? null : regraForm.minimo === "" ? null : Number(regraForm.minimo),
    maximo: regraForm.tratamento === "PROIBIDA" ? 0 : regraForm.maximo === "" ? null : Number(regraForm.maximo),
    justificativa: regraForm.justificativa.trim(), referencia_normativa: regraForm.referencia_normativa.trim() || null,
    vigencia_inicio: regraForm.vigencia_inicio || null, vigencia_fim: regraForm.vigencia_fim || null,
  });
  const salvarRegra = () => {
    const erro = validarRegra(regraForm);
    if (erro || !regraForm.categoria_id) { setMensagem(erro || "Selecione a categoria."); return; }
    const payload = payloadRegra();
    executar(() => revisando ? revisarRegraRegulatoria(revisando, payload) : criarRegraRegulatoria(payload), revisando ? "Nova revisão criada; o histórico foi preservado." : "Regra cadastrada.");
    setRevisando(null);
  };

  const iniciarRevisao = (regra) => {
    setRevisando(regra.id); setSecao("regras");
    setRegraForm({ categoria_id: String(regra.categoria_id), tipo_alvo: regra.tipo_alvo, materia_prima_id: String(regra.materia_prima_id || ""), componente_id: String(regra.componente_id || ""), tratamento: regra.tratamento, minimo: regra.minimo ?? "", maximo: regra.maximo ?? "", justificativa: regra.justificativa, referencia_normativa: regra.referencia_normativa || "", vigencia_inicio: regra.vigencia_inicio || "", vigencia_fim: regra.vigencia_fim || "" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return <div className="max-w-6xl mx-auto space-y-4">
    <div className="bg-white p-5 rounded shadow">
      <h2 className="text-lg font-semibold">Regulatório</h2>
      <p className="text-sm text-gray-600">Cadastros manuais para avaliação matemática. Não representam certificação normativa.</p>
      <div className="flex flex-wrap gap-2 mt-4" role="tablist" aria-label="Cadastros regulatórios">
        {[['categorias','Categorias'],['componentes','Componentes'],['composicoes','Composição nas MPs'],['regras','Regras']].map(([id,label]) => <button key={id} role="tab" aria-selected={secao === id} onClick={() => setSecao(id)} className={`${botao} ${secao === id ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>{label}</button>)}
      </div>
      {mensagem && <p role="status" className="mt-3 text-sm bg-blue-50 border border-blue-200 rounded p-3">{mensagem}</p>}
    </div>

    {secao === "categorias" && <div className="grid lg:grid-cols-2 gap-4">
      <div className="bg-white p-5 rounded shadow space-y-3"><h3 className="font-semibold">Nova categoria</h3>
        <Campo label="Código estável"><input className={input} value={categoriaForm.codigo} onChange={(e) => setCategoriaForm({...categoriaForm,codigo:e.target.value.toUpperCase()})} /></Campo>
        <Campo label="Nome"><input className={input} value={categoriaForm.nome} onChange={(e) => setCategoriaForm({...categoriaForm,nome:e.target.value})} /></Campo>
        <Campo label="Descrição"><textarea className={input} value={categoriaForm.descricao} onChange={(e) => setCategoriaForm({...categoriaForm,descricao:e.target.value})} /></Campo>
        <button disabled={ocupado} className={`${botao} bg-blue-600 text-white`} onClick={() => executar(() => criarCategoriaProduto({...categoriaForm,descricao:categoriaForm.descricao||null}),"Categoria cadastrada.")}>Cadastrar categoria</button>
      </div>
      <div className="space-y-3">{categorias.map((item) => <div key={item.id} className="bg-white p-4 rounded shadow"><div className="flex justify-between gap-3"><div><strong>{item.codigo} — {item.nome}</strong><p className="text-sm text-gray-600">Revisão {item.revisao} · {item.ativa ? 'Ativa' : 'Inativa'}</p></div><div className="flex flex-wrap gap-2"><button className={`${botao} bg-gray-100`} onClick={() => { const nome=window.prompt('Novo nome',item.nome); if(nome) executar(()=>atualizarCategoriaProduto(item.id,{nome}), 'Categoria atualizada.'); }}>Editar</button><button className={`${botao} bg-gray-100`} onClick={() => executar(()=>atualizarCategoriaProduto(item.id,{ativa:!item.ativa}),'Situação atualizada.')}>{item.ativa?'Desativar':'Ativar'}</button><button className={`${botao} bg-blue-50 text-blue-800`} onClick={async()=>{try{setDiagnostico(await obterDiagnosticoCategoria(item.id));}catch(e){setMensagem(mensagemErroApi(e));}}}>Diagnóstico</button></div></div></div>)}</div>
      {diagnostico && <div className="lg:col-span-2 bg-white p-5 rounded shadow"><h3 className="font-semibold">Diagnóstico cadastral</h3><p className="text-sm mt-2">MPs sem regra individual: {diagnostico.mps_sem_regra_individual?.length || 0}</p>{diagnostico.mps_sem_regra_individual?.length>0&&<ul className="list-disc ml-5 text-sm">{diagnostico.mps_sem_regra_individual.map((x)=><li key={x.materia_prima_id}>MP #{x.materia_prima_id}</li>)}</ul>}<p className="text-sm mt-2">Concentrações desconhecidas: {diagnostico.concentracoes_desconhecidas?.length || 0}</p>{diagnostico.concentracoes_desconhecidas?.length>0&&<ul className="list-disc ml-5 text-sm">{diagnostico.concentracoes_desconhecidas.map((x,i)=><li key={i}>MP #{x.materia_prima_id}, componente #{x.componente_id}: {x.motivo}</li>)}</ul>}</div>}
    </div>}

    {secao === "componentes" && <div className="grid lg:grid-cols-2 gap-4"><div className="bg-white p-5 rounded shadow space-y-3"><h3 className="font-semibold">Novo componente</h3>{[['Código estável','codigo'],['Nome','nome']].map(([label,key])=><Campo key={key} label={label}><input className={input} value={componenteForm[key]} onChange={(e)=>setComponenteForm({...componenteForm,[key]:key==='codigo'?e.target.value.toUpperCase():e.target.value})}/></Campo>)}<Campo label="Descrição"><textarea className={input} value={componenteForm.descricao} onChange={(e)=>setComponenteForm({...componenteForm,descricao:e.target.value})}/></Campo><p className="text-sm text-gray-600">Unidade/base: % m/m</p><button disabled={ocupado} className={`${botao} bg-blue-600 text-white`} onClick={()=>executar(()=>criarComponenteRegulatorio({...componenteForm,descricao:componenteForm.descricao||null}),'Componente cadastrado.')}>Cadastrar componente</button></div><div className="space-y-3">{componentes.map((item)=><div key={item.id} className="bg-white p-4 rounded shadow flex justify-between gap-3"><div><strong>{item.codigo} — {item.nome}</strong><p className="text-sm text-gray-600">{item.unidade} / {item.base} · {item.ativo?'Ativo':'Inativo'}</p></div><div className="flex gap-2"><button className={`${botao} bg-gray-100`} onClick={()=>{const nome=window.prompt('Novo nome',item.nome);if(nome)executar(()=>atualizarComponenteRegulatorio(item.id,{nome}),'Componente atualizado.');}}>Editar</button><button className={`${botao} bg-gray-100`} onClick={()=>executar(()=>atualizarComponenteRegulatorio(item.id,{ativo:!item.ativo}),'Situação atualizada.')}>{item.ativo?'Desativar':'Ativar'}</button></div></div>)}</div></div>}

    {secao === "composicoes" && <div className="space-y-4"><div className="bg-white p-5 rounded shadow grid md:grid-cols-2 lg:grid-cols-3 gap-3"><h3 className="font-semibold md:col-span-2 lg:col-span-3">Composição regulatória da matéria-prima</h3><Campo label="Matéria-prima"><select className={input} value={mpSelecionada} onChange={(e)=>setMpSelecionada(e.target.value)}>{mps.map((x)=><option key={x.id} value={x.id}>{x.codigo} — {x.nome}</option>)}</select></Campo><Campo label="Componente"><select className={input} value={composicaoForm.componente_id} onChange={(e)=>setComposicaoForm({...composicaoForm,componente_id:e.target.value})}>{componentes.filter(x=>x.ativo).map((x)=><option key={x.id} value={x.id}>{x.codigo} — {x.nome}</option>)}</select></Campo><Campo label="Situação do dado"><select className={input} value={composicaoForm.situacao} onChange={(e)=>setComposicaoForm({...composicaoForm,situacao:e.target.value,concentracao:e.target.value==='AUSENTE_CONFIRMADO'?'0':''})}><option>INFORMADO</option><option>AUSENTE_CONFIRMADO</option><option>DESCONHECIDO</option></select></Campo><Campo label="Concentração (% m/m)"><input type="number" min="0" max="100" className={input} disabled={composicaoForm.situacao!=='INFORMADO'} value={composicaoForm.concentracao} onChange={(e)=>setComposicaoForm({...composicaoForm,concentracao:e.target.value})}/></Campo><Campo label="Fonte"><input className={input} value={composicaoForm.fonte} onChange={(e)=>setComposicaoForm({...composicaoForm,fonte:e.target.value})}/></Campo><Campo label="Data de referência"><input type="date" className={input} value={composicaoForm.data_referencia} onChange={(e)=>setComposicaoForm({...composicaoForm,data_referencia:e.target.value})}/></Campo><Campo label="Observação"><textarea className={input} value={composicaoForm.observacao} onChange={(e)=>setComposicaoForm({...composicaoForm,observacao:e.target.value})}/></Campo><div className="flex items-end"><button disabled={ocupado} className={`${botao} bg-blue-600 text-white`} onClick={salvarComposicao}>Registrar composição</button></div></div><div className="bg-white p-4 rounded shadow overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left"><th className="p-2">Componente</th><th>Situação</th><th>Concentração</th><th>Referência</th><th>Fonte</th><th>Ação</th></tr></thead><tbody>{composicoes.map((x)=><tr key={x.id} className="border-t"><td className="p-2">{nomes.componente[x.componente_id]}</td><td>{x.situacao}</td><td>{x.concentracao==null?'Desconhecida':`${x.concentracao}%`}</td><td>{x.data_referencia}</td><td>{x.fonte||'—'}</td><td><button className="underline" onClick={()=>executar(()=>ativarComposicaoRegulatoria(x.id,!x.ativo),'Situação atualizada.')}>{x.ativo?'Desativar':'Ativar'}</button></td></tr>)}</tbody></table></div></div>}

    {secao === "regras" && <div className="space-y-4"><div className="bg-white p-5 rounded shadow grid md:grid-cols-2 lg:grid-cols-4 gap-3"><h3 className="font-semibold md:col-span-2 lg:col-span-4">{revisando?'Nova revisão da regra':'Nova regra manual'}</h3><Campo label="Categoria"><select className={input} value={regraForm.categoria_id} onChange={(e)=>setRegraForm({...regraForm,categoria_id:e.target.value})}>{categorias.filter(x=>x.ativa).map(x=><option key={x.id} value={x.id}>{x.nome}</option>)}</select></Campo><Campo label="Tipo de alvo"><select className={input} value={regraForm.tipo_alvo} onChange={(e)=>setRegraForm({...regraForm,tipo_alvo:e.target.value})}><option value="MATERIA_PRIMA">Matéria-prima</option><option value="COMPONENTE">Componente</option></select></Campo><Campo label="Alvo">{regraForm.tipo_alvo==='MATERIA_PRIMA'?<select className={input} value={regraForm.materia_prima_id} onChange={(e)=>setRegraForm({...regraForm,materia_prima_id:e.target.value})}>{mps.filter(x=>x.ativa).map(x=><option key={x.id} value={x.id}>{x.codigo} — {x.nome}</option>)}</select>:<select className={input} value={regraForm.componente_id} onChange={(e)=>setRegraForm({...regraForm,componente_id:e.target.value})}>{componentes.filter(x=>x.ativo).map(x=><option key={x.id} value={x.id}>{x.codigo} — {x.nome}</option>)}</select>}</Campo><Campo label="Tratamento"><select className={input} value={regraForm.tratamento} onChange={(e)=>setRegraForm({...regraForm,tratamento:e.target.value,minimo:e.target.value==='PROIBIDA'?'':regraForm.minimo,maximo:e.target.value==='PROIBIDA'?'0':regraForm.maximo})}><option>PERMITIDA</option><option>PROIBIDA</option><option>OBRIGATORIA</option><option>LIMITADA</option></select></Campo><Campo label="Mínimo (% m/m)"><input type="number" min="0" max="100" disabled={regraForm.tratamento==='PROIBIDA'} className={input} value={regraForm.minimo} onChange={(e)=>setRegraForm({...regraForm,minimo:e.target.value})}/></Campo><Campo label="Máximo (% m/m)"><input type="number" min="0" max="100" disabled={regraForm.tratamento==='PROIBIDA'} className={input} value={regraForm.maximo} onChange={(e)=>setRegraForm({...regraForm,maximo:e.target.value})}/></Campo><Campo label="Início da vigência"><input type="date" className={input} value={regraForm.vigencia_inicio} onChange={(e)=>setRegraForm({...regraForm,vigencia_inicio:e.target.value})}/></Campo><Campo label="Fim da vigência"><input type="date" className={input} value={regraForm.vigencia_fim} onChange={(e)=>setRegraForm({...regraForm,vigencia_fim:e.target.value})}/></Campo><Campo label="Justificativa"><textarea className={input} value={regraForm.justificativa} onChange={(e)=>setRegraForm({...regraForm,justificativa:e.target.value})}/></Campo><Campo label="Referência textual opcional"><textarea className={input} value={regraForm.referencia_normativa} onChange={(e)=>setRegraForm({...regraForm,referencia_normativa:e.target.value})}/></Campo><div className="flex items-end gap-2"><button disabled={ocupado} className={`${botao} bg-blue-600 text-white`} onClick={salvarRegra}>{revisando?'Criar revisão':'Cadastrar regra'}</button>{revisando&&<button className={`${botao} bg-gray-100`} onClick={()=>setRevisando(null)}>Cancelar</button>}</div></div><div className="space-y-3">{regras.map((x)=><div key={x.id} className="bg-white p-4 rounded shadow flex flex-wrap justify-between gap-3"><div><strong>{x.tipo_alvo}: {x.tipo_alvo==='MATERIA_PRIMA'?nomes.mp[x.materia_prima_id]:nomes.componente[x.componente_id]}</strong><p className="text-sm">{x.tratamento} · mín. {x.minimo??'—'} · máx. {x.maximo??'—'} · % m/m</p><p className="text-sm text-gray-600">{nomes.categoria[x.categoria_id]} · revisão {x.revisao} · {x.ativa?'Ativa':'Inativa'} · vigência {x.vigencia_inicio||'aberta'} a {x.vigencia_fim||'aberta'}</p></div><div className="flex gap-2"><button className={`${botao} bg-blue-50`} onClick={()=>iniciarRevisao(x)}>Revisar</button><button className={`${botao} bg-gray-100`} onClick={()=>executar(()=>ativarRegraRegulatoria(x.id,!x.ativa),'Situação atualizada.')}>{x.ativa?'Desativar':'Ativar'}</button></div></div>)}</div></div>}
  </div>;
}
