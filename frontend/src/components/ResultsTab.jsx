import React, { useEffect, useState } from "react";
import { PieSection, BarCompare } from "./ChartSection";

export default function ResultsTab(){
  const [resultado, setResultado] = useState(null);

  useEffect(()=>{
    const saved = localStorage.getItem('ultima_otimizacao');
    if(saved) setResultado(JSON.parse(saved));
  }, []);

  if(!resultado){
    return (
      <div className="max-w-6xl mx-auto">
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm">Nenhuma otimização disponível. Execute uma otimização na aba <strong>Otimizacao</strong>.</p>
        </div>
      </div>
    )
  }

  const pieData = Object.entries(resultado.inclusoes || {}).map(([mp, peso]) => ({ 'Matéria-Prima': mp, 'Peso (%)': Number(peso) }));
  // df_comp structure is backend-dependent; if available use it, else create an empty placeholder
  const comp = resultado.conferencia || []; // backend may return 'conferencia' with 'Nutriente','Meta','Obtido'
  let barData = comp.length? comp : [];

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-4 rounded shadow flex justify-between items-center">
        <div>
          <h2 className="font-semibold">Resultados da Otimização</h2>
          <p className="text-sm text-gray-600">Status: <strong>{resultado.status}</strong></p>
        </div>
        <div className="text-right">
          <div className="text-sm text-gray-500">Custo Total</div>
          <div className="text-xl font-bold">R$ {Number(resultado.custo_total).toFixed(4)}</div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <PieSection data={pieData} title="Participação das MPs na Fórmula" />
        {barData.length ? <BarCompare data={barData} title="Meta x Obtido" /> : (
          <div className="bg-white p-4 rounded shadow">
            <h3 className="font-medium">Conferência Nutricional</h3>
            <p className="text-sm text-gray-600 mt-2">Sem dados de conferência (backend não retornou).</p>
          </div>
        )}
      </div>

      <div className="bg-white p-4 rounded shadow">
        <h3 className="font-medium">Fórmula (detalhe)</h3>
        <table className="w-full mt-3 text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-2 text-left">Matéria-Prima</th>
              <th className="p-2 text-left">Peso (%)</th>
            </tr>
          </thead>
          <tbody>
            {pieData.map((r,i)=>(
              <tr key={i} className="border-t">
                <td className="p-2">{r['Matéria-Prima']}</td>
                <td className="p-2">{Number(r['Peso (%)']).toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
