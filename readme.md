# 🧮 Otimizador de Formulações Nutricionais

Este projeto é uma aplicação interativa desenvolvida em **React + Streamlit**, destinada à **otimização de formulações nutricionais** utilizando modelos de programação linear.  
Ele permite configurar matérias-primas, restrições de nutrientes e exportar resultados detalhados.

---

## 🚀 Funcionalidades
- Interface amigável para seleção de matérias-primas e nutrientes.
- Cálculo automático de inclusões ideais via modelo de otimização.
- Visualização com **gráficos de pizza e tabelas nutricionais**.
- Exportação de resultados em **Excel (.xlsx)** e **PDF (.pdf)**.
- Persistência local de resultados (localStorage).

---

## 🛠️ Tecnologias Utilizadas
- **Python (Streamlit, PuLP, Pandas)**
- **React (Frontend interativo)**
- **TailwindCSS** para estilização
- **Plotly / Recharts** para gráficos

---

## ⚙️ Como Executar
```bash
# 1. Clone o repositório
git clone https://github.com/SEU_USUARIO/NOME_DO_REPOSITORIO.git

# 2. Entre na pasta do projeto
cd NOME_DO_REPOSITORIO

# 3. Instale as dependências (frontend)
npm install

# 4. Rode o frontend
npm start

# 5. (Opcional) Rode o backend Streamlit
streamlit run app.py
