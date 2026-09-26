export const MAX_ARQUIVO_BYTES = 5 * 1024 * 1024;
export const ESTADOS_IMPORTACAO = Object.freeze({
  SEM_ARQUIVO: "SEM_ARQUIVO",
  ARQUIVO_SELECIONADO: "ARQUIVO_SELECIONADO",
  VALIDANDO: "VALIDANDO",
  VALIDADO_COM_ERROS: "VALIDADO_COM_ERROS",
  VALIDADO_APTO: "VALIDADO_APTO",
  PREPARANDO: "PREPARANDO",
  PREPARADO: "PREPARADO",
  CONFIRMANDO: "CONFIRMANDO",
  CONFIRMADO: "CONFIRMADO",
  FALHA_DEFINITIVA: "FALHA_DEFINITIVA",
  ERRO_REPETIVEL: "ERRO_REPETIVEL",
});

export const ABAS_CADASTRAIS = ["MATERIAS_PRIMAS", "NUTRIENTES", "COMPOSICAO_NUTRICIONAL", "PRECOS_MP", "GERAL"];

export function validarArquivoSelecionado(arquivo) {
  if (!arquivo) return "Selecione um arquivo .xlsx.";
  if (!arquivo.name?.toLowerCase().endsWith(".xlsx")) return "Selecione um arquivo no formato .xlsx.";
  if (arquivo.size === 0) return "O arquivo está vazio.";
  if (arquivo.size > MAX_ARQUIVO_BYTES) return "O arquivo excede o limite de 5 MiB.";
  return null;
}

export function resumoDaValidacao(validacao) {
  return ABAS_CADASTRAIS.map((aba) => ({
    aba,
    criar: Number(validacao?.resumo?.[aba]?.criar || 0),
    atualizar: Number(validacao?.resumo?.[aba]?.atualizar || 0),
    desativar: Number(validacao?.resumo?.[aba]?.desativar || 0),
    sem_alteracao: Number(validacao?.resumo?.[aba]?.sem_alteracao || 0),
    avisos: Number(validacao?.resumo?.[aba]?.avisos || 0),
    erros: Number(validacao?.resumo?.[aba]?.erros || 0),
  }));
}

export function pagina(itens = [], numero = 1, tamanho = 25) {
  const total = itens.length;
  const paginas = Math.max(1, Math.ceil(total / tamanho));
  const atual = Math.min(Math.max(1, numero), paginas);
  return { itens: itens.slice((atual - 1) * tamanho, atual * tamanho), atual, paginas, total };
}

export function hashResumido(hash = "") {
  return hash.length > 20 ? `${hash.slice(0, 12)}…${hash.slice(-8)}` : hash;
}

export function hashesConferem(validacao, preparacao) {
  return Boolean(validacao?.sha256 && preparacao?.arquivo_sha256 && validacao.sha256 === preparacao.arquivo_sha256);
}

export function respostaPertenceAoFluxo(geracaoResposta, geracaoAtual, abortado = false) {
  return !abortado && geracaoResposta === geracaoAtual;
}

export function botoesPorEstado(estado) {
  return {
    validar: estado === ESTADOS_IMPORTACAO.ARQUIVO_SELECIONADO,
    preparar: estado === ESTADOS_IMPORTACAO.VALIDADO_APTO,
    confirmar: [ESTADOS_IMPORTACAO.PREPARADO, ESTADOS_IMPORTACAO.ERRO_REPETIVEL].includes(estado),
  };
}

export function erroConfirmacao(erro) {
  const status = erro?.response?.status;
  if (status === 404) return { definitivo: true, mensagem: "Sessão ou credencial de confirmação inválida. Prepare uma nova importação." };
  if (status === 409) return { definitivo: true, mensagem: "A sessão não pode ser confirmada. O banco ou o estado da sessão mudou; valide e prepare novamente." };
  if (status === 500 || !erro?.response) return { definitivo: false, mensagem: "Não foi possível confirmar a resposta do servidor. Repita a confirmação com segurança." };
  return { definitivo: false, mensagem: "A resposta da confirmação foi inesperada. Repita a confirmação com segurança." };
}

export function mensagemSeguraImportacao(erro, etapa = "operação") {
  if (erro?.code === "ERR_CANCELED" || erro?.name === "CanceledError" || erro?.name === "AbortError") return null;
  const status = erro?.response?.status;
  if (etapa === "confirmação") return erroConfirmacao(erro).mensagem;
  if (status === 422 && etapa === "validar") return "A planilha não pôde ser validada. Confira os diagnósticos apresentados.";
  if (status === 422 && etapa === "preparar") return "A planilha mudou ou possui erros. Valide o arquivo novamente.";
  if (!erro?.response) return "Não foi possível acessar a API. Verifique a conexão e tente novamente.";
  return `Não foi possível concluir a etapa de ${etapa}.`;
}

export function sessaoExpirada(expiraEm, agora = new Date()) {
  if (!expiraEm) return false;
  const limite = new Date(expiraEm);
  return Number.isFinite(limite.getTime()) && limite.getTime() <= agora.getTime();
}

export function estadoAoTrocarArquivo(arquivo) {
  return { arquivo, validacao: null, sessao: null, resultado: null, confirmarAberto: false };
}
