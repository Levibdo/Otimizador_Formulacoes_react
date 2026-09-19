import React, { useEffect, useMemo, useState } from "react";
import { criarCenario, listarCenarios, listarProjetos } from "../api/api";

const moeda = (valor) => `R$ ${Number(valor || 0).toFixed(4)}`;
const percentual = (valor) => `${Number(valor || 0).toFixed(2)}%`;

export default function CenariosTab() {
  const [projetos, setProjetos] = useState([]);
  const [cenarios, setCenarios] = useState([]);
  const [projetoId, setProjetoId] = useState("");
  const [versaoId, setVersaoId] = useState("");
  const [nome, setNome] = useState("");
  const [observacao, setObservacao] = useState("");
  const [ajustes, setAjustes] = useState({});
  const [mensagem, setMensagem] = useState("");
  const [salvando, setSalvando] = useState(false);

  const carregar = async () => {
    try {
      const [dadosProjetos, dadosCenarios] = await Promise.all([
        listarProjetos(),
        listarCenarios(),
      ]);
      setProjetos(dadosProjetos);
      setCenarios(dadosCenarios);
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Não foi possível carregar os cenários.");
    }
  };

  useEffect(() => {
    carregar();
  }, []);

  const projeto = useMemo(
    () => projetos.find((item) => String(item.id) === projetoId),
    [projetos, projetoId]
  );
  const versoes = projeto?.versoes || [];
  const versao = versoes.find((item) => String(item.id) === versaoId);
  const materias = versao
    ? Object.entries(versao.inclusoes || {}).filter(([, inclusao]) => Number(inclusao) > 0)
    : [];

  const selecionarProjeto = (id) => {
    setProjetoId(id);
    setVersaoId("");
    setAjustes({});
  };

  const selecionarVersao = (id) => {
    setVersaoId(id);
    setAjustes({});
  };

  const precoBase = (materiaPrima) =>
    Number(versao?.matriz_snapshot?.[materiaPrima]?.Custo || 0);

  const alterarPercentual = (materiaPrima, valor) => {
    setAjustes((atuais) => ({
      ...atuais,
      [materiaPrima]: valor,
    }));
  };

  const salvar = async () => {
    const alterados = Object.entries(ajustes).filter(([, valor]) => valor !== "" && Number(valor) !== 0);
    if (!projetoId || !versaoId || !nome.trim()) {
      setMensagem("Selecione o projeto e a versão e informe o nome do cenário.");
      return;
    }
    if (alterados.length === 0) {
      setMensagem("Informe ao menos uma variação percentual diferente de zero.");
      return;
    }
    const precos = Object.fromEntries(
      alterados.map(([materiaPrima, variacao]) => [
        materiaPrima,
        precoBase(materiaPrima) * (1 + Number(variacao) / 100),
      ])
    );
    setSalvando(true);
    try {
      const criado = await criarCenario({
        projeto_id: Number(projetoId),
        versao_formula_id: Number(versaoId),
        nome: nome.trim(),
        observacao: observacao.trim() || null,
        precos_cenario: precos,
      });
      setNome("");
      setObservacao("");
      setAjustes({});
      setMensagem(`Cenário salvo: ${moeda(criado.custo_cenario_kg)}/kg.`);
      await carregar();
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao calcular o cenário.");
    } finally {
      setSalvando(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-5 rounded shadow space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Novo cenário de preços</h2>
          <p className="text-sm text-gray-600">Simule altas ou quedas nos preços mantendo a fórmula e os registros originais intactos.</p>
        </div>
        <div className="grid md:grid-cols-2 gap-3">
          <select className="border rounded px-3 py-2" value={projetoId} onChange={(e) => selecionarProjeto(e.target.value)}><option value="">Selecione o projeto</option>{projetos.map((item) => <option key={item.id} value={item.id}>{item.codigo} — {item.nome}</option>)}</select>
          <select className="border rounded px-3 py-2" value={versaoId} onChange={(e) => selecionarVersao(e.target.value)}><option value="">Selecione a versão</option>{versoes.map((item) => <option key={item.id} value={item.id}>v{item.numero} — {moeda(item.custo_total)}/kg</option>)}</select>
          <input className="border rounded px-3 py-2" placeholder="Nome do cenário" value={nome} onChange={(e) => setNome(e.target.value)} />
          <input className="border rounded px-3 py-2" placeholder="Observação (opcional)" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        </div>

        {versao && (
          <div className="overflow-x-auto border rounded">
            <table className="w-full text-sm">
              <thead className="bg-gray-100"><tr><th className="p-2 text-left">Matéria-prima</th><th className="p-2 text-right">Inclusão</th><th className="p-2 text-right">Preço-base/kg</th><th className="p-2 text-right">Variação</th><th className="p-2 text-right">Preço projetado/kg</th></tr></thead>
              <tbody>{materias.map(([materiaPrima, inclusao]) => { const ajuste = ajustes[materiaPrima] ?? ""; const projetado = precoBase(materiaPrima) * (1 + Number(ajuste || 0) / 100); return <tr key={materiaPrima} className="border-t"><td className="p-2">{materiaPrima}</td><td className="p-2 text-right">{percentual(inclusao)}</td><td className="p-2 text-right">{moeda(precoBase(materiaPrima))}</td><td className="p-2 text-right"><input type="number" step="0.1" className="border rounded px-2 py-1 w-28 text-right" placeholder="0%" value={ajuste} onChange={(e) => alterarPercentual(materiaPrima, e.target.value)} /></td><td className="p-2 text-right font-medium">{moeda(projetado)}</td></tr>; })}</tbody>
            </table>
          </div>
        )}
        <div className="flex items-center gap-3"><button disabled={salvando} onClick={salvar} className="bg-indigo-600 disabled:bg-indigo-300 text-white px-4 py-2 rounded">{salvando ? "Calculando..." : "Calcular e salvar cenário"}</button>{mensagem && <p className="text-sm text-gray-700">{mensagem}</p>}</div>
      </div>

      <div className="space-y-3">
        <h2 className="font-semibold">Cenários salvos</h2>
        {cenarios.length === 0 && <div className="bg-white p-4 rounded shadow text-sm text-gray-600">Nenhum cenário calculado.</div>}
        {cenarios.map((cenario) => {
          const positiva = Number(cenario.variacao_absoluta) >= 0;
          return <div key={cenario.id} className="bg-white p-5 rounded shadow space-y-3"><div className="flex flex-wrap justify-between gap-3"><div><strong>{cenario.nome}</strong><p className="text-sm text-gray-600">Projeto #{cenario.projeto_id} · versão #{cenario.versao_formula_id}{cenario.observacao ? ` — ${cenario.observacao}` : ""}</p></div><div className="grid grid-cols-3 gap-5 text-sm"><div><span className="block text-gray-500">Base</span><strong>{moeda(cenario.custo_base_kg)}/kg</strong></div><div><span className="block text-gray-500">Cenário</span><strong>{moeda(cenario.custo_cenario_kg)}/kg</strong></div><div><span className="block text-gray-500">Variação</span><strong className={positiva ? "text-red-600" : "text-green-700"}>{positiva ? "+" : ""}{moeda(cenario.variacao_absoluta)} ({positiva ? "+" : ""}{percentual(cenario.variacao_percentual)})</strong></div></div></div>{cenario.impacto_apresentacoes.length > 0 && <div className="border-t pt-3"><h4 className="text-sm font-medium mb-2">Impacto nas apresentações</h4><div className="grid md:grid-cols-2 gap-2">{cenario.impacto_apresentacoes.map((impacto) => <div key={impacto.apresentacao_id} className="bg-gray-50 p-3 rounded text-sm"><strong>{impacto.codigo} — {impacto.nome}</strong><div className="mt-1 text-gray-700">Unidade: {moeda(impacto.custo_unitario_base)} → {moeda(impacto.custo_unitario_cenario)}</div><div className="text-gray-700">Caixa: {moeda(impacto.custo_caixa_base)} → {moeda(impacto.custo_caixa_cenario)}</div></div>)}</div></div>}</div>;
        })}
      </div>
    </div>
  );
}
