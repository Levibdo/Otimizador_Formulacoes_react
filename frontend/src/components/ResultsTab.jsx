import React, { useEffect, useState } from "react";
import { PieSection, BarCompare } from "./ChartSection";

export default function ResultsTab() {
  const [resultado, setResultado] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem("ultima_otimizacao");
    if (saved) setResultado(JSON.parse(saved));
  }, []);

  if (!resultado) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm">
            Nenhuma otimização disponível. Execute uma otimização na aba{" "}
            <strong>Otimização</strong>.
          </p>
        </div>
      </div>
    );
  }

  // 🔹 Filtra MPs com peso > 0
  const pieData = Object.entries(resultado.inclusoes || {})
    .filter(([_, peso]) => Number(peso) > 0)
    .map(([mp, peso]) => ({
      "Matéria-Prima": mp,
      "Peso (%)": Number(peso),
    }));

  // 🔹 Custo individual
  const custosIndividuais = resultado.custos_individuais || {};

  // 🔹 Junta peso + custo
  const tabela = pieData.map((item) => ({
    ...item,
    "Custo (R$)": custosIndividuais[item["Matéria-Prima"]]
      ? Number(custosIndividuais[item["Matéria-Prima"]]).toFixed(4)
      : "-",
  }));

  // 🔹 Dados da conferência nutricional
  const conferencia = resultado.conferencia_nutricional || {};

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      {/* Cabeçalho */}
      <div className="bg-white p-4 rounded shadow flex justify-between items-center">
        <div>
          <h2 className="font-semibold">Resultados da Otimização</h2>
          <p className="text-sm text-gray-600">
            Status: <strong>{resultado.status}</strong>
          </p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">Custo Total</div>
          <div className="text-xl font-bold">
            R$ {Number(resultado.custo_total).toFixed(4)}
          </div>
        </div>
      </div>

      {/* Gráficos */}
      <div className="grid grid-cols-2 gap-4">
        <PieSection data={pieData} title="Participação das MPs na Fórmula" />

        {/* Conferência Nutricional */}
        <div className="bg-white p-4 rounded shadow">
          <h3 className="font-medium mb-2">Conferência Nutricional</h3>

          {Object.keys(conferencia).length > 0 ? (
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="p-2 text-left">Nutriente</th>
                  <th className="p-2 text-left">Valor Obtido</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(conferencia).map(([nutr, val]) => (
                  <tr key={nutr} className="border-t">
                    <td className="p-2">{nutr}</td>
                    <td className="p-2">{val}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-gray-600 mt-2">
              Sem dados de conferência (backend não retornou).
            </p>
          )}
        </div>
      </div>

      {/* Tabela Detalhada */}
      <div className="bg-white p-4 rounded shadow">
        <h3 className="font-medium">Fórmula (detalhe)</h3>
        <table className="w-full mt-3 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Matéria-Prima</th>
              <th className="p-2 text-left">Peso (%)</th>
              <th className="p-2 text-left">Custo (R$)</th>
            </tr>
          </thead>
          <tbody>
            {tabela.map((r, i) => (
              <tr key={i} className="border-t">
                <td className="p-2">{r["Matéria-Prima"]}</td>
                <td className="p-2">{r["Peso (%)"].toFixed(4)}</td>
                <td className="p-2">{r["Custo (R$)"]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
