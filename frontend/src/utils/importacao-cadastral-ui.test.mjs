import test from "node:test";
import assert from "node:assert/strict";
import {
  ESTADOS_IMPORTACAO, MAX_ARQUIVO_BYTES, botoesPorEstado, erroConfirmacao,
  estadoAoTrocarArquivo, hashesConferem, mensagemSeguraImportacao, pagina,
  respostaPertenceAoFluxo, resumoDaValidacao, sessaoExpirada, validarArquivoSelecionado,
} from "./importacao-cadastral-ui.mjs";

test("estado inicial e habilitação estrita dos botões", () => {
  assert.deepEqual(botoesPorEstado(ESTADOS_IMPORTACAO.SEM_ARQUIVO), { validar: false, preparar: false, confirmar: false });
  assert.equal(botoesPorEstado(ESTADOS_IMPORTACAO.ARQUIVO_SELECIONADO).validar, true);
  assert.equal(botoesPorEstado(ESTADOS_IMPORTACAO.VALIDADO_APTO).preparar, true);
  assert.equal(botoesPorEstado(ESTADOS_IMPORTACAO.PREPARADO).confirmar, true);
  assert.equal(botoesPorEstado(ESTADOS_IMPORTACAO.ERRO_REPETIVEL).confirmar, true);
  assert.deepEqual(botoesPorEstado(ESTADOS_IMPORTACAO.CONFIRMANDO), { validar: false, preparar: false, confirmar: false });
});

test("rejeita extensão inválida, vazio e tamanho acima de 5 MiB", () => {
  assert.match(validarArquivoSelecionado({ name: "dados.csv", size: 10 }), /xlsx/);
  assert.match(validarArquivoSelecionado({ name: "dados.xlsx", size: 0 }), /vazio/);
  assert.equal(validarArquivoSelecionado({ name: "dados.xlsx", size: MAX_ARQUIVO_BYTES }), null);
  assert.match(validarArquivoSelecionado({ name: "dados.xlsx", size: MAX_ARQUIVO_BYTES + 1 }), /5 MiB/);
});

test("resume todas as abas e anuncia truncamento pelo contrato", () => {
  const linhas = resumoDaValidacao({ resumo: { MATERIAS_PRIMAS: { criar: 2, avisos: 1 }, GERAL: { erros: 1 } }, resultado_truncado: true });
  assert.equal(linhas.length, 5); assert.equal(linhas[0].criar, 2); assert.equal(linhas.at(-1).erros, 1);
});

test("pagina listas sem renderizar tudo", () => {
  const itens = Array.from({ length: 61 }, (_, i) => i + 1);
  assert.deepEqual(pagina(itens, 2, 25), { itens: itens.slice(25, 50), atual: 2, paginas: 3, total: 61 });
  assert.equal(pagina(itens, 99, 25).atual, 3);
});

test("ignora resposta assíncrona antiga ou abortada", () => {
  assert.equal(respostaPertenceAoFluxo(4, 5), false);
  assert.equal(respostaPertenceAoFluxo(5, 5, true), false);
  assert.equal(respostaPertenceAoFluxo(5, 5), true);
});

test("troca de arquivo limpa validação, sessão, token e resultado", () => {
  const novo = { name: "novo.xlsx", size: 10 };
  assert.deepEqual(estadoAoTrocarArquivo(novo), { arquivo: novo, validacao: null, sessao: null, resultado: null, confirmarAberto: false });
});

test("divergência de SHA bloqueia confirmação", () => {
  assert.equal(hashesConferem({ sha256: "abc" }, { arquivo_sha256: "abc" }), true);
  assert.equal(hashesConferem({ sha256: "abc" }, { arquivo_sha256: "xyz" }), false);
});

test("erro definitivo descarta token e erro ambíguo permite repetição", () => {
  assert.equal(erroConfirmacao({ response: { status: 404 } }).definitivo, true);
  assert.equal(erroConfirmacao({ response: { status: 409 } }).definitivo, true);
  assert.equal(erroConfirmacao({ response: { status: 500 } }).definitivo, false);
  assert.equal(erroConfirmacao({ code: "ECONNABORTED" }).definitivo, false);
});

test("formata erros sem resposta bruta e ignora aborto intencional", () => {
  assert.equal(mensagemSeguraImportacao({ code: "ERR_CANCELED" }, "validar"), null);
  const mensagem = mensagemSeguraImportacao({ response: { status: 500, data: { detail: "SQL stack trace" } } }, "validar");
  assert.doesNotMatch(mensagem, /SQL|stack/i);
});

test("reconhece sessão expirada e confirmação concluída", () => {
  assert.equal(sessaoExpirada("2026-01-01T00:00:00Z", new Date("2026-01-02T00:00:00Z")), true);
  assert.deepEqual(botoesPorEstado(ESTADOS_IMPORTACAO.CONFIRMADO), { validar: false, preparar: false, confirmar: false });
});
