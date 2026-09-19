import React, { useEffect, useMemo, useState } from "react";
import {
  atualizarItemEmbalagem,
  criarApresentacao,
  criarItemEmbalagem,
  listarApresentacoes,
  listarItensEmbalagem,
  listarProjetos,
} from "../api/api";

const componenteVazio = () => ({ item_embalagem_id: "", quantidade: 1 });
const moeda = (valor) => `R$ ${Number(valor || 0).toFixed(4)}`;

export default function ApresentacoesTab() {
  const [itens, setItens] = useState([]);
  const [projetos, setProjetos] = useState([]);
  const [apresentacoes, setApresentacoes] = useState([]);
  const [mensagem, setMensagem] = useState("");

  const [itemCodigo, setItemCodigo] = useState("");
  const [itemNome, setItemNome] = useState("");
  const [itemUnidade, setItemUnidade] = useState("un");
  const [itemCusto, setItemCusto] = useState("");

  const [projetoId, setProjetoId] = useState("");
  const [versaoId, setVersaoId] = useState("");
  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState("");
  const [peso, setPeso] = useState("");
  const [unidadesCaixa, setUnidadesCaixa] = useState(1);
  const [componentes, setComponentes] = useState([componenteVazio()]);
  const [salvando, setSalvando] = useState(false);

  const carregar = async () => {
    try {
      const [novosItens, novosProjetos, novasApresentacoes] = await Promise.all([
        listarItensEmbalagem(),
        listarProjetos(),
        listarApresentacoes(),
      ]);
      setItens(novosItens);
      setProjetos(novosProjetos.filter((projeto) => projeto.status === "ATIVO"));
      setApresentacoes(novasApresentacoes);
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Não foi possível carregar os custos.");
    }
  };

  useEffect(() => {
    carregar();
  }, []);

  const projetoSelecionado = useMemo(
    () => projetos.find((projeto) => String(projeto.id) === projetoId),
    [projetos, projetoId]
  );
  const versoes = projetoSelecionado?.versoes || [];

  const selecionarProjeto = (id) => {
    setProjetoId(id);
    const projeto = projetos.find((item) => String(item.id) === id);
    setVersaoId(projeto?.versoes?.length ? String(projeto.versoes.at(-1).id) : "");
  };

  const cadastrarItem = async () => {
    if (!itemCodigo.trim() || !itemNome.trim() || itemCusto === "") {
      setMensagem("Informe código, nome e custo do componente.");
      return;
    }
    try {
      await criarItemEmbalagem({
        codigo: itemCodigo.trim(),
        nome: itemNome.trim(),
        unidade: itemUnidade.trim() || "un",
        custo_unitario: Number(itemCusto),
      });
      setItemCodigo("");
      setItemNome("");
      setItemCusto("");
      setMensagem("Componente cadastrado.");
      await carregar();
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao cadastrar componente.");
    }
  };

  const alternarItem = async (item) => {
    try {
      await atualizarItemEmbalagem(item.id, { ativo: !item.ativo });
      await carregar();
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao atualizar componente.");
    }
  };

  const alterarCustoItem = async (item) => {
    const informado = prompt(
      `Novo custo unitário de ${item.nome}:`,
      Number(item.custo_unitario).toString()
    );
    if (informado === null) return;
    const novoCusto = Number(informado.replace(",", "."));
    if (!Number.isFinite(novoCusto) || novoCusto < 0) {
      setMensagem("Informe um custo válido e não negativo.");
      return;
    }
    try {
      await atualizarItemEmbalagem(item.id, { custo_unitario: novoCusto });
      await carregar();
      setMensagem("Custo do componente atualizado. Os históricos foram preservados.");
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao atualizar o custo.");
    }
  };

  const atualizarComponente = (indice, campo, valor) => {
    setComponentes((atuais) =>
      atuais.map((item, i) => (i === indice ? { ...item, [campo]: valor } : item))
    );
  };

  const salvarApresentacao = async () => {
    const validos = componentes.filter((item) => item.item_embalagem_id);
    if (!projetoId || !versaoId || !codigo.trim() || !nome.trim() || !peso) {
      setMensagem("Informe projeto, versão, código, nome e peso líquido.");
      return;
    }
    setSalvando(true);
    try {
      const criada = await criarApresentacao({
        projeto_id: Number(projetoId),
        versao_formula_id: Number(versaoId),
        codigo: codigo.trim(),
        nome: nome.trim(),
        peso_liquido_g: Number(peso),
        unidades_por_caixa: Number(unidadesCaixa),
        componentes: validos.map((item) => ({
          item_embalagem_id: Number(item.item_embalagem_id),
          quantidade: Number(item.quantidade),
        })),
      });
      setCodigo("");
      setNome("");
      setPeso("");
      setComponentes([componenteVazio()]);
      setMensagem(`Apresentação salva: custo unitário ${moeda(criada.custo_unitario)}.`);
      await carregar();
    } catch (erro) {
      const detalhe = erro.response?.data?.detail;
      setMensagem(typeof detalhe === "string" ? detalhe : "Erro ao calcular apresentação.");
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-5 rounded shadow space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Componentes de embalagem</h2>
          <p className="text-sm text-gray-600">Cadastre pote, tampa, selo, rótulo, caixa e demais componentes com seu custo por unidade de consumo.</p>
        </div>
        <div className="grid md:grid-cols-5 gap-2">
          <input className="border rounded px-3 py-2" placeholder="Código" value={itemCodigo} onChange={(e) => setItemCodigo(e.target.value)} />
          <input className="border rounded px-3 py-2 md:col-span-2" placeholder="Nome do componente" value={itemNome} onChange={(e) => setItemNome(e.target.value)} />
          <input className="border rounded px-3 py-2" placeholder="Unidade" value={itemUnidade} onChange={(e) => setItemUnidade(e.target.value)} />
          <input type="number" min="0" step="0.0001" className="border rounded px-3 py-2" placeholder="Custo unitário" value={itemCusto} onChange={(e) => setItemCusto(e.target.value)} />
        </div>
        <button onClick={cadastrarItem} className="bg-blue-600 text-white px-4 py-2 rounded">Cadastrar componente</button>
        {itens.length > 0 && (
          <div className="overflow-x-auto border rounded">
            <table className="w-full text-sm">
              <thead className="bg-gray-100"><tr><th className="p-2 text-left">Código</th><th className="p-2 text-left">Componente</th><th className="p-2 text-left">Custo</th><th className="p-2 text-left">Situação</th><th /></tr></thead>
              <tbody>{itens.map((item) => <tr key={item.id} className="border-t"><td className="p-2">{item.codigo}</td><td className="p-2">{item.nome}</td><td className="p-2">{moeda(item.custo_unitario)} / {item.unidade}</td><td className="p-2">{item.ativo ? "Ativo" : "Inativo"}</td><td className="p-2 text-right space-x-3"><button onClick={() => alterarCustoItem(item)} className="text-indigo-700">Alterar custo</button><button onClick={() => alternarItem(item)} className="text-blue-700">{item.ativo ? "Desativar" : "Reativar"}</button></td></tr>)}</tbody>
            </table>
          </div>
        )}
      </div>

      <div className="bg-white p-5 rounded shadow space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Calcular nova apresentação</h2>
          <p className="text-sm text-gray-600">Selecione uma versão da fórmula e informe o peso e o conjunto de embalagens.</p>
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          <select className="border rounded px-3 py-2" value={projetoId} onChange={(e) => selecionarProjeto(e.target.value)}><option value="">Selecione o projeto</option>{projetos.map((projeto) => <option key={projeto.id} value={projeto.id}>{projeto.codigo} — {projeto.nome}</option>)}</select>
          <select className="border rounded px-3 py-2" value={versaoId} onChange={(e) => setVersaoId(e.target.value)}><option value="">Selecione a versão</option>{versoes.map((versao) => <option key={versao.id} value={versao.id}>v{versao.numero} — {moeda(versao.custo_total)}/kg</option>)}</select>
          <input className="border rounded px-3 py-2" placeholder="Código da apresentação" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
          <input className="border rounded px-3 py-2" placeholder="Nome da apresentação" value={nome} onChange={(e) => setNome(e.target.value)} />
          <input type="number" min="0.001" className="border rounded px-3 py-2" placeholder="Peso líquido (g)" value={peso} onChange={(e) => setPeso(e.target.value)} />
          <input type="number" min="1" className="border rounded px-3 py-2" placeholder="Unidades por caixa" value={unidadesCaixa} onChange={(e) => setUnidadesCaixa(e.target.value)} />
        </div>
        <div className="space-y-2">
          <div className="flex justify-between items-center"><h3 className="font-medium">Componentes utilizados</h3><button className="bg-gray-100 px-3 py-1 rounded" onClick={() => setComponentes((atuais) => [...atuais, componenteVazio()])}>+ Componente</button></div>
          {componentes.map((componente, indice) => <div key={indice} className="flex gap-2"><select className="border rounded px-3 py-2 flex-1" value={componente.item_embalagem_id} onChange={(e) => atualizarComponente(indice, "item_embalagem_id", e.target.value)}><option value="">Selecione</option>{itens.filter((item) => item.ativo).map((item) => <option key={item.id} value={item.id}>{item.nome} — {moeda(item.custo_unitario)}/{item.unidade}</option>)}</select><input type="number" min="0.000001" step="0.001" className="border rounded px-3 py-2 w-32" value={componente.quantidade} onChange={(e) => atualizarComponente(indice, "quantidade", e.target.value)} /><button className="text-red-600 px-2" onClick={() => setComponentes((atuais) => atuais.filter((_, i) => i !== indice))}>Remover</button></div>)}
        </div>
        <div className="flex items-center gap-3"><button disabled={salvando} onClick={salvarApresentacao} className="bg-indigo-600 disabled:bg-indigo-300 text-white px-4 py-2 rounded">{salvando ? "Calculando..." : "Calcular e salvar"}</button>{mensagem && <p className="text-sm text-gray-700">{mensagem}</p>}</div>
      </div>

      <div className="space-y-3">
        <h2 className="font-semibold">Histórico de custos por apresentação</h2>
        {apresentacoes.length === 0 && <div className="bg-white p-4 rounded shadow text-sm text-gray-600">Nenhuma apresentação calculada.</div>}
        {apresentacoes.map((item) => <div key={item.id} className="bg-white p-5 rounded shadow"><div className="flex flex-wrap justify-between gap-3"><div><strong>{item.codigo} — {item.nome}</strong><p className="text-sm text-gray-600">{Number(item.peso_liquido_g).toFixed(0)} g · versão da fórmula #{item.versao_formula_id} · {item.unidades_por_caixa} un./caixa</p></div><div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm"><div><span className="text-gray-500 block">Fórmula</span><strong>{moeda(item.custo_formula)}</strong></div><div><span className="text-gray-500 block">Embalagem</span><strong>{moeda(item.custo_embalagem)}</strong></div><div><span className="text-gray-500 block">Unidade</span><strong>{moeda(item.custo_unitario)}</strong></div><div><span className="text-gray-500 block">Caixa</span><strong>{moeda(item.custo_caixa)}</strong></div></div></div><div className="mt-3 text-xs text-gray-600">{item.componentes.map((componente) => `${componente.item_nome_snapshot} (${componente.quantidade} × ${moeda(componente.custo_unitario_snapshot)})`).join(" · ") || "Sem componentes de embalagem"}</div></div>)}
      </div>
    </div>
  );
}
