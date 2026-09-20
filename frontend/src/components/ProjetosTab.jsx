import React, { useEffect, useState } from "react";
import { atualizarProjeto, criarProjeto, listarCategoriasProduto, listarProjetos } from "../api/api";
import { mensagemErroApi } from "../utils/regulatory-ui.mjs";

const requisitoVazio = () => ({
  origem: "DESENVOLVIMENTO",
  tipo_item: "NUTRIENTE",
  item: "",
  minimo: "",
  maximo: "",
  unidade: "",
  observacao: "",
});

const statusClasses = {
  ATIVO: "bg-green-100 text-green-800",
  CONCLUIDO: "bg-blue-100 text-blue-800",
  ARQUIVADO: "bg-gray-200 text-gray-700",
};

export default function ProjetosTab() {
  const [projetos, setProjetos] = useState([]);
  const [categorias, setCategorias] = useState([]);
  const [categoriaId, setCategoriaId] = useState("");
  const [codigo, setCodigo] = useState("");
  const [nome, setNome] = useState("");
  const [descricao, setDescricao] = useState("");
  const [requisitos, setRequisitos] = useState([requisitoVazio()]);
  const [mensagem, setMensagem] = useState("");
  const [salvando, setSalvando] = useState(false);

  const carregar = async () => {
    try {
      const [dadosProjetos, dadosCategorias] = await Promise.all([listarProjetos(), listarCategoriasProduto(true)]);
      setProjetos(dadosProjetos);
      setCategorias(dadosCategorias);
    } catch (erro) {
      setMensagem(mensagemErroApi(erro, "Não foi possível carregar os projetos."));
    }
  };

  useEffect(() => {
    carregar();
  }, []);

  const atualizarRequisito = (indice, campo, valor) => {
    setRequisitos((atuais) =>
      atuais.map((item, i) => (i === indice ? { ...item, [campo]: valor } : item))
    );
  };

  const salvar = async () => {
    const preenchidos = requisitos.filter((item) => item.item.trim());
    if (!codigo.trim() || !nome.trim()) {
      setMensagem("Informe o código e o nome do projeto.");
      return;
    }
    if (preenchidos.some((item) => item.minimo === "" && item.maximo === "")) {
      setMensagem("Cada requisito deve possuir um limite mínimo ou máximo.");
      return;
    }

    setSalvando(true);
    try {
      await criarProjeto({
        codigo: codigo.trim(),
        nome: nome.trim(),
        descricao: descricao.trim() || null,
        categoria_produto_id: categoriaId ? Number(categoriaId) : null,
        requisitos: preenchidos.map((item) => ({
          ...item,
          minimo: item.minimo === "" ? null : Number(item.minimo),
          maximo: item.maximo === "" ? null : Number(item.maximo),
          unidade: item.unidade.trim() || null,
          observacao: item.observacao.trim() || null,
        })),
      });
      setCodigo("");
      setNome("");
      setDescricao("");
      setCategoriaId("");
      setRequisitos([requisitoVazio()]);
      setMensagem("Projeto criado com sucesso.");
      await carregar();
    } catch (erro) {
      setMensagem(mensagemErroApi(erro, "Erro ao criar o projeto."));
    } finally {
      setSalvando(false);
    }
  };

  const alterarStatus = async (projeto, status) => {
    try {
      await atualizarProjeto(projeto.id, { status });
      await carregar();
      setMensagem("Status do projeto atualizado.");
    } catch (erro) {
      setMensagem(erro.response?.data?.detail || "Erro ao atualizar o projeto.");
    }
  };

  const alterarCategoria = async (projeto, valor) => {
    try {
      await atualizarProjeto(projeto.id, { categoria_produto_id: valor ? Number(valor) : null });
      await carregar();
      setMensagem("Categoria do projeto atualizada. Projetos históricos não foram alterados automaticamente.");
    } catch (erro) { setMensagem(mensagemErroApi(erro, "Erro ao atualizar a categoria.")); }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-6 rounded shadow space-y-4">
        <div>
          <h2 className="text-lg font-semibold">Novo projeto de desenvolvimento</h2>
          <p className="text-sm text-gray-600">
            Registre o briefing técnico antes de salvar versões da formulação.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-3">
          <label className="text-sm"><span className="block font-medium mb-1">Código</span><input className="border rounded px-3 py-2 w-full" value={codigo} onChange={(e) => setCodigo(e.target.value)} /></label>
          <label className="text-sm md:col-span-2"><span className="block font-medium mb-1">Nome do projeto</span><input className="border rounded px-3 py-2 w-full" value={nome} onChange={(e) => setNome(e.target.value)} /></label>
          <label className="text-sm md:col-span-3"><span className="block font-medium mb-1">Categoria de produto (opcional)</span><select className="border rounded px-3 py-2 w-full" value={categoriaId} onChange={(e)=>setCategoriaId(e.target.value)}><option value="">Sem categoria — sem avaliação regulatória</option>{categorias.map((categoria)=><option key={categoria.id} value={categoria.id}>{categoria.codigo} — {categoria.nome}</option>)}</select></label>
          <textarea aria-label="Descrição ou objetivo do projeto" className="border rounded px-3 py-2 md:col-span-3" placeholder="Descrição / objetivo" value={descricao} onChange={(e) => setDescricao(e.target.value)} />
        </div>

        <div className="space-y-2">
          <div className="flex justify-between items-center">
            <h3 className="font-medium">Requisitos</h3>
            <button className="px-3 py-1 rounded bg-gray-100" onClick={() => setRequisitos((atuais) => [...atuais, requisitoVazio()])}>+ Requisito</button>
          </div>
          {requisitos.map((item, indice) => (
            <div key={indice} className="grid md:grid-cols-12 gap-2 p-3 border rounded bg-gray-50">
              <select aria-label={`Origem do requisito ${indice + 1}`} className="border rounded px-2 py-2 md:col-span-2" value={item.origem} onChange={(e) => atualizarRequisito(indice, "origem", e.target.value)}>
                <option value="DESENVOLVIMENTO">Desenvolvimento</option>
                <option value="TECNICO">Técnico</option>
                <option value="REGULATORIO">Regulatório</option>
              </select>
              <select aria-label={`Tipo do requisito ${indice + 1}`} className="border rounded px-2 py-2 md:col-span-2" value={item.tipo_item} onChange={(e) => atualizarRequisito(indice, "tipo_item", e.target.value)}>
                <option value="NUTRIENTE">Nutriente</option>
                <option value="MP">Matéria-prima</option>
                <option value="CUSTO">Custo</option>
              </select>
              <input aria-label={`Item do requisito ${indice + 1}`} className="border rounded px-2 py-2 md:col-span-2" placeholder="Item" value={item.item} onChange={(e) => atualizarRequisito(indice, "item", e.target.value)} />
              <input aria-label={`Mínimo do requisito ${indice + 1}`} type="number" className="border rounded px-2 py-2 md:col-span-2" placeholder="Mínimo" value={item.minimo} onChange={(e) => atualizarRequisito(indice, "minimo", e.target.value)} />
              <input aria-label={`Máximo do requisito ${indice + 1}`} type="number" className="border rounded px-2 py-2 md:col-span-2" placeholder="Máximo" value={item.maximo} onChange={(e) => atualizarRequisito(indice, "maximo", e.target.value)} />
              <input aria-label={`Unidade do requisito ${indice + 1}`} className="border rounded px-2 py-2" placeholder="Unidade" value={item.unidade} onChange={(e) => atualizarRequisito(indice, "unidade", e.target.value)} />
              <button className="text-red-600" onClick={() => setRequisitos((atuais) => atuais.filter((_, i) => i !== indice))}>Remover</button>
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <button disabled={salvando} onClick={salvar} className="bg-blue-600 disabled:bg-blue-300 text-white px-4 py-2 rounded">{salvando ? "Salvando..." : "Criar projeto"}</button>
          {mensagem && <p className="text-sm text-gray-700">{mensagem}</p>}
        </div>
      </div>

      <div className="space-y-3">
        <h2 className="font-semibold">Projetos e histórico de versões</h2>
        {projetos.length === 0 && <div className="bg-white p-4 rounded shadow text-sm text-gray-600">Nenhum projeto cadastrado.</div>}
        {projetos.map((projeto) => (
          <div key={projeto.id} className="bg-white p-5 rounded shadow space-y-3">
            <div className="flex flex-wrap justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <strong>{projeto.codigo} — {projeto.nome}</strong>
                  <span className={`text-xs px-2 py-1 rounded ${statusClasses[projeto.status]}`}>{projeto.status}</span>
                </div>
                {projeto.descricao && <p className="text-sm text-gray-600 mt-1">{projeto.descricao}</p>}
                <p className="text-sm mt-1">Categoria: <strong>{categorias.find((c)=>c.id===projeto.categoria_produto_id)?.nome || "Sem categoria — sem avaliação regulatória"}</strong></p>
              </div>
              <select aria-label={`Status do projeto ${projeto.codigo}`} className="border rounded px-2 py-1 text-sm" value={projeto.status} onChange={(e) => alterarStatus(projeto, e.target.value)}>
                <option value="ATIVO">Ativo</option>
                <option value="CONCLUIDO">Concluído</option>
                <option value="ARQUIVADO">Arquivado</option>
              </select>
              <select aria-label={`Categoria do projeto ${projeto.codigo}`} className="border rounded px-2 py-1 text-sm" value={projeto.categoria_produto_id || ""} onChange={(e)=>alterarCategoria(projeto,e.target.value)}><option value="">Sem categoria</option>{categorias.map((categoria)=><option key={categoria.id} value={categoria.id}>{categoria.nome}</option>)}</select>
            </div>
            <div className="grid md:grid-cols-2 gap-4 text-sm">
              <div>
                <h4 className="font-medium mb-1">Requisitos atuais</h4>
                {projeto.requisitos.length === 0 ? <p className="text-gray-500">Sem requisitos.</p> : (
                  <ul className="space-y-1">{projeto.requisitos.map((req, i) => <li key={i}>{req.item}: {req.minimo != null ? `mín. ${req.minimo}` : ""} {req.maximo != null ? `máx. ${req.maximo}` : ""} {req.unidade || ""}</li>)}</ul>
                )}
              </div>
              <div>
                <h4 className="font-medium mb-1">Versões imutáveis</h4>
                {projeto.versoes.length === 0 ? <p className="text-gray-500">Nenhuma versão salva.</p> : (
                  <ul className="space-y-1">{projeto.versoes.map((versao) => <li key={versao.id}><strong>v{versao.numero}</strong> · {versao.status_solver} · {versao.custo_total == null ? "sem custo" : `R$ ${Number(versao.custo_total).toFixed(4)}`} {versao.observacao ? `— ${versao.observacao}` : ""}</li>)}</ul>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
