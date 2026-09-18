export default function Tabs({ tab, setTab }) {
  const tabs = [
    { id: "otimizacao", label: "📊 Otimização" },
    { id: "consulta", label: "🔍 Consulta" },
    { id: "resultados", label: "📈 Resultados" },
    { id: "projetos", label: "🧪 Projetos" },
    { id: "apresentacoes", label: "📦 Apresentações" },
    { id: "materias", label: "🧱 Matérias-Primas" }
  ];

  return (
    <div className="bg-white shadow-sm">
      <div className="max-w-6xl mx-auto flex overflow-x-auto">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-5 py-4 min-w-max flex-1 text-center font-medium ${
              tab === t.id ? "border-b-2 border-blue-600 text-blue-600" : "text-gray-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
