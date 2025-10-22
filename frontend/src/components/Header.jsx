export default function Header(){
  return (
    <header className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white p-4 shadow">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">🚀 Otimizador de Formulações</h1>
          <p className="text-sm opacity-80">FastAPI + React + Tailwind — P&D friendly</p>
        </div>
        <div className="text-sm opacity-90">
          <span className="px-3 py-1 rounded bg-white/10">Local</span>
        </div>
      </div>
    </header>
  )
}
