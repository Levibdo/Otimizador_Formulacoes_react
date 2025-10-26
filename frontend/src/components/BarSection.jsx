/* import React from "react";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

export function BarSection({ data, title }) {
  if (!data || data.length === 0) return <p>Nenhum dado disponível.</p>;

  const labels = data.map((d) => d.Nutriente);
  const valores = data.map((d) => d["Valor Obtido"]);

  const chartData = {
    labels,
    datasets: [
      {
        label: "Valor Obtido",
        data: valores,
        backgroundColor: "rgba(37, 99, 235, 0.6)",
        borderRadius: 6,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      title: { display: true, text: title },
    },
  };

  return <Bar data={chartData} options={options} />;
}
