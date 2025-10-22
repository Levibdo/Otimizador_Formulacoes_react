import React, { useEffect, useState } from "react";
import { getMetaData, consultaFormula } from "../api/api";
import { PieSection } from "./ChartSection";

export default function ConsultaTab(){
  const [mps, setMps] = useState([]);
  const [form, setForm] = useState({});
  const [resultado, setResultado] = useState(null);

  useEffect(()=>{
    async function load(){ 
      const d = await getMetaData();
      setMps(d.materias_primas || []);
      // initialize form
      const initial = {};
      (d.materias_primas || []).forEach(mp => initial[mp]=0);
      setForm(initial);
    }
    load();
  }, []);

  function updateMp(mp, v){
    setForm(prev => ({...prev, [mp]: Number(v)}));
  }

  async function handleConsultar(){
    const res = await consultaFormula(form);
    setResultado(res);
  }

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-4 rounded shadow">
        <h2 className="font-semibold">🔍 Modo Consulta</h2>
        <p className="text-sm text-gray-600">Insira as porcentagens da fórmula (somar 100%).</p>
      </div>

      <div className="bg-white p-4 rounded shadow grid grid-cols-3 gap-3">
        {mps.map(mp => (
          <div key={mp} className="space-y-1">
            <label className="text-sm">{mp} (%)</label>
            <input type="number" min="0" max="100" step="0.01" value={form[mp]||0} onChange={e=>updateMp(mp,e.target.value)} className="w-full border rounded px-2 py-1" />
          </div>
        ))}
      </div>

      <div className="flex gap-3">
        <button className="bg-blue-600 text-white px-4 py-2 rounded" onClick={handleConsultar}>🔍 Consultar Composição</button>
        <div className="text-sm text-gray-600 self-center">Resultado será exibido abaixo.</div>
      </div>

      {resultado && (
        <>
          <div className="bg-white p-4 rounded shadow">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">Resultado</h3>
              <div className="text-sm">Custo Total: <strong>R$ {resultado.custo_total?.toFixed(4)}</strong></div>
            </div>

            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <h4 className="font-medium mb-2">Composição Nutricional</h4>
                <table className="w-full text-sm border">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="p-2 text-left">Nutriente</th>
                      <th className="p-2 text-left">Valor Obtido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {resultado.nutrientes.map((n,i)=>(
                      <tr key={i} className="border-t">
                        <td className="p-2">{n.Nutriente}</td>
                        <td className="p-2">{Number(n["Valor Obtido"]).toFixed(4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div>
                <PieSection data={ (Object.keys(form).map(k=> ({ "Matéria-Prima": k, "Peso (%)": form[k] })) ).filter(d=>d["Peso (%)"]>0) } title="Distribuição (entrada)" />
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
