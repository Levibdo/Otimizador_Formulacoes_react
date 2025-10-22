import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export async function getMetaData() {
  const res = await axios.get(`${API_BASE}/data`);
  return res.data;
}

export async function consultaFormula(formulacao) {
  const res = await axios.post(`${API_BASE}/consulta`, { formulacao });
  return res.data;
}

export async function otimizarFormula(payload) {
  // payload: { metas: {...}, limites_mp: {...}, custo_max?: number }
  const res = await axios.post(`${API_BASE}/optimize`, payload);
  return res.data;
}
