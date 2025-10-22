import { Link } from "react-router-dom";

export default function Navbar() {
  return (
    <nav className="bg-blue-600 text-white p-4 flex justify-between">
      <h1 className="font-semibold text-lg">⚗️ Otimizador de Formulações</h1>
      <div className="flex gap-4">
        <Link to="/">Otimizar</Link>
        <Link to="/consulta">Consulta</Link>
        <Link to="/resultados">Resultados</Link>
      </div>
    </nav>
  );
}
