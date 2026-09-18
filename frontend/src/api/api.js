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

export async function consultaFormula(formulacao, matriz) {
  const res = await axios.post(`${API_BASE}/consulta`, { formulacao, matriz });
  return res.data;
}

export async function otimizarFormula(payload) {
  // payload: { metas: {...}, limites_mp: {...}, custo_max?: number }
  const res = await axios.post(`${API_BASE}/optimize`, payload);
  return res.data;
}
