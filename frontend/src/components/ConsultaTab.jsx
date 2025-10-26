import React, { useEffect, useState } from "react";
import { getMetaData, consultaFormula } from "../api/api";
import { PieSection } from "./ChartSection";

export default function ConsultaTab() {
  const [mps, setMps] = useState([]);
  const [form, setForm] = useState({});
  const [resultado, setResultado] = useState(null);

  useEffect(() => {
    async function load() {
      const d = await getMetaData();
      setMps(d.materias_primas || []);
      const initial = {};
      (d.materias_primas || []).forEach((mp) => (initial[mp] = 0));
      setForm(initial);
    }
    load();
  }, []);

  // Atualiza matérias-primas com limite de 100%
  function updateMp(mp, v) {
    const novoValor = Number(v);
    setForm((prev) => {
      const totalAtual = Object.entries(prev)
        .filter(([k]) => k !== mp)
        .reduce((s, [, val]) => s + val, 0);
      const novoTotal = totalAtual + novoValor;

      if (novoTotal > 100) {
        alert("❗ A soma das matérias-primas não pode ultrapassar 100%");
        return prev;
      }

      return { ...prev, [mp]: novoValor };
    });
  }

  async function handleConsultar() {
    try {
      const res = await consultaFormula(form);
      console.log("📦 Resposta do backend:", res);
      setResultado(res);
    } catch (err) {
      console.error("Erro na consulta:", err);
    }
  }

  // Soma total das MPs
  const totalPercentual = Object.values(form).reduce((a, b) => a + b, 0);

  // Dados filtrados para o gráfico
  const dadosGrafico = Object.keys(form)
    .map((k) => ({ "Matéria-Prima": k, "Peso (%)": form[k] }))
    .filter((d) => d["Peso (%)"] > 0);

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold">🔍 Modo Consulta</h2>
        <p className="text-sm text-gray-600">
          Insira as porcentagens da fórmula (somar 100%).
        </p>
        <div className="mt-2 text-sm">
          Total atual:{" "}
          <strong
            className={
              totalPercentual > 100
                ? "text-red-600"
                : totalPercentual === 100
                ? "text-green-600"
                : "text-blue-600"
            }
          >
            {totalPercentual.toFixed(2)}%
          </strong>
        </div>
      </div>

      {/* Entradas das matérias-primas */}
      <div className="bg-white p-4 rounded shadow grid grid-cols-3 gap-3">
        {mps.map((mp) => (
          <div key={mp} className="space-y-1">
            <label className="text-sm">{mp} (%)</label>
            <input
              type="number"
              min="0"
              max="100"
              step="0.01"
              value={form[mp] || 0}
              onChange={(e) => updateMp(mp, e.target.value)}
              className="w-full border rounded px-2 py-1"
            />
          </div>
        ))}
      </div>

      {/* Botão de consulta */}
      <div className="flex gap-3">
        <button
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          onClick={handleConsultar}
        >
          🔍 Consultar Composição
        </button>
        <div className="text-sm text-gray-600 self-center">
          Resultado será exibido abaixo.
        </div>
      </div>

      {/* Exibição dos resultados */}
      {resultado && (
        <div className="bg-white p-4 rounded shadow">
          <div className="flex justify-between items-center mb-2">
            <h3 className="font-semibold">📊 Resultado</h3>
            <div className="text-sm">
              💰 Custo Total:{" "}
              <strong className="text-green-700">
                R$ {Number(resultado.custo_total || 0).toFixed(4)}
              </strong>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-4">
            {/* Tabela Nutricional */}
            <div className="overflow-y-auto max-h-[400px] border rounded-lg shadow-sm">
              <h4 className="font-medium mb-2 p-2 bg-gray-50 rounded-t-lg">
                Composição Nutricional
              </h4>
              {resultado.nutrientes && Array.isArray(resultado.nutrientes) ? (
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 sticky top-0">
                    <tr>
                      <th className="p-2 text-left w-2/3">Nutriente</th>
                      <th className="p-2 text-left w-1/3">Valor Obtido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.nutrientes.map((n, i) => (
                      <tr
                        key={i}
                        className={`border-t hover:bg-gray-50 ${
                          i % 2 === 0 ? "bg-white" : "bg-gray-50"
                        }`}
                      >
                        <td className="p-2">{n.Nutriente}</td>
                        <td className="p-2">
                          {Number(n["Valor Obtido"] || 0).toFixed(4)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-gray-500 p-2">
                  Nenhum dado nutricional disponível.
                </p>
              )}
            </div>

            {/* Gráfico de pizza */}
            <div className="flex flex-col justify-center items-center">
              <h4 className="font-medium mb-2">Distribuição (entrada)</h4>
              {dadosGrafico.length > 0 ? (
                <PieSection data={dadosGrafico} title="" />
              ) : (
                <p className="text-sm text-gray-500 mt-4">
                  Nenhuma matéria-prima informada.
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
