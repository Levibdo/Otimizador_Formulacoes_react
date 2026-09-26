import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  baixarTemplateImportacaoCadastral,
  confirmarImportacaoCadastral,
  prepararImportacaoCadastral,
  validarImportacaoCadastral,
} from "../api/api";
import {
  ESTADOS_IMPORTACAO,
  botoesPorEstado,
  erroConfirmacao,
  estadoAoTrocarArquivo,
  hashesConferem,
  hashResumido,
  mensagemSeguraImportacao,
  pagina,
  respostaPertenceAoFluxo,
  resumoDaValidacao,
  sessaoExpirada,
  validarArquivoSelecionado,
} from "../utils/importacao-cadastral-ui.mjs";

const TAMANHO_PAGINA = 20;
const botao = "px-4 py-2 rounded font-medium disabled:bg-gray-300 disabled:text-gray-600 disabled:cursor-not-allowed";
const nomesAba = {
  MATERIAS_PRIMAS: "Matérias-primas",
  NUTRIENTES: "Nutrientes",
  COMPOSICAO_NUTRICIONAL: "Composição nutricional",
  PRECOS_MP: "Preços",
  GERAL: "Geral",
};

function formatarTamanho(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function Paginacao({ dados, paginaAtual, setPaginaAtual, renderItem, vazio }) {
  const bloco = pagina(dados, paginaAtual, TAMANHO_PAGINA);
  useEffect(() => setPaginaAtual((atual) => Math.min(atual, bloco.paginas)), [bloco.paginas, setPaginaAtual]);
  if (!bloco.total) return <p className="text-sm text-gray-500">{vazio}</p>;
  return <div className="space-y-3">
    <div className="space-y-2">{bloco.itens.map(renderItem)}</div>
    <div className="flex items-center justify-between text-sm" aria-label="Paginação">
      <button className="underline disabled:text-gray-400" disabled={bloco.atual === 1} onClick={() => setPaginaAtual(bloco.atual - 1)}>Anterior</button>
      <span>Página {bloco.atual} de {bloco.paginas} · {bloco.total} itens</span>
      <button className="underline disabled:text-gray-400" disabled={bloco.atual === bloco.paginas} onClick={() => setPaginaAtual(bloco.atual + 1)}>Próxima</button>
    </div>
  </div>;
}

export default function ImportacaoCadastralTab({ aoConfirmar }) {
  const [arquivo, setArquivo] = useState(null);
  const [validacao, setValidacao] = useState(null);
  const [sessao, setSessao] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [mensagem, setMensagem] = useState("");
  const [estado, setEstado] = useState(ESTADOS_IMPORTACAO.SEM_ARQUIVO);
  const [confirmarAberto, setConfirmarAberto] = useState(false);
  const [paginaDiagnosticos, setPaginaDiagnosticos] = useState(1);
  const [paginaOperacoes, setPaginaOperacoes] = useState(1);
  const [chaveInput, setChaveInput] = useState(0);
  const geracaoRef = useRef(0);
  const controladorRef = useRef(null);
  const ocupadoRef = useRef(false);

  const invalidarPendencias = () => {
    geracaoRef.current += 1;
    controladorRef.current?.abort();
    controladorRef.current = null;
    ocupadoRef.current = false;
  };

  useEffect(() => () => {
    geracaoRef.current += 1;
    controladorRef.current?.abort();
    ocupadoRef.current = false;
  }, []);

  const iniciarRequisicao = () => {
    if (ocupadoRef.current) return null;
    ocupadoRef.current = true;
    const controlador = new AbortController();
    controladorRef.current = controlador;
    return { geracao: geracaoRef.current, controlador };
  };

  const respostaAtual = (requisicao) => respostaPertenceAoFluxo(
    requisicao.geracao, geracaoRef.current, requisicao.controlador.signal.aborted
  );

  const finalizarRequisicao = (requisicao) => {
    if (respostaAtual(requisicao)) {
      ocupadoRef.current = false;
      controladorRef.current = null;
    }
  };

  const trocarArquivo = (evento) => {
    invalidarPendencias();
    const novo = evento.target.files?.[0] || null;
    const limpo = estadoAoTrocarArquivo(novo);
    setArquivo(limpo.arquivo); setValidacao(limpo.validacao); setSessao(limpo.sessao);
    setResultado(limpo.resultado); setConfirmarAberto(false);
    setPaginaDiagnosticos(1); setPaginaOperacoes(1);
    const erro = validarArquivoSelecionado(novo);
    setMensagem(erro || "Arquivo selecionado. Faça a validação antes de preparar.");
    setEstado(erro ? ESTADOS_IMPORTACAO.SEM_ARQUIVO : ESTADOS_IMPORTACAO.ARQUIVO_SELECIONADO);
  };

  const botoes = botoesPorEstado(estado);
  const totais = useMemo(() => resumoDaValidacao(validacao), [validacao]);

  const baixar = async () => {
    const req = iniciarRequisicao(); if (!req) return;
    setMensagem("");
    let url = null;
    try {
      const blob = await baixarTemplateImportacaoCadastral(req.controlador.signal);
      if (!respostaAtual(req)) return;
      url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = "template-cadastral-v1.0.xlsx"; link.click();
    } catch (erro) {
      if (respostaAtual(req)) { const texto = mensagemSeguraImportacao(erro, "download"); if (texto) setMensagem(texto); }
    } finally {
      if (url) URL.revokeObjectURL(url);
      finalizarRequisicao(req);
    }
  };

  const validar = async () => {
    if (!botoes.validar || validarArquivoSelecionado(arquivo)) return;
    const req = iniciarRequisicao(); if (!req) return;
    setEstado(ESTADOS_IMPORTACAO.VALIDANDO); setMensagem(""); setValidacao(null); setSessao(null); setResultado(null);
    try {
      const dados = await validarImportacaoCadastral(arquivo, req.controlador.signal);
      if (!respostaAtual(req)) return;
      if (!dados || typeof dados.valido_para_confirmacao !== "boolean" || typeof dados.sha256 !== "string") throw new Error("Resposta inválida");
      setValidacao(dados);
      setEstado(dados.valido_para_confirmacao ? ESTADOS_IMPORTACAO.VALIDADO_APTO : ESTADOS_IMPORTACAO.VALIDADO_COM_ERROS);
      setMensagem(dados.valido_para_confirmacao ? "Validação concluída. Nenhum cadastro foi alterado." : "A planilha possui erros e não está pronta para preparação.");
    } catch (erro) {
      if (respostaAtual(req)) { const texto = mensagemSeguraImportacao(erro, "validar"); if (texto) setMensagem(texto); setEstado(ESTADOS_IMPORTACAO.ARQUIVO_SELECIONADO); }
    } finally { finalizarRequisicao(req); }
  };

  const preparar = async () => {
    if (!botoes.preparar) return;
    const req = iniciarRequisicao(); if (!req) return;
    setEstado(ESTADOS_IMPORTACAO.PREPARANDO); setMensagem("");
    try {
      const dados = await prepararImportacaoCadastral(arquivo, req.controlador.signal);
      if (!respostaAtual(req)) return;
      if (!dados?.sessao_id || !dados?.token_confirmacao || !dados?.expira_em) throw new Error("Resposta inválida");
      if (!hashesConferem(validacao, dados)) {
        setSessao(null); setEstado(ESTADOS_IMPORTACAO.FALHA_DEFINITIVA);
        setMensagem("O arquivo preparado não corresponde ao arquivo validado. Valide e prepare novamente."); return;
      }
      setSessao({ sessao_id: dados.sessao_id, token: dados.token_confirmacao, expira_em: dados.expira_em, resumo: dados.resumo, status: dados.status, arquivo_sha256: dados.arquivo_sha256 });
      setEstado(ESTADOS_IMPORTACAO.PREPARADO);
      setMensagem("Sessão temporária preparada. Os cadastros ainda não foram alterados.");
    } catch (erro) {
      if (respostaAtual(req)) { const texto = mensagemSeguraImportacao(erro, "preparar"); if (texto) setMensagem(texto); setEstado(ESTADOS_IMPORTACAO.VALIDADO_APTO); }
    } finally { finalizarRequisicao(req); }
  };

  const confirmar = async () => {
    if (!botoes.confirmar || !sessao?.token) return;
    if (sessaoExpirada(sessao.expira_em)) {
      setSessao((atual) => atual ? { ...atual, token: null, status: "EXPIRADA" } : null);
      setEstado(ESTADOS_IMPORTACAO.FALHA_DEFINITIVA); setConfirmarAberto(false);
      setMensagem("A sessão expirou. Valide e prepare novamente."); return;
    }
    const req = iniciarRequisicao(); if (!req) return;
    const id = sessao.sessao_id; const token = sessao.token;
    setEstado(ESTADOS_IMPORTACAO.CONFIRMANDO); setConfirmarAberto(false); setMensagem("");
    try {
      const dados = await confirmarImportacaoCadastral(id, token, req.controlador.signal);
      if (!respostaAtual(req)) return;
      if (!dados || dados.status !== "CONFIRMADA") throw new Error("Resposta inválida");
      setSessao((atual) => atual ? { ...atual, token: null, status: "CONFIRMADA" } : null);
      setResultado(dados); setEstado(ESTADOS_IMPORTACAO.CONFIRMADO);
      setMensagem("Importação confirmada e aplicada em uma única transação."); aoConfirmar?.();
    } catch (erro) {
      if (!respostaAtual(req)) return;
      const texto = mensagemSeguraImportacao(erro, "confirmação");
      if (!texto) return;
      const tratamento = erroConfirmacao(erro);
      if (tratamento.definitivo) {
        setSessao((atual) => atual ? { ...atual, token: null, status: "FALHOU" } : null);
        setEstado(ESTADOS_IMPORTACAO.FALHA_DEFINITIVA);
      } else {
        setEstado(ESTADOS_IMPORTACAO.ERRO_REPETIVEL);
      }
      setMensagem(texto);
    } finally { finalizarRequisicao(req); }
  };

  const novaImportacao = () => {
    invalidarPendencias();
    setArquivo(null); setValidacao(null); setSessao(null); setResultado(null); setConfirmarAberto(false);
    setMensagem(""); setEstado(ESTADOS_IMPORTACAO.SEM_ARQUIVO); setPaginaDiagnosticos(1); setPaginaOperacoes(1);
    setChaveInput((valor) => valor + 1);
  };

  const totalConfirmacao = (campo) => totais.reduce((soma, item) => soma + item[campo], 0);
  const ocupado = [ESTADOS_IMPORTACAO.VALIDANDO, ESTADOS_IMPORTACAO.PREPARANDO, ESTADOS_IMPORTACAO.CONFIRMANDO].includes(estado) || ocupadoRef.current;

  return <div className="max-w-7xl mx-auto space-y-5">
    <section className="bg-white p-6 rounded shadow space-y-4">
      <div><h2 className="text-xl font-semibold">Importação Cadastral</h2><p className="text-sm text-gray-600">Fluxo em duas etapas para matérias-primas, nutrientes, composição nutricional e preços.</p></div>
      <ol className="grid md:grid-cols-4 gap-2 text-sm" aria-label="Etapas da importação">
        {["1. Baixar modelo", "2. Validar sem gravar", "3. Preparar sessão", "4. Confirmar e aplicar"].map((texto) => <li key={texto} className="border rounded p-2 bg-gray-50">{texto}</li>)}
      </ol>
      <div className="flex flex-wrap gap-3 items-end">
        <button type="button" disabled={ocupado} onClick={baixar} className={`${botao} bg-gray-700 text-white`}>Baixar modelo XLSX</button>
        <label className="text-sm flex-1 min-w-64">Arquivo .xlsx
          <input key={chaveInput} type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={trocarArquivo} className="block w-full border p-2 rounded bg-white" />
        </label>
        <button type="button" disabled={!botoes.validar || ocupado} onClick={validar} className={`${botao} bg-blue-600 text-white`}>{ocupado ? "Aguarde…" : "Validar sem gravar"}</button>
      </div>
      {arquivo && <p className="text-sm"><strong>Arquivo:</strong> {arquivo.name} · {formatarTamanho(arquivo.size)}</p>}
      <p className="text-sm text-blue-800">Validar somente lê o arquivo e o banco. Preparar cria uma sessão temporária de 24 horas. Somente confirmar altera os cadastros.</p>
      {mensagem && <div role="status" className="border rounded p-3 bg-gray-50 text-sm">{mensagem}</div>}
    </section>

    {validacao && <section className="bg-white p-6 rounded shadow space-y-4">
      <div className="flex flex-wrap justify-between gap-2"><h3 className="text-lg font-semibold">Resultado da validação</h3><span className="font-medium">{validacao.valido_para_confirmacao ? "✓ Apta para preparação" : "✕ Contém erros"}</span></div>
      <p className="text-sm">SHA-256: <code title={validacao.sha256}>{hashResumido(validacao.sha256)}</code></p>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left border-b"><th className="p-2">Aba</th><th>Criar</th><th>Atualizar</th><th>Desativar</th><th>Sem alteração</th><th>Avisos</th><th>Erros</th></tr></thead><tbody>{totais.map((item) => <tr key={item.aba} className="border-b"><td className="p-2">{nomesAba[item.aba]}</td><td>{item.criar}</td><td>{item.atualizar}</td><td>{item.desativar}</td><td>{item.sem_alteracao}</td><td>{item.avisos}</td><td>{item.erros}</td></tr>)}</tbody></table></div>
      {validacao.resultado_truncado && <p className="border border-amber-300 bg-amber-50 p-3 text-sm">⚠ A API limitou a lista exibida. Os totais acima consideram todas as operações e todos os diagnósticos.</p>}
      <div><h4 className="font-medium mb-2">Diagnósticos ({validacao.diagnosticos_total})</h4><Paginacao dados={validacao.diagnosticos || []} paginaAtual={paginaDiagnosticos} setPaginaAtual={setPaginaDiagnosticos} vazio="Nenhum aviso ou erro." renderItem={(item, indice) => <div key={`${item.aba}-${item.linha}-${item.coluna}-${indice}`} className="border rounded p-3 text-sm"><strong>{item.severidade === "ERRO" ? "✕ Erro" : "⚠ Aviso"}</strong> · {item.aba || "GERAL"}{item.linha ? ` · linha ${item.linha}` : ""}{item.coluna ? ` · coluna ${item.coluna}` : ""}{item.codigo ? ` · ${item.codigo}` : ""}<p>{item.mensagem}</p></div>} /></div>
      <div><h4 className="font-medium mb-2">Operações previstas ({validacao.operacoes_total})</h4><Paginacao dados={validacao.operacoes || []} paginaAtual={paginaOperacoes} setPaginaAtual={setPaginaOperacoes} vazio="Nenhuma operação válida prevista." renderItem={(item, indice) => <div key={`${item.aba}-${item.linha}-${indice}`} className="border rounded p-3 text-sm"><strong>{item.resultado}</strong> · {item.aba} · linha {item.linha} · {item.codigo || "sem código"}{item.campos_alterados?.length ? ` · campos: ${item.campos_alterados.join(", ")}` : ""}</div>} /></div>
      <button type="button" disabled={!botoes.preparar || ocupado} onClick={preparar} className={`${botao} bg-indigo-600 text-white`}>{ocupado ? "Preparando…" : "Preparar importação"}</button>
    </section>}

    {sessao && <section className="bg-white p-6 rounded shadow space-y-3">
      <h3 className="text-lg font-semibold">Sessão de importação</h3><p className="text-sm"><strong>Estado do fluxo:</strong> {estado}</p><p className="text-sm"><strong>Status da sessão:</strong> {sessao.status}</p><p className="text-sm"><strong>Sessão:</strong> {sessao.sessao_id}</p><p className="text-sm"><strong>Expira em:</strong> {new Date(sessao.expira_em).toLocaleString("pt-BR")} (24 horas após a preparação)</p>
      {sessao.status === "PENDENTE" && <button type="button" disabled={!botoes.confirmar || ocupado} onClick={() => setConfirmarAberto(true)} className={`${botao} bg-red-700 text-white`}>{estado === ESTADOS_IMPORTACAO.ERRO_REPETIVEL ? "Repetir confirmação com segurança" : "Revisar confirmação definitiva"}</button>}
    </section>}

    {confirmarAberto && sessao && <section role="dialog" aria-modal="true" aria-labelledby="titulo-confirmacao" className="bg-white border-2 border-red-300 p-6 rounded shadow space-y-3">
      <h3 id="titulo-confirmacao" className="text-lg font-semibold">Confirmar aplicação definitiva</h3><p><strong>Arquivo:</strong> {arquivo?.name}</p><p><strong>Sessão:</strong> {sessao.sessao_id}</p>
      <ul className="list-disc pl-6 text-sm"><li>Criar: {totalConfirmacao("criar")}</li><li>Atualizar: {totalConfirmacao("atualizar")}</li><li>Matérias-primas a desativar: {validacao?.resumo?.MATERIAS_PRIMAS?.desativar || 0}</li><li>Sem alteração: {totalConfirmacao("sem_alteracao")}</li></ul>
      <p className="font-medium">As alterações serão aplicadas em uma única transação PostgreSQL.</p><div className="flex gap-3"><button disabled={ocupado} onClick={() => setConfirmarAberto(false)} className={`${botao} bg-gray-200`}>Cancelar</button><button disabled={!botoes.confirmar || ocupado} onClick={confirmar} className={`${botao} bg-red-700 text-white`}>Confirmar e aplicar</button></div>
    </section>}

    {resultado && <section className="bg-white p-6 rounded shadow space-y-3"><h3 className="text-lg font-semibold">Resultado final</h3><p><strong>Status:</strong> ✓ {resultado.status}</p><div className="grid sm:grid-cols-4 gap-2 text-sm">{Object.entries(resultado.totais || {}).map(([chave, valor]) => <div key={chave} className="border rounded p-2"><strong>{chave.replace("_", " ")}:</strong> {valor}</div>)}</div><p className="text-sm"><strong>Códigos afetados:</strong> {(resultado.codigos_afetados || []).join(", ") || "Nenhum"}</p>{resultado.resultado_truncado && <p className="text-sm bg-amber-50 border border-amber-300 p-2">⚠ A lista de códigos afetados foi truncada; os totais permanecem completos.</p>}<button onClick={novaImportacao} className={`${botao} bg-blue-600 text-white`}>Iniciar nova importação</button></section>}
  </div>;
}
