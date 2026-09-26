import React, { useEffect, useState } from "react";
import {
  adicionarPrecoMateriaPrima,
  atualizarMateriaPrima,
  criarMateriaPrima,
  importarMateriasPrimas,
  listarMateriasPrimas,
} from "../api/api";

const nutrienteVazio = () => ({
  nutriente_codigo: "",
  nutriente_nome: "",
  unidade: "g/100 g",
  valor: "",
});

const dataLocal = () => {
  const hoje = new Date();
  const offset = hoje.getTimezoneOffset() * 60000;
  return new Date(hoje.getTime() - offset).toISOString().slice(0, 10);
};

export default function MateriasPrimasTab() {
  const [materias, setMaterias] = useState([]);
  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState("");
  const [preco, setPreco] = useState("");
  const [vigenciaInicio, setVigenciaInicio] = useState(dataLocal());
  const [composicao, setComposicao] = useState([nutrienteVazio()]);
  const [mensagem, setMensagem] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [arquivo, setArquivo] = useState(null);
  const [unidadePadrao, setUnidadePadrao] = useState("não informada");
  const [editandoId, setEditandoId] = useState(null);
  const [materiaPreco, setMateriaPreco] = useState(null);
  const [novoPreco, setNovoPreco] = useState("");
  const [novaVigenciaInicio, setNovaVigenciaInicio] = useState(dataLocal());
  const [novaVigenciaFim, setNovaVigenciaFim] = useState("");

  const carregarMaterias = async () => {
    setCarregando(true);
    try {
      setMaterias(await listarMateriasPrimas());
      setMensagem("");
    } catch (erro) {
      setMensagem(
        erro.response?.data?.detail || "Não foi possível carregar as matérias-primas."
      );
    } finally {
      setCarregando(false);
    }
  };

  useEffect(() => {
    carregarMaterias();
  }, []);

  const atualizarNutriente = (indice, campo, valor) => {
    setComposicao((atual) =>
      atual.map((item, i) => (i === indice ? { ...item, [campo]: valor } : item))
    );
  };

  const adicionarNutriente = () => {
    setComposicao((atual) => [...atual, nutrienteVazio()]);
  };

  const removerNutriente = (indice) => {
    setComposicao((atual) => atual.filter((_, i) => i !== indice));
  };

  const limparFormulario = () => {
    setCodigo("");
    setNome("");
    setPreco("");
    setVigenciaInicio(dataLocal());
    setComposicao([nutrienteVazio()]);
    setEditandoId(null);
  };

  const adicionarMateria = async () => {
    const nutrientesValidos = composicao.filter(
      (item) => item.nutriente_codigo && item.nutriente_nome && item.unidade
    );

    if (!codigo || !nome || (!editandoId && preco === "")) {
      setMensagem(
        editandoId
          ? "Preencha código e nome da matéria-prima."
          : "Preencha código, nome e preço da matéria-prima."
      );
      return;
    }
    if (nutrientesValidos.some((item) => item.valor === "")) {
      setMensagem("Informe o valor de todos os nutrientes preenchidos.");
      return;
    }

    try {
      const dadosBasicos = {
        codigo,
        nome,
        composicao: nutrientesValidos.map((item) => ({
          ...item,
          valor: Number(item.valor),
        })),
      };
      if (editandoId) {
        await atualizarMateriaPrima(editandoId, dadosBasicos);
      } else {
        await criarMateriaPrima({
          ...dadosBasicos,
          preco_inicial: {
            preco_kg: Number(preco),
            vigencia_inicio: vigenciaInicio,
          },
        });
      }
      limparFormulario();
      await carregarMaterias();
      setMensagem(
        editandoId
          ? "Matéria-prima atualizada com sucesso."
          : "Matéria-prima cadastrada com sucesso."
      );
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao cadastrar matéria-prima.");
    }
  };

  const importar = async () => {
    if (!arquivo) {
      setMensagem("Selecione um arquivo .xlsx ou .csv.");
      return;
    }

    setCarregando(true);
    try {
      const resultado = await importarMateriasPrimas(
        arquivo,
        vigenciaInicio,
        unidadePadrao
      );
      await carregarMaterias();
      setArquivo(null);
      setMensagem(
        `${resultado.materias_primas_importadas} matérias-primas importadas. ` +
          `${resultado.unidades_nao_informadas} valores ficaram com unidade não informada.`
      );
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao importar planilha.");
    } finally {
      setCarregando(false);
    }
  };

  const alternarStatus = async (materiaPrima) => {
    const acao = materiaPrima.ativa ? "desativar" : "reativar";
    if (!confirm(`${acao === "desativar" ? "Desativar" : "Reativar"} ${materiaPrima.nome}?`)) return;

    try {
      await atualizarMateriaPrima(materiaPrima.id, { ativa: !materiaPrima.ativa });
      await carregarMaterias();
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || `Erro ao ${acao} matéria-prima.`);
    }
  };

  const iniciarEdicao = (materiaPrima) => {
    setEditandoId(materiaPrima.id);
    setCodigo(materiaPrima.codigo);
    setNome(materiaPrima.nome);
    setPreco("");
    setComposicao(
      materiaPrima.composicao.length
        ? materiaPrima.composicao.map((item) => ({ ...item, valor: Number(item.valor) }))
        : [nutrienteVazio()]
    );
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const abrirPrecos = (materiaPrima) => {
    setMateriaPreco(materiaPrima);
    setNovoPreco("");
    setNovaVigenciaInicio(dataLocal());
    setNovaVigenciaFim("");
  };

  const salvarNovoPreco = async () => {
    if (!materiaPreco || novoPreco === "") {
      setMensagem("Informe o novo preço.");
      return;
    }
    try {
      const atualizada = await adicionarPrecoMateriaPrima(materiaPreco.id, {
        preco_kg: Number(novoPreco),
        vigencia_inicio: novaVigenciaInicio,
        vigencia_fim: novaVigenciaFim || null,
      });
      setMateriaPreco(atualizada);
      setNovoPreco("");
      await carregarMaterias();
      setMensagem("Novo preço registrado com sucesso.");
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao registrar preço.");
    }
  };

  const precoAtual = (materiaPrima) => {
    const hoje = dataLocal();
    return materiaPrima.precos?.find(
      (item) =>
        item.vigencia_inicio <= hoje &&
        (!item.vigencia_fim || item.vigencia_fim >= hoje)
    )?.preco_kg;
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-6 rounded shadow space-y-4">
        <div>
          <h2 className="text-xl font-semibold">Cadastro de Matérias-Primas</h2>
          <p className="text-sm text-gray-600">
            Fonte oficial: PostgreSQL. A composição aceita qualquer quantidade de nutrientes.
          </p>
        </div>

        <div className="border rounded p-4 space-y-3 bg-gray-50">
          <div>
            <h3 className="font-medium">Importação rápida de matérias-primas — formato legado</h3>
            <p className="text-xs text-gray-600">
              Aceita matriz transposta (MPs nas colunas) ou tabela vertical com Nome e Custo.
              A importação é cancelada integralmente se houver erro ou conflito. Este formato não possui pré-visualização nem confirmação em duas etapas.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <label className="text-sm md:col-span-2">
              Arquivo
              <input
                type="file"
                accept=".xlsx,.csv"
                onChange={(e) => setArquivo(e.target.files?.[0] || null)}
                className="block w-full border p-2 rounded bg-white"
              />
            </label>
            <label className="text-sm">
              Unidade quando ausente
              <input
                value={unidadePadrao}
                onChange={(e) => setUnidadePadrao(e.target.value)}
                className="block w-full border p-2 rounded bg-white"
              />
            </label>
            <button
              type="button"
              onClick={importar}
              disabled={carregando}
              className="bg-green-600 disabled:bg-gray-300 text-white px-4 py-2 rounded"
            >
              {carregando ? "Importando..." : "Importar para PostgreSQL"}
            </button>
          </div>
          <p className="text-xs text-amber-700">
            Use “não informada” quando a planilha misturar g, mg, µg e kcal sem declarar as unidades.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            placeholder="Código (ex.: MP0001)"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value)}
            className="border p-2 rounded"
          />
          <input
            placeholder="Nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="border p-2 rounded"
          />
          {!editandoId && (
            <>
              <input
                type="number"
                min="0"
                step="0.0001"
                placeholder="Preço (R$/kg)"
                value={preco}
                onChange={(e) => setPreco(e.target.value)}
                className="border p-2 rounded"
              />
              <input
                type="date"
                value={vigenciaInicio}
                onChange={(e) => setVigenciaInicio(e.target.value)}
                className="border p-2 rounded"
              />
            </>
          )}
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="font-medium">Composição nutricional</h3>
            <button
              type="button"
              onClick={adicionarNutriente}
              className="bg-gray-100 px-3 py-1 rounded"
            >
              + Nutriente
            </button>
          </div>

          {composicao.map((item, indice) => (
            <div key={indice} className="grid grid-cols-1 md:grid-cols-5 gap-2">
              <input
                placeholder="Código (PROT)"
                value={item.nutriente_codigo}
                onChange={(e) =>
                  atualizarNutriente(indice, "nutriente_codigo", e.target.value)
                }
                className="border p-2 rounded"
              />
              <input
                placeholder="Nutriente"
                value={item.nutriente_nome}
                onChange={(e) =>
                  atualizarNutriente(indice, "nutriente_nome", e.target.value)
                }
                className="border p-2 rounded"
              />
              <input
                placeholder="Unidade"
                value={item.unidade}
                onChange={(e) => atualizarNutriente(indice, "unidade", e.target.value)}
                className="border p-2 rounded"
              />
              <input
                type="number"
                min="0"
                step="0.000001"
                placeholder="Valor"
                value={item.valor}
                onChange={(e) => atualizarNutriente(indice, "valor", e.target.value)}
                className="border p-2 rounded"
              />
              <button
                type="button"
                onClick={() => removerNutriente(indice)}
                disabled={composicao.length === 1}
                className="text-red-600 disabled:text-gray-300"
              >
                Remover
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={adicionarMateria}
            className="bg-blue-600 text-white px-4 py-2 rounded"
          >
            {editandoId ? "Salvar alterações" : "Cadastrar matéria-prima"}
          </button>
          {editandoId && (
            <button
              type="button"
              onClick={limparFormulario}
              className="bg-gray-200 px-4 py-2 rounded"
            >
              Cancelar edição
            </button>
          )}
          {mensagem && <p className="text-sm text-gray-700">{mensagem}</p>}
        </div>
      </div>

      <div className="bg-white p-6 rounded shadow overflow-x-auto">
        <h3 className="font-medium mb-3">Matérias-primas cadastradas</h3>
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-gray-100">
              <th className="border p-2 text-left">Código</th>
              <th className="border p-2 text-left">Matéria-prima</th>
              <th className="border p-2 text-left">Preço atual</th>
              <th className="border p-2 text-left">Composição</th>
              <th className="border p-2 text-left">Status</th>
              <th className="border p-2 text-center">Ações</th>
            </tr>
          </thead>
          <tbody>
            {materias.length === 0 ? (
              <tr>
                <td colSpan="6" className="text-center p-4 text-gray-500">
                  {carregando ? "Carregando..." : "Nenhuma matéria-prima cadastrada."}
                </td>
              </tr>
            ) : (
              materias.map((mp) => (
                <tr key={mp.id} className="border-t">
                  <td className="p-2">{mp.codigo}</td>
                  <td className="p-2">{mp.nome}</td>
                  <td className="p-2">
                    {precoAtual(mp) == null
                      ? "Sem preço"
                      : `R$ ${Number(precoAtual(mp)).toFixed(4)}/kg`}
                  </td>
                  <td className="p-2">
                    {mp.composicao
                      .map(
                        (item) =>
                          `${item.nutriente_nome}: ${Number(item.valor)} ${item.unidade}`
                      )
                      .join("; ") || "Sem composição"}
                  </td>
                  <td className="p-2">{mp.ativa ? "Ativa" : "Inativa"}</td>
                  <td className="p-2 text-center">
                    <div className="flex flex-wrap justify-center gap-1">
                      <button
                        onClick={() => iniciarEdicao(mp)}
                        className="bg-blue-600 text-white px-2 py-1 rounded text-xs"
                      >
                        Editar
                      </button>
                      <button
                        onClick={() => abrirPrecos(mp)}
                        className="bg-amber-600 text-white px-2 py-1 rounded text-xs"
                      >
                        Preços
                      </button>
                      <button
                        onClick={() => alternarStatus(mp)}
                        className={`${
                          mp.ativa ? "bg-red-600" : "bg-green-600"
                        } text-white px-2 py-1 rounded text-xs`}
                      >
                        {mp.ativa ? "Desativar" : "Reativar"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {materiaPreco && (
        <div className="bg-white p-6 rounded shadow space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="font-medium">Preços — {materiaPreco.nome}</h3>
              <p className="text-xs text-gray-600">
                Um novo preço fecha automaticamente a vigência aberta anterior.
              </p>
            </div>
            <button onClick={() => setMateriaPreco(null)} className="text-gray-600">
              Fechar
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <label className="text-sm">
              Preço (R$/kg)
              <input
                type="number"
                min="0"
                step="0.0001"
                value={novoPreco}
                onChange={(e) => setNovoPreco(e.target.value)}
                className="block w-full border p-2 rounded"
              />
            </label>
            <label className="text-sm">
              Início
              <input
                type="date"
                value={novaVigenciaInicio}
                onChange={(e) => setNovaVigenciaInicio(e.target.value)}
                className="block w-full border p-2 rounded"
              />
            </label>
            <label className="text-sm">
              Fim opcional
              <input
                type="date"
                value={novaVigenciaFim}
                onChange={(e) => setNovaVigenciaFim(e.target.value)}
                className="block w-full border p-2 rounded"
              />
            </label>
            <button
              onClick={salvarNovoPreco}
              className="bg-amber-600 text-white px-4 py-2 rounded"
            >
              Registrar preço
            </button>
          </div>

          <table className="w-full text-sm border-collapse">
            <thead className="bg-gray-100">
              <tr>
                <th className="border p-2 text-left">Preço</th>
                <th className="border p-2 text-left">Início</th>
                <th className="border p-2 text-left">Fim</th>
              </tr>
            </thead>
            <tbody>
              {materiaPreco.precos.map((item) => (
                <tr key={item.id}>
                  <td className="border p-2">R$ {Number(item.preco_kg).toFixed(4)}</td>
                  <td className="border p-2">{item.vigencia_inicio}</td>
                  <td className="border p-2">{item.vigencia_fim || "Em aberto"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
