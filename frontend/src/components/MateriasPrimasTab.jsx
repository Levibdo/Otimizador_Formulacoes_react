import React, { useState, useEffect } from "react";

export default function MateriasPrimasTab() {
  const [materia, setMateria] = useState("");
  const [custo, setCusto] = useState("");
  const [carboidratos, setCarboidratos] = useState("");
  const [proteinas, setProteinas] = useState("");
  const [gorduras, setGorduras] = useState("");
  const [materias, setMaterias] = useState([]);
  const [arquivo, setArquivo] = useState(null);

  const usuarioId = "teste1"; // ⚠️ pode futuramente vir do login

  // Carregar do localStorage
  useEffect(() => {
    const saved = localStorage.getItem("materias_primas");
    if (saved) setMaterias(JSON.parse(saved));
  }, []);

  // Salvar no localStorage
  useEffect(() => {
    localStorage.setItem("materias_primas", JSON.stringify(materias));
  }, [materias]);

  // ------------------------------
  // Importar Matérias-Primas
  // ------------------------------
  const importarMaterias = async () => {
    if (!arquivo) {
      alert("Selecione um arquivo .xlsx ou .csv para importar!");
      return;
    }

    const formData = new FormData();
    formData.append("usuario_id", usuarioId);
    formData.append("file", arquivo);

    try {
      const response = await fetch("http://127.0.0.1:8000/importar_materias_primas", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const err = await response.text();
        throw new Error(err);
      }

      const data = await response.json();
      alert(data.mensagem || "Importação concluída!");

      // Opcional: atualizar lista local
      listarMaterias();
    } catch (err) {
      alert("Erro ao importar: " + err.message);
    }
  };

  // ------------------------------
  // Exportar Matérias-Primas
  // ------------------------------
  const exportarMaterias = async () => {
    try {
      const response = await fetch(
        `http://127.0.0.1:8000/exportar_materias_primas?usuario_id=${usuarioId}`
      );

      if (!response.ok) throw new Error("Falha ao exportar.");

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `materias_primas_${usuarioId}.xlsx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      alert("Erro ao exportar: " + err.message);
    }
  };

  // ------------------------------
  // (Opcional) Buscar MPs do banco
  // ------------------------------
  const listarMaterias = async () => {
    try {
      const res = await fetch(`http://127.0.0.1:8000/mp/${usuarioId}`);
      if (res.ok) {
        const data = await res.json();
        console.log("Materias importadas:", data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // ------------------------------
  // Adicionar / remover MPs locais
  // ------------------------------
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

  // ------------------------------
  // JSX
  // ------------------------------
  return (
    <div className="max-w-5xl mx-auto bg-white p-6 rounded shadow space-y-4">
      <h2 className="text-xl font-semibold">Cadastro de Matérias-Primas</h2>

      {/* Botões de Importar / Exportar */}
      <div className="flex items-center gap-3 mb-4">
        <input
          type="file"
          accept=".xlsx,.csv"
          onChange={(e) => setArquivo(e.target.files[0])}
          className="border p-2 rounded"
        />
        <button
          onClick={importarMaterias}
          className="bg-green-600 text-white px-4 py-2 rounded"
        >
          📥 Importar
        </button>
        <button
          onClick={exportarMaterias}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          📤 Exportar
        </button>
      </div>

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
