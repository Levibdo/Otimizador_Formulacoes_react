import React, { useEffect, useState, useRef } from "react";
import { PieSection } from "./ChartSection";
import * as XLSX from "xlsx";
import { saveAs } from "file-saver";
import jsPDF from "jspdf";
import html2canvas from "html2canvas";
import { criarVersaoFormula, listarProjetos } from "../api/api";

export default function ResultsTab() {
  const [resultado, setResultado] = useState(null);
  const [projetos, setProjetos] = useState([]);
  const [projetoId, setProjetoId] = useState("");
  const [observacao, setObservacao] = useState("");
  const [mensagemVersao, setMensagemVersao] = useState("");
  const [salvandoVersao, setSalvandoVersao] = useState(false);
  const relatorioRef = useRef();

  useEffect(() => {
    const saved = localStorage.getItem("ultima_otimizacao");
    if (saved) setResultado(JSON.parse(saved));
    listarProjetos()
      .then((dados) => {
        const ativos = dados.filter((projeto) => projeto.status === "ATIVO");
        setProjetos(ativos);
        if (ativos.length) setProjetoId(String(ativos[0].id));
      })
      .catch(() => setMensagemVersao("Não foi possível carregar os projetos."));
  }, []);

  const salvarVersao = async () => {
    if (!projetoId) {
      setMensagemVersao("Crie ou selecione um projeto ativo.");
      return;
    }
    const contexto = resultado.contexto_otimizacao || {};
    setSalvandoVersao(true);
    try {
      const versao = await criarVersaoFormula(Number(projetoId), {
        observacao: observacao.trim() || null,
        status_solver: resultado.status || "Indefinido",
        custo_total: resultado.custo_total == null ? null : Number(resultado.custo_total),
        inclusoes: resultado.inclusoes || {},
        custos_individuais: resultado.custos_individuais || {},
        composicao_nutricional: resultado.conferencia_nutricional || {},
        parametros: {
          metas: contexto.metas || {},
          restricoes: contexto.restricoes || {},
          custo_max: contexto.custo_max ?? null,
        },
        matriz_snapshot: contexto.matriz || {},
      });
      setMensagemVersao(`Versão ${versao.numero} salva com sucesso.`);
      setObservacao("");
    } catch (erro) {
      setMensagemVersao(erro.response?.data?.detail || "Erro ao salvar a versão.");
    } finally {
      setSalvandoVersao(false);
    }
  };

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

  // ==========================
  // 🔹 Preparar dados
  // ==========================
  const pieData = Object.entries(resultado.inclusoes || {})
    .filter(([_, peso]) => Number(peso) > 0)
    .map(([mp, peso]) => ({
      "Matéria-Prima": mp,
      "Peso (%)": Number(peso),
    }));

  const custosIndividuais = resultado.custos_individuais || {};

  const tabela = pieData.map((item) => ({
    ...item,
    "Custo (R$)": custosIndividuais[item["Matéria-Prima"]]
      ? Number(custosIndividuais[item["Matéria-Prima"]]).toFixed(4)
      : "-",
  }));

  const conferencia = resultado.conferencia_nutricional || {};

  // ==========================
  // 🔹 Exportar CSV
  // ==========================
  const exportarCSV = () => {
    const linhas = [];
    linhas.push("Matéria-Prima,Peso (%),Custo (R$)");
    tabela.forEach((r) =>
      linhas.push(`${r["Matéria-Prima"]},${r["Peso (%)"]},${r["Custo (R$)"]}`)
    );

    linhas.push("\nComposição Nutricional:");
    linhas.push("Nutriente,Valor Obtido");
    Object.entries(conferencia).forEach(([nutr, val]) =>
      linhas.push(`${nutr},${val}`)
    );

    const blob = new Blob([linhas.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    saveAs(blob, "resultado_otimizacao.csv");
  };

  // ==========================
  // 🔹 Exportar Excel
  // ==========================
  const exportarExcel = () => {
    const wb = XLSX.utils.book_new();

    const ws1 = XLSX.utils.json_to_sheet(tabela);
    XLSX.utils.book_append_sheet(wb, ws1, "Fórmula");

    const nutrArray = Object.entries(conferencia).map(([nutr, val]) => ({
      Nutriente: nutr,
      "Valor Obtido": val,
    }));
    const ws2 = XLSX.utils.json_to_sheet(nutrArray);
    XLSX.utils.book_append_sheet(wb, ws2, "Composição Nutricional");

    XLSX.writeFile(wb, "resultado_otimizacao.xlsx");
  };

  // ==========================
  // 🔹 Exportar PDF (com gráfico)
  // ==========================
  const exportarPDF = async () => {
    const input = relatorioRef.current;
    const canvas = await html2canvas(input, { scale: 2, useCORS: true });
    const imgData = canvas.toDataURL("image/png");

    const pdf = new jsPDF("p", "mm", "a4");
    const pageWidth = pdf.internal.pageSize.getWidth();
    const imgWidth = pageWidth - 20; // margem lateral
    const imgHeight = (canvas.height * imgWidth) / canvas.width;

    pdf.addImage(imgData, "PNG", 10, 10, imgWidth, imgHeight);
    pdf.save("resultado_otimizacao.pdf");
  };

  // ==========================
  // 🔹 Renderização
  // ==========================
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

          <div className="flex gap-2 mt-2 justify-end">
            <button
              onClick={exportarCSV}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm px-3 py-1 rounded"
            >
              CSV
            </button>
            <button
              onClick={exportarExcel}
              className="bg-green-600 hover:bg-green-700 text-white text-sm px-3 py-1 rounded"
            >
              Excel
            </button>
            <button
              onClick={exportarPDF}
              className="bg-red-600 hover:bg-red-700 text-white text-sm px-3 py-1 rounded"
            >
              PDF
            </button>
          </div>
        </div>
      </div>

      <div className="bg-white p-4 rounded shadow space-y-3">
        <div>
          <h3 className="font-semibold">Salvar no histórico do projeto</h3>
          <p className="text-sm text-gray-600">
            Cria uma versão imutável com fórmula, custo, parâmetros, requisitos e matriz usados.
          </p>
        </div>
        <div className="grid md:grid-cols-3 gap-3">
          <select className="border rounded px-3 py-2" value={projetoId} onChange={(e) => setProjetoId(e.target.value)}>
            {projetos.length === 0 && <option value="">Nenhum projeto ativo</option>}
            {projetos.map((projeto) => <option key={projeto.id} value={projeto.id}>{projeto.codigo} — {projeto.nome}</option>)}
          </select>
          <input className="border rounded px-3 py-2 md:col-span-2" placeholder="Observação desta versão (opcional)" value={observacao} onChange={(e) => setObservacao(e.target.value)} />
        </div>
        <div className="flex items-center gap-3">
          <button disabled={salvandoVersao || !projetoId} onClick={salvarVersao} className="bg-indigo-600 disabled:bg-indigo-300 text-white px-4 py-2 rounded">
            {salvandoVersao ? "Salvando..." : "Salvar versão"}
          </button>
          {mensagemVersao && <p className="text-sm text-gray-700">{mensagemVersao}</p>}
        </div>
      </div>

      {/* 🔹 Relatório completo para exportar */}
      <div ref={relatorioRef} className="space-y-4">
        {/* Layout lado a lado */}
        <div className="grid grid-cols-2 gap-4">
          {/* Gráfico de Pizza */}
          <PieSection data={pieData} title="Participação das MPs na Fórmula" />

          {/* Tabela Nutricional */}
          <div className="overflow-y-auto max-h-[400px] border rounded-lg shadow-sm bg-white">
            <h4 className="font-medium mb-2 p-2 bg-gray-50 rounded-t-lg">
              Composição Nutricional
            </h4>
            {Object.keys(conferencia).length > 0 ? (
              <table className="w-full text-sm">
                <thead className="bg-gray-100 sticky top-0">
                  <tr>
                    <th className="p-2 text-left w-2/3">Nutriente</th>
                    <th className="p-2 text-left w-1/3">Valor Obtido</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(conferencia).map(([nutr, val], i) => (
                    <tr
                      key={nutr}
                      className={`border-t hover:bg-gray-50 ${
                        i % 2 === 0 ? "bg-white" : "bg-gray-50"
                      }`}
                    >
                      <td className="p-2">{nutr}</td>
                      <td className="p-2">{Number(val || 0).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-sm text-gray-600 p-2">
                Nenhum dado nutricional disponível.
              </p>
            )}
          </div>
        </div>

        {/* Tabela de MPs */}
        <div className="bg-white p-4 rounded shadow">
          <h3 className="font-medium">Fórmula (detalhe)</h3>
          <div className="overflow-y-auto max-h-[400px] mt-3 border rounded-lg">
            <table className="w-full text-sm">
              <thead className="bg-gray-100 sticky top-0">
                <tr>
                  <th className="p-2 text-left">Matéria-Prima</th>
                  <th className="p-2 text-left">Peso (%)</th>
                  <th className="p-2 text-left">Custo (R$)</th>
                </tr>
              </thead>
              <tbody>
                {tabela.map((r, i) => (
                  <tr
                    key={i}
                    className={`border-t hover:bg-gray-50 ${
                      i % 2 === 0 ? "bg-white" : "bg-gray-50"
                    }`}
                  >
                    <td className="p-2">{r["Matéria-Prima"]}</td>
                    <td className="p-2">{r["Peso (%)"].toFixed(4)}</td>
                    <td className="p-2">{r["Custo (R$)"]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
