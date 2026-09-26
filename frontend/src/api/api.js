import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function getMetaData() {
  const res = await axios.get(`${API_BASE}/api/v1/materias-primas/matriz`);
  return res.data;
}

export async function listarMateriasPrimas() {
  const res = await axios.get(`${API_BASE}/api/v1/materias-primas`);
  return res.data;
}

export async function criarMateriaPrima(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/materias-primas`, payload);
  return res.data;
}

export async function desativarMateriaPrima(id) {
  await axios.delete(`${API_BASE}/api/v1/materias-primas/${id}`);
}

export async function atualizarMateriaPrima(id, payload) {
  const res = await axios.patch(
    `${API_BASE}/api/v1/materias-primas/${id}`,
    payload
  );
  return res.data;
}

export async function adicionarPrecoMateriaPrima(id, payload) {
  const res = await axios.post(
    `${API_BASE}/api/v1/materias-primas/${id}/precos`,
    payload
  );
  return res.data;
}

export async function importarMateriasPrimas(
  arquivo,
  vigenciaInicio,
  unidadePadrao = 'não informada'
) {
  const formData = new FormData();
  formData.append('arquivo', arquivo);
  formData.append('vigencia_inicio', vigenciaInicio);
  formData.append('unidade_padrao', unidadePadrao);
  const res = await axios.post(
    `${API_BASE}/api/v1/materias-primas/importar`,
    formData
  );
  return res.data;
}

export async function consultaFormula(formulacao, matriz) {
  const res = await axios.post(`${API_BASE}/consulta`, { formulacao, matriz });
  return res.data;
}

export async function otimizarFormula(payload) {
  // payload: { metas: {...}, limites_mp: {...}, custo_max?: number }
  const res = await axios.post(`${API_BASE}/optimize`, payload);
  return res.data;
}

export async function listarProjetos() {
  const res = await axios.get(`${API_BASE}/api/v1/projetos`);
  return res.data;
}

export async function criarProjeto(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/projetos`, payload);
  return res.data;
}

export async function atualizarProjeto(id, payload) {
  const res = await axios.patch(`${API_BASE}/api/v1/projetos/${id}`, payload);
  return res.data;
}

export async function criarVersaoFormula(projetoId, payload) {
  const res = await axios.post(
    `${API_BASE}/api/v1/projetos/${projetoId}/versoes`,
    payload
  );
  return res.data;
}

export async function executarOtimizacaoProjeto(projetoId, payload) {
  const res = await axios.post(
    `${API_BASE}/api/v1/projetos/${projetoId}/otimizacoes`,
    payload
  );
  return res.data;
}

export async function obterExecucaoOtimizacao(id) {
  const res = await axios.get(`${API_BASE}/api/v1/otimizacoes/${id}`);
  return res.data;
}

export async function listarCategoriasProduto(ativa = null) {
  const res = await axios.get(`${API_BASE}/api/v1/categorias-produto`, {
    params: ativa == null ? {} : { ativa },
  });
  return res.data;
}

export async function criarCategoriaProduto(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/categorias-produto`, payload);
  return res.data;
}

export async function atualizarCategoriaProduto(id, payload) {
  const res = await axios.patch(`${API_BASE}/api/v1/categorias-produto/${id}`, payload);
  return res.data;
}

export async function obterDiagnosticoCategoria(id) {
  const res = await axios.get(`${API_BASE}/api/v1/categorias-produto/${id}/diagnostico-cadastral`);
  return res.data;
}

export async function listarComponentesRegulatorios(ativo = null) {
  const res = await axios.get(`${API_BASE}/api/v1/componentes-regulatorios`, {
    params: ativo == null ? {} : { ativo },
  });
  return res.data;
}

export async function criarComponenteRegulatorio(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/componentes-regulatorios`, payload);
  return res.data;
}

export async function atualizarComponenteRegulatorio(id, payload) {
  const res = await axios.patch(`${API_BASE}/api/v1/componentes-regulatorios/${id}`, payload);
  return res.data;
}

export async function listarComposicoesRegulatorias(mpId) {
  const res = await axios.get(`${API_BASE}/api/v1/materias-primas/${mpId}/componentes-regulatorios`);
  return res.data;
}

export async function criarComposicaoRegulatoria(mpId, payload) {
  const res = await axios.post(`${API_BASE}/api/v1/materias-primas/${mpId}/componentes-regulatorios`, payload);
  return res.data;
}

export async function ativarComposicaoRegulatoria(id, ativo) {
  const res = await axios.patch(`${API_BASE}/api/v1/composicoes-componentes-mp/${id}`, { ativo });
  return res.data;
}

export async function listarRegrasRegulatorias(categoriaId = null) {
  const res = await axios.get(`${API_BASE}/api/v1/regras-regulatorias`, {
    params: categoriaId ? { categoria_id: categoriaId } : {},
  });
  return res.data;
}

export async function criarRegraRegulatoria(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/regras-regulatorias`, payload);
  return res.data;
}

export async function ativarRegraRegulatoria(id, ativa) {
  const res = await axios.patch(`${API_BASE}/api/v1/regras-regulatorias/${id}`, { ativa });
  return res.data;
}

export async function revisarRegraRegulatoria(id, payload) {
  const res = await axios.post(`${API_BASE}/api/v1/regras-regulatorias/${id}/revisoes`, payload);
  return res.data;
}

export async function listarItensEmbalagem() {
  const res = await axios.get(`${API_BASE}/api/v1/itens-embalagem`);
  return res.data;
}

export async function criarItemEmbalagem(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/itens-embalagem`, payload);
  return res.data;
}

export async function atualizarItemEmbalagem(id, payload) {
  const res = await axios.patch(`${API_BASE}/api/v1/itens-embalagem/${id}`, payload);
  return res.data;
}

export async function listarApresentacoes() {
  const res = await axios.get(`${API_BASE}/api/v1/apresentacoes`);
  return res.data;
}

export async function criarApresentacao(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/apresentacoes`, payload);
  return res.data;
}

export async function listarCenarios(projetoId = null) {
  const res = await axios.get(`${API_BASE}/api/v1/cenarios`, {
    params: projetoId ? { projeto_id: projetoId } : {},
  });
  return res.data;
}

export async function criarCenario(payload) {
  const res = await axios.post(`${API_BASE}/api/v1/cenarios`, payload);
  return res.data;
}

export async function baixarTemplateImportacaoCadastral(signal) {
  const res = await axios.get(`${API_BASE}/api/v1/importacoes-cadastrais/template`, {
    responseType: 'blob',
    signal,
  });
  return res.data;
}

function formularioImportacao(arquivo) {
  const dados = new FormData();
  dados.append('arquivo', arquivo);
  return dados;
}

export async function validarImportacaoCadastral(arquivo, signal) {
  const res = await axios.post(
    `${API_BASE}/api/v1/importacoes-cadastrais/validar`,
    formularioImportacao(arquivo),
    { signal }
  );
  return res.data;
}

export async function prepararImportacaoCadastral(arquivo, signal) {
  const res = await axios.post(
    `${API_BASE}/api/v1/importacoes-cadastrais/preparar`,
    formularioImportacao(arquivo),
    { signal }
  );
  return res.data;
}

export async function consultarSessaoImportacaoCadastral(sessaoId, signal) {
  const res = await axios.get(`${API_BASE}/api/v1/importacoes-cadastrais/${sessaoId}`, { signal });
  return res.data;
}

export async function confirmarImportacaoCadastral(sessaoId, token, signal) {
  const res = await axios.post(
    `${API_BASE}/api/v1/importacoes-cadastrais/${sessaoId}/confirmar`,
    { token },
    { signal }
  );
  return res.data;
}
