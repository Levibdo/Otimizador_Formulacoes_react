export const MAX_ARQUIVO_BYTES = 5 * 1024 * 1024;
export const ESTADOS_IMPORTACAO = Object.freeze({
  SEM_ARQUIVO: "SEM_ARQUIVO", ARQUIVO_SELECIONADO: "ARQUIVO_SELECIONADO",
  VALIDANDO: "VALIDANDO", VALIDADO_COM_ERROS: "VALIDADO_COM_ERROS",
  VALIDADO_APTO: "VALIDADO_APTO", PREPARANDO: "PREPARANDO",
  PREPARADO: "PREPARADO", CONFIRMANDO: "CONFIRMANDO",
  CONFIRMADO: "CONFIRMADO", FALHA_DEFINITIVA: "FALHA_DEFINITIVA",
  ERRO_REPETIVEL: "ERRO_REPETIVEL",
});

export const ABAS_V10 = Object.freeze([
  "MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP", "GERAL",
]);
export const ABAS_V11 = Object.freeze([
  "MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP",
  "CATEGORIAS_PRODUTO", "COMPONENTES_REGULATORIOS",
  "COMPOSICAO_COMPONENTES_MP", "REGRAS_REGULATORIAS_MP",
  "REGRAS_REGULATORIAS_COMPONENTE", "GERAL",
]);
export const NOMES_ABAS = Object.freeze({
  MATERIAS_PRIMAS: "Matérias-primas", NUTRIENTES: "Nutrientes",
  COMPOSICAO_NUTRICIONAL: "Composição nutricional",
  PRECOS_MP: "Preços de matérias-primas", CATEGORIAS_PRODUTO: "Categorias de produto",
  COMPONENTES_REGULATORIOS: "Componentes regulatórios",
  COMPOSICAO_COMPONENTES_MP: "Composição de componentes por matéria-prima",
  REGRAS_REGULATORIAS_MP: "Regras regulatórias por matéria-prima",
  REGRAS_REGULATORIAS_COMPONENTE: "Regras regulatórias por componente",
  GERAL: "Geral",
});
const CAMPOS_RESUMO = ["criar", "atualizar", "desativar", "sem_alteracao", "avisos", "erros"];

export function abasParaVersao(versao) {
  if (versao === "1.0") return [...ABAS_V10];
  if (versao === "1.1") return [...ABAS_V11];
  return [];
}
function numeroSeguro(valor) {
  const numero = Number(valor);
  return Number.isFinite(numero) && numero >= 0 ? numero : 0;
}
export function resumoDaValidacao(validacao) {
  return abasParaVersao(validacao?.versao).map((aba) => ({
    aba,
    ...Object.fromEntries(CAMPOS_RESUMO.map((campo) => [campo, numeroSeguro(validacao?.resumo?.[aba]?.[campo])])),
  }));
}
export function versaoSuportada(versao) { return abasParaVersao(versao).length > 0; }
export function validacaoEstruturalValida(dados) {
  const abas = abasParaVersao(dados?.versao);
  return Boolean(dados && abas.length
    && typeof dados.valido_para_confirmacao === "boolean"
    && typeof dados.sha256 === "string" && dados.sha256.length > 0
    && dados.resumo && typeof dados.resumo === "object"
    && abas.every((aba) => dados.resumo[aba] && typeof dados.resumo[aba] === "object")
    && Array.isArray(dados.diagnosticos) && Array.isArray(dados.operacoes));
}
export function preparacaoEstruturalValida(preparacao) {
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  const expiracao = new Date(preparacao?.expira_em);
  return Boolean(preparacao && preparacao.status === "PENDENTE"
    && uuid.test(preparacao.sessao_id || "")
    && typeof preparacao.token_confirmacao === "string" && preparacao.token_confirmacao.length > 0
    && typeof preparacao.arquivo_sha256 === "string" && preparacao.arquivo_sha256.length > 0
    && versaoSuportada(preparacao.versao)
    && Number.isFinite(expiracao.getTime()));
}
export function preparacaoConfere(validacao, preparacao) {
  return Boolean(preparacaoEstruturalValida(preparacao)
    && validacao?.sha256 === preparacao.arquivo_sha256
    && versaoSuportada(validacao?.versao)
    && validacao.versao === preparacao.versao);
}
export const hashesConferem = preparacaoConfere;
export function totaisConfirmacao(linhas) {
  const semGeral = (Array.isArray(linhas) ? linhas : []).filter((item) => item?.aba !== "GERAL");
  return Object.fromEntries(["criar", "atualizar", "desativar", "sem_alteracao"]
    .map((campo) => [campo, semGeral.reduce((soma, item) => soma + numeroSeguro(item?.[campo]), 0)]));
}
export function nomeAba(aba) { return NOMES_ABAS[aba] || "Aba não reconhecida"; }
export function operacaoParaExibicao(item, versao) {
  if (!item || !abasParaVersao(versao).includes(item.aba) || item.aba === "GERAL") return null;
  return {
    resultado: String(item.resultado || "NÃO INFORMADO"), aba: nomeAba(item.aba),
    linha: Number.isInteger(item.linha) && item.linha > 0 ? item.linha : null,
    codigo: typeof item.codigo === "string" ? item.codigo : "sem identidade",
    campos: Array.isArray(item.campos_alterados)
      ? item.campos_alterados.filter((campo) => typeof campo === "string").slice(0, 50) : [],
  };
}
export function nomeArquivoTemplate(contentDisposition) {
  if (typeof contentDisposition === "string") {
    const utf8 = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
    const simples = contentDisposition.match(/filename="?([^";]+)"?/i);
    let candidato = simples?.[1];
    if (utf8?.[1]) {
      try { candidato = decodeURIComponent(utf8[1]); } catch { candidato = null; }
    }
    if (candidato && /^[A-Za-z0-9_.-]+\.xlsx$/i.test(candidato)
        && !candidato.includes("..")) return candidato;
  }
  return "template-cadastral-v1.1.xlsx";
}
export function resultadoConfirmacaoValido(resultado) {
  const campos = ["criar", "atualizar", "desativar", "sem_alteracao"];
  return Boolean(resultado?.status === "CONFIRMADA"
    && resultado.totais && campos.every((campo) => {
      const valor = resultado.totais[campo];
      return typeof valor === "number" && Number.isFinite(valor) && valor >= 0;
    })
    && Array.isArray(resultado.codigos_afetados)
    && resultado.codigos_afetados.length <= 500
    && resultado.codigos_afetados.every((item) => typeof item === "string")
    && typeof resultado.resultado_truncado === "boolean");
}

export function validarArquivoSelecionado(arquivo) {
  if (!arquivo) return "Selecione um arquivo .xlsx.";
  if (!arquivo.name?.toLowerCase().endsWith(".xlsx")) return "Selecione um arquivo no formato .xlsx.";
  if (arquivo.size === 0) return "O arquivo está vazio.";
  if (arquivo.size > MAX_ARQUIVO_BYTES) return "O arquivo excede o limite de 5 MiB.";
  return null;
}
export function pagina(itens = [], numero = 1, tamanho = 25) {
  const lista = Array.isArray(itens) ? itens : [];
  const total = lista.length; const paginas = Math.max(1, Math.ceil(total / tamanho));
  const atual = Math.min(Math.max(1, numero), paginas);
  return { itens: lista.slice((atual - 1) * tamanho, atual * tamanho), atual, paginas, total };
}
export function hashResumido(hash = "") { return hash.length > 20 ? `${hash.slice(0, 12)}…${hash.slice(-8)}` : hash; }
export function respostaPertenceAoFluxo(geracaoResposta, geracaoAtual, abortado = false) { return !abortado && geracaoResposta === geracaoAtual; }
export function botoesPorEstado(estado) {
  return { validar: estado === ESTADOS_IMPORTACAO.ARQUIVO_SELECIONADO,
    preparar: estado === ESTADOS_IMPORTACAO.VALIDADO_APTO,
    confirmar: [ESTADOS_IMPORTACAO.PREPARADO, ESTADOS_IMPORTACAO.ERRO_REPETIVEL].includes(estado) };
}
export function erroConfirmacao(erro) {
  const status = erro?.response?.status;
  const codigo = erro?.response?.data?.detail?.codigo;
  if (status === 404) return { definitivo: true, codigo: "CREDENCIAL_INVALIDA", mensagem: "Sessão ou credencial de confirmação inválida. Prepare uma nova importação." };
  if (status === 409 && codigo === "REVALIDACAO_DIVERGENTE") return { definitivo: true, codigo, mensagem: "Os cadastros mudaram desde a validação. Valide e prepare uma nova importação." };
  if (status === 409 && codigo === "SESSAO_EXPIRADA") return { definitivo: true, codigo, mensagem: "A sessão expirou. Prepare uma nova importação." };
  if (status === 409 && codigo === "SESSAO_FALHOU") return { definitivo: true, codigo, mensagem: "A sessão falhou e não pode ser repetida. Prepare uma nova importação." };
  if (status === 409) return { definitivo: true, codigo: "SESSAO_INDISPONIVEL", mensagem: "A sessão expirou ou não pode mais ser confirmada. Prepare uma nova importação." };
  if (status === 500 || !erro?.response) return { definitivo: false, codigo: "ERRO_REPETIVEL", mensagem: "Não foi possível confirmar a resposta do servidor. Repita a confirmação com segurança." };
  return { definitivo: false, codigo: "ERRO_REPETIVEL", mensagem: "A resposta da confirmação foi inesperada. Repita a confirmação com segurança." };
}
export function mensagemSeguraImportacao(erro, etapa = "operação") {
  if (["ERR_CANCELED", "CanceledError", "AbortError"].includes(erro?.code) || ["CanceledError", "AbortError"].includes(erro?.name)) return null;
  const status = erro?.response?.status;
  if (etapa === "confirmação") return erroConfirmacao(erro).mensagem;
  if (status === 422 && etapa === "validar") return "A planilha não pôde ser validada. Confira os diagnósticos apresentados.";
  if (status === 422 && etapa === "preparar") return "A planilha mudou ou possui erros. Valide o arquivo novamente.";
  if (!erro?.response) return "Não foi possível acessar a API. Verifique a conexão e tente novamente.";
  return `Não foi possível concluir a etapa de ${etapa}.`;
}
export function sessaoExpirada(expiraEm, agora = new Date()) {
  if (!expiraEm) return false; const limite = new Date(expiraEm);
  return Number.isFinite(limite.getTime()) && limite.getTime() <= agora.getTime();
}
export function estadoAoTrocarArquivo(arquivo) { return { arquivo, validacao: null, sessao: null, resultado: null, confirmarAberto: false }; }
