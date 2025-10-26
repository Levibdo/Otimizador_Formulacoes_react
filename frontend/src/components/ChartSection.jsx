import React from 'react';
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer
} from 'recharts';

const COLORS = [
  '#2563EB', // azul
  '#06B6D4', // ciano
  '#7C3AED', // roxo
  '#F59E0B', // amarelo
  '#EF4444', // vermelho
  '#10B981', // verde
  '#F97316', // laranja
];

// ==========================
// Gráfico de Pizza
// ==========================
export function PieSection({
  data = [],
  valueKey = 'Peso (%)',
  nameKey = 'Matéria-Prima',
  title,
}) {
  const hasData = Array.isArray(data) && data.length > 0;

  return (
    <div className="bg-white p-4 rounded shadow w-full">
      {title && <h3 className="font-semibold mb-2">{title}</h3>}

      <div style={{ width: '100%', height: 300 }}>
        {hasData ? (
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={data}
                dataKey={valueKey}
                nameKey={nameKey}
                innerRadius={60}
                outerRadius={100}
                paddingAngle={3}
                label={({ name, percent }) =>
                  `${name} ${(percent * 100).toFixed(1)}%`
                }
              >
                {data.map((_, idx) => (
                  <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => `${value.toFixed(2)}%`}
                contentStyle={{ fontSize: '0.85rem' }}
              />
              <Legend layout="horizontal" align="center" verticalAlign="bottom" />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            Nenhum dado para exibir.
          </div>
        )}
      </div>
    </div>
  );
}

// ==========================
// Gráfico de Barras Comparativo
// ==========================
export function BarCompare({
  data = [],
  xKey = 'Nutriente',
  series = ['Meta', 'Obtido'],
  title,
}) {
  const hasData = Array.isArray(data) && data.length > 0;

  return (
    <div className="bg-white p-4 rounded shadow w-full">
      {title && <h3 className="font-semibold mb-2">{title}</h3>}

      <div style={{ width: '100%', height: 320 }}>
        {hasData ? (
          <ResponsiveContainer>
            <BarChart data={data}>
              <XAxis dataKey={xKey} tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip
                formatter={(value) => value.toFixed(2)}
                contentStyle={{ fontSize: '0.85rem' }}
              />
              <Legend wrapperStyle={{ fontSize: '0.85rem' }} />
              {series.map((s, i) => (
                <Bar key={s} dataKey={s} fill={COLORS[i % COLORS.length]} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500 text-sm">
            Nenhum dado para exibir.
          </div>
        )}
      </div>
    </div>
  );
}
