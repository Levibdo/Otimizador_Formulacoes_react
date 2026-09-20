export const STATUS_REGULATORIO = {
  SEM_AVALIACAO_REGULATORIA: "O projeto não possui avaliação regulatória.",
  ATENDE: "Atende às regras cadastradas para esta categoria.",
  ATENDE_COM_ALERTAS: "Atende às regras avaliadas, mas existem matérias-primas sem classificação.",
  INCONCLUSIVA: "Não foi possível concluir a avaliação com os dados cadastrados.",
  INVIAVEL: "Não foi encontrada formulação que satisfaça todas as restrições.",
  ERRO_TECNICO: "Não foi possível concluir a otimização.",
};

export function mensagemStatusRegulatorio(status) {
  return STATUS_REGULATORIO[status] || "Estado regulatório não informado.";
}

export function execucaoAptaParaVersao(resultado) {
  return Boolean(
    resultado?.execucao_id &&
    ["SEM_AVALIACAO_REGULATORIA", "ATENDE", "ATENDE_COM_ALERTAS"].includes(resultado.status) &&
    resultado.status_solver === "Optimal"
  );
}

export function validarComposicao({ situacao, concentracao }) {
  if (situacao === "INFORMADO" && (concentracao === "" || concentracao == null)) {
    return "Informe a concentração do componente.";
  }
  if (situacao === "AUSENTE_CONFIRMADO" && (concentracao === "" || concentracao == null || Number(concentracao) !== 0)) {
    return "Ausência confirmada exige concentração igual a zero.";
  }
  if (situacao === "DESCONHECIDO" && concentracao !== "" && concentracao != null) {
    return "Concentração desconhecida deve permanecer vazia.";
  }
  const numero = concentracao === "" || concentracao == null ? null : Number(concentracao);
  if (numero != null && (!Number.isFinite(numero) || numero < 0 || numero > 100)) {
    return "A concentração deve estar entre 0 e 100%.";
  }
  return null;
}

export function validarRegra({ tipo_alvo, materia_prima_id, componente_id, tratamento, minimo, maximo, justificativa }) {
  if (!justificativa?.trim()) return "Informe a justificativa da regra.";
  if (tipo_alvo === "MATERIA_PRIMA" && !materia_prima_id) return "Selecione a matéria-prima alvo.";
  if (tipo_alvo === "COMPONENTE" && !componente_id) return "Selecione o componente alvo.";
  const min = minimo === "" || minimo == null ? null : Number(minimo);
  const max = maximo === "" || maximo == null ? null : Number(maximo);
  if (min != null && max != null && min > max) return "O mínimo não pode superar o máximo.";
  if (tratamento === "OBRIGATORIA" && !(min > 0)) return "Regra obrigatória exige mínimo maior que zero.";
  if (tratamento === "LIMITADA" && min == null && max == null) return "Regra limitada exige mínimo ou máximo.";
  if (tratamento === "PROIBIDA" && ((min != null && min !== 0) || (max != null && max !== 0))) return "Regra proibida exige máximo zero.";
  return null;
}

export function mensagemErroApi(erro, fallback = "Não foi possível concluir a operação.") {
  const detalhe = erro?.response?.data?.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe)) return detalhe.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
  if (!erro?.response) return "API indisponível. Verifique a conexão e tente novamente.";
  return fallback;
}
