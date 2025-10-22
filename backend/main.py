from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from optimization_engine import otimizar_formula, CUSTO_ROW_NAME

app = FastAPI(title="Otimizador de Formulações API")

# ==============================================================
# CORS CONFIGURAÇÃO
# ==============================================================
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

# ==============================================================
# DADOS DE MATÉRIAS-PRIMAS
# ==============================================================
materias_primas = pd.read_excel("data/MPs_data.xlsx", index_col=0)

@app.get("/")
def root():
    return {"message": "Otimizador de Formulações API rodando com CORS ativo!"}

@app.get("/data")
def get_data():
    return {
        "materias_primas": list(materias_primas.columns),
        "nutrientes": [i for i in materias_primas.index if i != CUSTO_ROW_NAME],
    }

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
