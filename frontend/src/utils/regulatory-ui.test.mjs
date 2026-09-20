import test from "node:test";
import assert from "node:assert/strict";
import { execucaoAptaParaVersao, mensagemStatusRegulatorio, validarComposicao, validarRegra } from "./regulatory-ui.mjs";

test("mapeia os seis estados regulatórios sem alegação normativa", () => {
  for (const status of ["SEM_AVALIACAO_REGULATORIA", "ATENDE", "ATENDE_COM_ALERTAS", "INCONCLUSIVA", "INVIAVEL", "ERRO_TECNICO"]) {
    assert.notEqual(mensagemStatusRegulatorio(status), "Estado regulatório não informado.");
  }
  assert.match(mensagemStatusRegulatorio("ATENDE_COM_ALERTAS"), /sem classificação/);
});

test("só permite versionar execução ótima e apta", () => {
  assert.equal(execucaoAptaParaVersao({ execucao_id: 1, status: "ATENDE", status_solver: "Optimal" }), true);
  for (const status of ["INCONCLUSIVA", "INVIAVEL", "ERRO_TECNICO"]) {
    assert.equal(execucaoAptaParaVersao({ execucao_id: 1, status, status_solver: "Optimal" }), false);
  }
});

test("valida zero confirmado, desconhecido e informado", () => {
  assert.equal(validarComposicao({ situacao: "AUSENTE_CONFIRMADO", concentracao: "0" }), null);
  assert.match(validarComposicao({ situacao: "AUSENTE_CONFIRMADO", concentracao: "" }), /zero/);
  assert.equal(validarComposicao({ situacao: "DESCONHECIDO", concentracao: "" }), null);
  assert.match(validarComposicao({ situacao: "INFORMADO", concentracao: "" }), /concentração/);
});

test("valida regras obrigatória, limitada e alvos", () => {
  const base = { tipo_alvo: "MATERIA_PRIMA", materia_prima_id: 1, tratamento: "PERMITIDA", minimo: "", maximo: "", justificativa: "Cadastro manual" };
  assert.equal(validarRegra(base), null);
  assert.match(validarRegra({ ...base, tratamento: "OBRIGATORIA" }), /mínimo/);
  assert.match(validarRegra({ ...base, tratamento: "LIMITADA" }), /mínimo ou máximo/);
});
