import test from "node:test";
import assert from "node:assert/strict";
import {
  ABAS_V10, ABAS_V11, ESTADOS_IMPORTACAO, MAX_ARQUIVO_BYTES, abasParaVersao,
  botoesPorEstado, erroConfirmacao, estadoAoTrocarArquivo, mensagemSeguraImportacao,
  nomeArquivoTemplate, operacaoParaExibicao, pagina, preparacaoConfere,
  preparacaoEstruturalValida, respostaPertenceAoFluxo, resultadoConfirmacaoValido,
  resumoDaValidacao, sessaoExpirada, totaisConfirmacao, validacaoEstruturalValida,
  validarArquivoSelecionado,
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

test("abas e resumos v1.0 e v1.1 seguem o contrato", () => {
  assert.deepEqual(abasParaVersao("1.0"), [...ABAS_V10]);
  assert.deepEqual(abasParaVersao("1.1"), [...ABAS_V11]);
  assert.deepEqual(abasParaVersao("desconhecida"), []);
  assert.equal(resumoDaValidacao({ versao: "1.0", resumo: {} }).length, 5);
  const v11 = resumoDaValidacao({ versao: "1.1", resumo: { MATERIAS_PRIMAS: { criar: 2 }, SEGREDOS: { criar: 99 } } });
  assert.equal(v11.length, 10); assert.equal(v11[0].criar, 2);
  assert.equal(v11.some((item) => item.aba === "SEGREDOS"), false);
  assert.equal(resumoDaValidacao({ versao: "1.1", resumo: { MATERIAS_PRIMAS: { criar: "NaN" } } })[0].criar, 0);
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

test("preparação exige SHA, versão, sessão e estado", () => {
  const validacao = { sha256: "abc", versao: "1.1" };
  const preparada = { arquivo_sha256: "abc", versao: "1.1", sessao_id: "123e4567-e89b-42d3-a456-426614174000", status: "PENDENTE", token_confirmacao: "segredo-em-memoria", expira_em: "2026-09-28T00:00:00Z" };
  assert.equal(preparacaoConfere(validacao, preparada), true);
  assert.equal(preparacaoConfere(validacao, { ...preparada, arquivo_sha256: "xyz" }), false);
  assert.equal(preparacaoConfere(validacao, { ...preparada, versao: "1.0" }), false);
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


test("estrutura, totais e operação regulatória são seguros", () => {
  assert.equal(validacaoEstruturalValida({ versao: "1.1", valido_para_confirmacao: true, sha256: "x", resumo: Object.fromEntries(ABAS_V11.map((aba) => [aba, {}])), diagnosticos: [], operacoes: [] }), true);
  assert.equal(validacaoEstruturalValida({ versao: "2.0", valido_para_confirmacao: true }), false);
  const linhas = resumoDaValidacao({ versao: "1.1", resumo: { MATERIAS_PRIMAS: { criar: 2 }, GERAL: { criar: 2 } } });
  assert.deepEqual(totaisConfirmacao(linhas), { criar: 2, atualizar: 0, desativar: 0, sem_alteracao: 0 });
  assert.deepEqual(operacaoParaExibicao({ aba: "REGRAS_REGULATORIAS_MP", linha: 2, codigo: "CAT/MP//", resultado: "CRIAR", campos_alterados: ["maximo"] }, "1.1"), { resultado: "CRIAR", aba: "Regras regulatórias por matéria-prima", linha: 2, codigo: "CAT/MP//", campos: ["maximo"] });
  assert.equal(operacaoParaExibicao({ aba: "ARBITRARIA" }, "1.1"), null);
});

test("download usa Content-Disposition seguro e fallback v1.1", () => {
  assert.equal(nomeArquivoTemplate('attachment; filename="modelo-v1.1.xlsx"'), "modelo-v1.1.xlsx");
  assert.equal(nomeArquivoTemplate('attachment; filename="ataque.html"'), "template-cadastral-v1.1.xlsx");
});

test("paginação final suporta 500 identidades e truncamento textual é contratual", () => {
  const itens = Array.from({ length: 500 }, (_, i) => `ABA:ID_${i}`);
  assert.equal(pagina(itens, 25, 20).itens.length, 20);
  assert.equal(pagina(itens, 99, 20).atual, 25);
});

test("revalidação divergente usa somente código estruturado", () => {
  const divergente = erroConfirmacao({ response: { status: 409, data: { detail: { codigo: "REVALIDACAO_DIVERGENTE", mensagem: "livre" } } } });
  assert.equal(divergente.definitivo, true); assert.equal(divergente.codigo, "REVALIDACAO_DIVERGENTE");
  assert.match(divergente.mensagem, /mudaram/);
  const livre = erroConfirmacao({ response: { status: 409, data: { detail: "REVALIDACAO_DIVERGENTE" } } });
  assert.equal(livre.codigo, "SESSAO_INDISPONIVEL");
});


test("versões ausentes, numéricas, desconhecidas e objetos malformados são rejeitados", () => {
  for (const versao of [undefined, 1.1, "9.9", {}, null]) {
    assert.equal(validacaoEstruturalValida({ versao, valido_para_confirmacao: true, sha256: "x", resumo: {}, diagnosticos: [], operacoes: [] }), false);
  }
  const incompleto = Object.fromEntries(["MATERIAS_PRIMAS", "GERAL"].map((aba) => [aba, {}]));
  assert.equal(validacaoEstruturalValida({ versao: "1.1", valido_para_confirmacao: true, sha256: "x", resumo: incompleto, diagnosticos: [], operacoes: [] }), false);
});

test("preparação rejeita UUID, status, token e expiração inválidos", () => {
  const base = { arquivo_sha256: "abc", versao: "1.1", sessao_id: "123e4567-e89b-42d3-a456-426614174000", status: "PENDENTE", token_confirmacao: "token", expira_em: "2026-09-28T00:00:00Z" };
  assert.equal(preparacaoEstruturalValida(base), true);
  for (const alteracao of [{ sessao_id: "" }, { sessao_id: "não-uuid" }, { status: "CONFIRMADA" }, { token_confirmacao: "" }, { expira_em: "inválida" }]) {
    assert.equal(preparacaoEstruturalValida({ ...base, ...alteracao }), false);
  }
});

test("resultado final malformado nunca é aceito como sucesso", () => {
  const base = { status: "CONFIRMADA", totais: { criar: 1, atualizar: 0, desativar: 0, sem_alteracao: 0 }, codigos_afetados: ["CATEGORIAS_PRODUTO:CAT_01"], resultado_truncado: false };
  assert.equal(resultadoConfirmacaoValido(base), true);
  assert.equal(resultadoConfirmacaoValido({ ...base, status: "PENDENTE" }), false);
  assert.equal(resultadoConfirmacaoValido({ ...base, totais: { ...base.totais, criar: "1" } }), false);
  assert.equal(resultadoConfirmacaoValido({ ...base, totais: { ...base.totais, criar: -1 } }), false);
  assert.equal(resultadoConfirmacaoValido({ ...base, codigos_afetados: [123] }), false);
  assert.equal(resultadoConfirmacaoValido({ ...base, resultado_truncado: "false" }), false);
});

test("nome do download rejeita traversal, barras, controles, vazio e URI inválida", () => {
  for (const cabecalho of [undefined, 'attachment; filename="../ataque.xlsx"', 'attachment; filename="pasta\\ataque.xlsx"', 'attachment; filename=""', "attachment; filename*=UTF-8''%ZZ.xlsx", 'attachment; filename="ataque.xlsx\n.html"']) {
    assert.equal(nomeArquivoTemplate(cabecalho), "template-cadastral-v1.1.xlsx");
  }
});

test("EXPIRADA e FALHOU estruturados são definitivos e distintos", () => {
  const expirada = erroConfirmacao({ response: { status: 409, data: { detail: { codigo: "SESSAO_EXPIRADA" } } } });
  const falhou = erroConfirmacao({ response: { status: 409, data: { detail: { codigo: "SESSAO_FALHOU" } } } });
  assert.equal(expirada.codigo, "SESSAO_EXPIRADA"); assert.match(expirada.mensagem, /expirou/);
  assert.equal(falhou.codigo, "SESSAO_FALHOU"); assert.match(falhou.mensagem, /falhou/);
});
