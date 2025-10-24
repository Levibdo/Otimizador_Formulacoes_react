from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from optimization_engine import otimizar_formula, CUSTO_ROW_NAME
import unicodedata

app = FastAPI(title="Otimizador de Formulações API")

# ============================================================== #
# CONFIGURAÇÃO DE CORS
# ============================================================== #
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================== #
# FUNÇÃO DE NORMALIZAÇÃO DE NOMES
# ============================================================== #
def normalizar_nome(nome):
    """Remove acentos, converte para minúsculas, troca _ por espaço e remove espaços extras."""
    nome = ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    )
    return nome.strip().lower().replace('_', ' ')

# ============================================================== #
# CARREGAR DADOS DE MATÉRIAS-PRIMAS
# ============================================================== #
materias_primas = pd.read_excel("data/MPs_data.xlsx", index_col=0)

materias_primas.columns = materias_primas.columns.str.strip()
materias_primas.index = materias_primas.index.str.strip()

@app.get("/")
def root():
    return {"message": "Otimizador de Formulações API rodando com CORS ativo!"}

@app.get("/data")
def get_data():
    return {
        "materias_primas": list(materias_primas.columns),
        "nutrientes": [i for i in materias_primas.index if i != CUSTO_ROW_NAME],
    }

# ============================================================== #
# ENDPOINT DE OTIMIZAÇÃO
# ============================================================== #
@app.post("/optimize")
async def optimize(request: Request):
    try:
        body = await request.json()
        metas = body.get("metas", {})
        restricoes = body.get("restricoes", {})
        custo_max = body.get("custo_max", 9999)

        resultado = otimizar_formula(
            materias_primas,
            restricoes=restricoes,
            metas=metas,
        )
        return resultado

    except Exception as e:
        print("❌ ERRO NO BACKEND:", e)
        return {"erro": str(e)}

# ============================================================== #
# ENDPOINT DE CONSULTA DE FÓRMULA
# ============================================================== #
@app.post("/consulta")
async def consultar(request: Request):
    try:
        body = await request.json()
        print("📨 Dados recebidos do frontend:", body)
        print("📘 Colunas disponíveis:", list(materias_primas.columns))

        # Captura corretamente o dicionário de formulação
        formulacao = body.get("formulacao", body)

        # Normaliza nomes
        colunas_norm = {normalizar_nome(c): c for c in materias_primas.columns}
        proporcoes_validas = {}

        for mp, valor in formulacao.items():
            try:
                valor_float = float(valor)
            except Exception:
                continue  # ignora valores inválidos

            if valor_float > 0:
                nome_norm = normalizar_nome(mp)
                if nome_norm in colunas_norm:
                    proporcoes_validas[colunas_norm[nome_norm]] = valor_float

        print("✅ MPs reconhecidas:", proporcoes_validas)

        if not proporcoes_validas:
            raise ValueError("Nenhuma matéria-prima válida foi informada.")

        # Cria Series e normaliza proporções
        proporcoes = pd.Series(proporcoes_validas, dtype=float)
        proporcoes = proporcoes / proporcoes.sum()

        # 🔧 Filtra e reordena a matriz conforme as MPs selecionadas
        matriz_filtrada = materias_primas[proporcoes.index]

        # Calcula nutrientes e custo total
        matriz_sem_custo = matriz_filtrada.drop(index=CUSTO_ROW_NAME, errors="ignore")
        nutrientes = matriz_sem_custo.dot(proporcoes)

        custo_por_mp = matriz_filtrada.loc[CUSTO_ROW_NAME] * proporcoes
        custo_total = custo_por_mp.sum()

        resultado_nutrientes = [
            {"Nutriente": n, "Valor Obtido": v} for n, v in nutrientes.items()
        ]
        resultado_custos = [
            {"Matéria-Prima": mp, "Custo": custo} for mp, custo in custo_por_mp.items()
        ]

        print("💰 Custo total:", custo_total)

        return {
            "status": "OK",
            "nutrientes": resultado_nutrientes,
            "custos": resultado_custos,
            "custo_total": custo_total,
        }

    except Exception as e:
        print("❌ ERRO NA CONSULTA:", e)
        return {"erro": str(e)}
