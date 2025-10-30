import React, { useState, useEffect } from "react";

export default function MateriasPrimasTab() {
  const [materia, setMateria] = useState("");
  const [custo, setCusto] = useState("");
  const [carboidratos, setCarboidratos] = useState("");
  const [proteinas, setProteinas] = useState("");
  const [gorduras, setGorduras] = useState("");
  const [materias, setMaterias] = useState([]);

  // Carregar do localStorage
  useEffect(() => {
    const saved = localStorage.getItem("materias_primas");
    if (saved) setMaterias(JSON.parse(saved));
  }, []);

  // Salvar no localStorage
  useEffect(() => {
    localStorage.setItem("materias_primas", JSON.stringify(materias));
  }, [materias]);

  const adicionarMateria = () => {
    if (!materia || !custo)
      return alert("Preencha pelo menos o nome e o custo!");

    const nova = {
      nome: materia,
      custo: parseFloat(custo),
      nutrientes: {
        Carboidratos: parseFloat(carboidratos) || 0,
        Proteínas: parseFloat(proteinas) || 0,
        "Gorduras Totais": parseFloat(gorduras) || 0,
      },
    };

    setMaterias([...materias, nova]);
    setMateria("");
    setCusto("");
    setCarboidratos("");
    setProteinas("");
    setGorduras("");
  };

  const removerMateria = (index) => {
    if (confirm("Remover esta matéria-prima?")) {
      setMaterias(materias.filter((_, i) => i !== index));
    }
  };

  return (
    <div className="max-w-5xl mx-auto bg-white p-6 rounded shadow space-y-4">
      <h2 className="text-xl font-semibold">Cadastro de Matérias-Primas</h2>

      {/* Formulário */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-2">
        <input
          type="text"
          placeholder="Nome"
          value={materia}
          onChange={(e) => setMateria(e.target.value)}
          className="border p-2 rounded col-span-2"
        />
        <input
          type="number"
          placeholder="Custo (R$/kg)"
          value={custo}
          onChange={(e) => setCusto(e.target.value)}
          className="border p-2 rounded"
        />
        <input
          type="number"
          placeholder="Carboidratos (%)"
          value={carboidratos}
          onChange={(e) => setCarboidratos(e.target.value)}
          className="border p-2 rounded"
        />
        <input
          type="number"
          placeholder="Proteínas (%)"
          value={proteinas}
          onChange={(e) => setProteinas(e.target.value)}
          className="border p-2 rounded"
        />
        <input
          type="number"
          placeholder="Gorduras Totais (%)"
          value={gorduras}
          onChange={(e) => setGorduras(e.target.value)}
          className="border p-2 rounded"
        />
        <button
          onClick={adicionarMateria}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Adicionar
        </button>
      </div>

      {/* Tabela */}
      <table className="w-full border-collapse text-sm mt-4">
        <thead>
          <tr className="bg-gray-100">
            <th className="border p-2 text-left">Matéria-Prima</th>
            <th className="border p-2 text-left">Custo (R$/kg)</th>
            <th className="border p-2 text-left">Carboidratos (%)</th>
            <th className="border p-2 text-left">Proteínas (%)</th>
            <th className="border p-2 text-left">Gorduras Totais (%)</th>
            <th className="border p-2 text-center">Ações</th>
          </tr>
        </thead>
        <tbody>
          {materias.length === 0 ? (
            <tr>
              <td colSpan="6" className="text-center p-4 text-gray-500">
                Nenhuma matéria-prima cadastrada.
              </td>
            </tr>
          ) : (
            materias.map((mp, i) => (
              <tr key={i} className="border-t">
                <td className="p-2">{mp.nome}</td>
                <td className="p-2">{mp.custo.toFixed(4)}</td>
                <td className="p-2">{mp.nutrientes.Carboidratos}</td>
                <td className="p-2">{mp.nutrientes.Proteínas}</td>
                <td className="p-2">{mp.nutrientes["Gorduras Totais"]}</td>
                <td className="p-2 text-center">
                  <button
                    onClick={() => removerMateria(i)}
                    className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-xs"
                  >
                    Remover
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
