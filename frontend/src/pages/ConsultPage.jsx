import { useState } from "react";
import axios from "axios";

export default function ConsultPage() {
  const [formData, setFormData] = useState({});
  const [resultado, setResultado] = useState(null);

  const handleChange = (mp, value) => {
    setFormData({ ...formData, [mp]: parseFloat(value) || 0 });
  };

  const handleSubmit = async () => {
    const res = await axios.post("http://localhost:8000/consulta", { formulacao: formData });
    setResultado(res.data);
  };

  return (
    <div>
      <h2 className="text-2xl font-semibold mb-4">🔍 Consulta de Formulação</h2>
      <div className="grid grid-cols-3 gap-2">
        {["milho", "farelo_soja", "calcario", "óleo"].map((mp) => (
          <input
            key={mp}
            type="number"
            placeholder={`${mp} (%)`}
            onChange={(e) => handleChange(mp, e.target.value)}
            className="border rounded p-2"
          />
        ))}
      </div>
      <button
        onClick={handleSubmit}
        className="mt-4 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
      >
        Calcular
      </button>

      {resultado && (
        <div className="mt-6 bg-white shadow p-4 rounded">
          <h3 className="font-semibold">Custo Total: R$ {resultado.custo_total}</h3>
          <table className="w-full mt-3 border">
            <thead>
              <tr className="bg-gray-100">
                <th>Nutriente</th>
                <th>Valor Obtido</th>
              </tr>
            </thead>
            <tbody>
              {resultado.nutrientes.map((n, i) => (
                <tr key={i}>
                  <td className="border p-2">{n.Nutriente}</td>
                  <td className="border p-2">{n["Valor Obtido"]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
