import React, { useEffect, useState } from "react";
import { getMetaData, otimizarFormula } from "../api/api";

export default function OptimizationTab({ setTab }) {
  const [mps, setMps] = useState([]);
  const [nutrientes, setNutrientes] = useState([]);
  const [dadosMps, setDadosMps] = useState({});
  const [restricoes, setRestricoes] = useState([]);
  const [custoMax, setCustoMax] = useState(9999);
  const [statusMsg, setStatusMsg] = useState(null);

  // ==========================================================
  // 🔹 Carregar MPs do backend + MPs do localStorage
  // ==========================================================
  useEffect(() => {
    async function load() {
      try {
        const data = await getMetaData();

        // Dados do backend
        let backendMPs = data.materias_primas || [];
        let backendNutrientes = data.nutrientes || [];
        let backendMatriz = data.matriz || {};

        // MPs salvas localmente
        const localMPs = JSON.parse(localStorage.getItem("materias_primas")) || [];

        // 🔄 Combinar MPs
        localMPs.forEach((mp) => {
          // Adiciona se ainda não existir
          if (!backendMPs.includes(mp.nome)) {
            backendMPs.push(mp.nome);
          }

          // Adiciona/atualiza dados nutricionais e custo
          backendMatriz[mp.nome] = {
            Carboidratos: parseFloat(mp.carboidratos) || 0,
            Proteínas: parseFloat(mp.proteinas) || 0,
            "Gorduras Totais": parseFloat(mp.gorduras) || 0,
            Custo: parseFloat(mp.custo) || 0,
          };
        });

        setMps(backendMPs);
        setNutrientes(backendNutrientes);
        setDadosMps(backendMatriz);
      } catch (err) {
        console.error("Erro ao carregar metadados:", err);
        setStatusMsg("Erro ao carregar metadados.");
      }
    }
    load();
  }, []);

  // ==========================================================
  // 🧩 Gerenciar restrições
  // ==========================================================
  function addMpRestriction() {
    if (mps.length === 0) return;
    setRestricoes((r) => [
      ...r,
      { id: Date.now(), item: mps[0], tipo: "<=", valor: 0, tipo_item: "MP" },
    ]);
  }

  function addNutrRestriction() {
    if (nutrientes.length === 0) return;
    setRestricoes((r) => [
      ...r,
      { id: Date.now(), item: nutrientes[0], tipo: ">=", valor: 0, tipo_item: "Nutriente" },
    ]);
  }

  function updateRestriction(idx, field, value) {
    setRestricoes((prev) =>
      prev.map((p, i) => (i === idx ? { ...p, [field]: value } : p))
    );
  }

  function removeRestriction(idx) {
    setRestricoes((prev) => prev.filter((_, i) => i !== idx));
  }

  // ==========================================================
  // 🚀 Enviar para o backend e otimizar
  // ==========================================================
  async function handleOptimize() {
    const metas = {};
    const limites_mp = {};

    restricoes.forEach((r) => {
      if (r.tipo_item === "Nutriente") {
        if (!metas[r.item]) metas[r.item] = [null, null];
        if (r.tipo === ">=") metas[r.item][0] = parseFloat(r.valor);
        if (r.tipo === "<=") metas[r.item][1] = parseFloat(r.valor);
        if (r.tipo === "=")
          metas[r.item] = [parseFloat(r.valor), parseFloat(r.valor)];
      } else if (r.tipo_item === "MP") {
        if (!limites_mp[r.item]) limites_mp[r.item] = [null, null];
        if (r.tipo === ">=") limites_mp[r.item][0] = parseFloat(r.valor);
        if (r.tipo === "<=") limites_mp[r.item][1] = parseFloat(r.valor);
        if (r.tipo === "=")
          limites_mp[r.item] = [parseFloat(r.valor), parseFloat(r.valor)];
      }
    });

    const payload = {
      metas,
      restricoes: limites_mp,
      custo_max: custoMax,
      matriz: dadosMps, // 🔹 inclui MPs do localStorage também
    };

    console.log("🔍 Enviando payload completo:", payload);

    setStatusMsg("Executando otimização...");
    try {
      const res = await otimizarFormula(payload);
      console.log("✅ Resposta do backend:", res);

      setStatusMsg(
        `Status: ${res.status || "Indefinido"} — Custo: ${
          res.custo_total ? res.custo_total.toFixed(4) : "-"
        }`
      );

      localStorage.setItem("ultima_otimizacao", JSON.stringify(res));
      setTab("resultados");
    } catch (err) {
      console.error("Erro na otimização:", err);
      setStatusMsg("Erro na otimização. Veja o console.");
    }
  }

  // ==========================================================
  // 🧱 Interface
  // ==========================================================
  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="bg-white p-4 rounded shadow flex items-center justify-between">
        <div>
          <h2 className="font-semibold">Configuração</h2>
          <p className="text-sm text-gray-600">
            Defina metas e limites para a otimização.
          </p>
        </div>
        <div className="flex gap-3 items-center">
          <label className="text-sm">Custo Máx. (R$)</label>
          <input
            type="number"
            value={custoMax}
            onChange={(e) => setCustoMax(parseFloat(e.target.value) || 0)}
            className="border rounded px-2 py-1 w-32"
          />
          <button
            onClick={handleOptimize}
            className="bg-blue-600 text-white px-4 py-2 rounded"
          >
            🚀 Otimizar
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <h3 className="font-medium mb-3">Restrições</h3>
          <div className="flex gap-2 mb-3">
            <button
              onClick={addMpRestriction}
              className="px-3 py-1 rounded bg-gray-100"
            >
              ➕ MP
            </button>
            <button
              onClick={addNutrRestriction}
              className="px-3 py-1 rounded bg-gray-100"
            >
              ➕ Nutriente
            </button>
          </div>

          {restricoes.map((r, i) => (
            <div
              key={r.id}
              className="flex flex-wrap gap-2 items-center bg-white p-2 rounded border border-gray-200"
            >
              <select
                value={r.item}
                onChange={(e) => updateRestriction(i, "item", e.target.value)}
                className="flex-1 border rounded px-2 py-1"
              >
                {(r.tipo_item === "MP" ? mps : nutrientes).map((opt) => (
                  <option key={opt} value={opt}>
                    {opt}
                  </option>
                ))}
              </select>
              <select
                value={r.tipo}
                onChange={(e) => updateRestriction(i, "tipo", e.target.value)}
                className="w-20 border rounded px-2 py-1"
              >
                <option value="<=">{"≤"}</option>
                <option value=">=">{"≥"}</option>
                <option value="=">{"="}</option>
              </select>
              <input
                type="number"
                value={r.valor}
                onChange={(e) => updateRestriction(i, "valor", e.target.value)}
                className="w-28 border rounded px-2 py-1"
              />
              <button
                onClick={() => removeRestriction(i)}
                className="text-red-500 px-2"
              >
                ✖
              </button>
            </div>
          ))}
        </div>

        <div className="bg-white p-4 rounded shadow">
          <h3 className="font-medium mb-3">Resumo / Execução</h3>
          <ul className="text-sm space-y-1">
            {restricoes.map((r, idx) => (
              <li key={idx}>
                {r.tipo_item} — {r.item} {r.tipo} {r.valor}
              </li>
            ))}
          </ul>
          <div className="mt-4">
            <p className="text-sm">{statusMsg}</p>
            <p className="text-xs text-gray-500 mt-2">
              Após a otimização, você será levado automaticamente à aba{" "}
              <strong>Resultados</strong>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
