import React, { useState } from "react";
import Header from "./components/Header";
import Tabs from "./components/Tabs";
import OptimizationTab from "./components/OptimizationTab";
import ConsultaTab from "./components/ConsultaTab";
import ResultsTab from "./components/ResultsTab";
import MateriasPrimasTab from "./components/MateriasPrimasTab";

export default function App() {
  const [tab, setTab] = useState("otimizacao");

  // ✅ Estado global de matérias-primas
  const [materiasPrimas, setMateriasPrimas] = useState([]);

  return (
    <div className="min-h-screen bg-gray-100 text-gray-800">
      <Header />
      <Tabs tab={tab} setTab={setTab} />

      <div className="p-6">
        {tab === "otimizacao" && (
          <OptimizationTab
            setTab={setTab}
            materiasPrimas={materiasPrimas}
          />
        )}

        {tab === "consulta" && <ConsultaTab />}

        {tab === "resultados" && <ResultsTab />}

        {tab === "materias" && (
          <MateriasPrimasTab
            materiasPrimas={materiasPrimas} 
            setMateriasPrimas={setMateriasPrimas} 
          />
        )}
      </div>
    </div>
  );
}
