from fastapi import FastAPI, Request, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
from optimization_engine import otimizar_formula, CUSTO_ROW_NAME 
import sys
import unicodedata
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import os
import io
from fastapi.responses import StreamingResponse

sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================
# CONFIGURAÇÕES INICIAIS
# ==============================================================

load_dotenv()
app = FastAPI(title="Otimizador de Formulações API com MongoDB")

# ==============================================================
# CORS
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
# CONEXÃO COM MONGODB ATLAS
# ==============================================================

MONGO_URI = os.getenv("MONGO_URI")
db = None
mp_collection = None

if MONGO_URI:
    try:
        client = MongoClient(MONGO_URI)
        client.admin.command("ping")
        db = client["otimizador_db"]
        mp_collection = db["materias_primas"]
        print("✅ Conectado ao MongoDB Atlas com sucesso!")
    except Exception as e:
        print("❌ Erro ao conectar ao MongoDB:", e)
else:
    print("⚠️ Nenhuma variável MONGO_URI definida. Usando base local Excel.")

# ==============================================================
# FUNÇÃO DE NORMALIZAÇÃO
# ==============================================================

def normalizar_nome(nome):
    nome = ''.join(
        c for c in unicodedata.normalize("NFD", nome)
        if unicodedata.category(c) != "Mn"
    )
    return nome.strip().lower().replace("_", " ")

# ==============================================================
# BASE LOCAL (caso MongoDB indisponível)
# ==============================================================

materias_primas_local = pd.read_excel("data/MPs_data.xlsx", index_col=0)
materias_primas_local.columns = materias_primas_local.columns.str.strip()
materias_primas_local.index = materias_primas_local.index.str.strip()

# ==============================================================
# ENDPOINTS
# ==============================================================

@app.get("/")
def root():
    return {"message": "API do Otimizador de Formulações rodando com sucesso!"}


# --------------------------------------------------------------
# 🔹 /data → Retorna MPs e nutrientes (Mongo ou local)
# --------------------------------------------------------------
@app.get("/data")
def get_data(usuario_id: str = None):
    try:
        if db is not None and usuario_id:
            mps = list(mp_collection.find({"usuario_id": usuario_id}))
            if not mps:
                raise ValueError("Nenhuma MP encontrada no banco do usuário.")

            df = pd.DataFrame(mps).set_index("nome")
            matriz_dict = df.to_dict()
            materias = list(df.index)
            nutrientes = [c for c in df.columns if c not in ["_id", "usuario_id", "nome"]]

            return {
                "materias_primas": materias,
                "nutrientes": nutrientes,
                "matriz": matriz_dict,
            }

        # fallback
        return {
            "materias_primas": list(materias_primas_local.columns),
            "nutrientes": [i for i in materias_primas_local.index if i != CUSTO_ROW_NAME],
            "matriz": materias_primas_local.to_dict(),
        }

    except Exception as e:
        print("❌ Erro ao carregar dados:", e)
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------
# 🔹 CRUD de Matérias-Primas (MongoDB)
# --------------------------------------------------------------
@app.post("/mp")
async def adicionar_mp(request: Request):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")
    try:
        body = await request.json()
        result = mp_collection.insert_one(body)
        return {"id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/mp/{usuario_id}")
def listar_mps(usuario_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")
    mps = list(mp_collection.find({"usuario_id": usuario_id}))
    for m in mps:
        m["_id"] = str(m["_id"])
    return mps


@app.delete("/mp/{mp_id}")
def deletar_mp(mp_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")
    result = mp_collection.delete_one({"_id": ObjectId(mp_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="MP não encontrada.")
    return {"status": "ok"}


# --------------------------------------------------------------
# 🔹 /importar_materias_primas → Importar CSV/XLSX para MongoDB
# --------------------------------------------------------------
@app.post("/importar_materias_primas")
async def importar_materias_primas(
    usuario_id: str = Form(...),
    file: UploadFile = File(...)
):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")

    try:
        content = await file.read()

        # Detectar formato do arquivo
        if file.filename.endswith(".xlsx"):
            df_raw = pd.read_excel(io.BytesIO(content), header=None)
        elif file.filename.endswith(".csv"):
            df_raw = pd.read_csv(io.BytesIO(content), header=None)
        else:
            raise HTTPException(status_code=400, detail="Formato não suportado. Use .xlsx ou .csv")

        # Detectar automaticamente se a primeira linha contém MPs
        # (isto é, a primeira célula A1 é 'Custo' ou algo semelhante)
        primeira_celula = str(df_raw.iat[0, 0]).strip().lower()
        if "custo" in primeira_celula:
            # formato correto já verticalizado
            df = df_raw
        else:
            # formato transposto: nutrientes nas linhas
            df = df_raw.T

        # Renomear colunas
        df.columns = df.iloc[0]  # primeira linha vira cabeçalho
        df = df.drop(0)

        # A primeira coluna deve conter o nome das MPs
        df.rename(columns={df.columns[0]: "nome"}, inplace=True)

        # Converter valores numéricos
        for col in df.columns:
            if col != "nome":
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Adicionar usuário
        df["usuario_id"] = usuario_id

        # Inserir no MongoDB
        mp_collection.insert_many(df.to_dict(orient="records"))

        return {"mensagem": f"{len(df)} registros importados com sucesso!"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar planilha: {str(e)}")
# --------------------------------------------------------------
# 🔹 /exportar_materias_primas → Exportar dados do usuário
# --------------------------------------------------------------
@app.get("/exportar_materias_primas")
async def exportar_materias_primas(usuario_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")

    try:
        # Busca as MPs do usuário
        mps = list(mp_collection.find({"usuario_id": usuario_id}, {"_id": 0}))
        if not mps:
            raise HTTPException(status_code=404, detail="Nenhuma matéria-prima encontrada para este usuário.")

        # Converte para DataFrame
        df = pd.DataFrame(mps)

        # Converte em Excel (BytesIO)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="MateriasPrimas")

        output.seek(0)

        # Retorna como arquivo para download
        headers = {
            "Content-Disposition": f"attachment; filename=materias_primas_{usuario_id}.xlsx"
        }

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# --------------------------------------------------------------
# 🔹 /optimize → Otimização de fórmula
# --------------------------------------------------------------
@app.post("/optimize")
async def optimize(request: Request):
    try:
        body = await request.json()
        metas = body.get("metas", {})
        restricoes = body.get("restricoes", {})
        matriz_dict = body.get("matriz", None)

        if matriz_dict:
            mp_df = pd.DataFrame(matriz_dict).T
        else:
            mp_df = materias_primas_local

        mp_df = mp_df.apply(pd.to_numeric, errors="ignore").fillna(0)
        resultado = otimizar_formula(mp_df, restricoes=restricoes, metas=metas)
        return resultado

    except Exception as e:
        print("❌ ERRO NO BACKEND:", e)
        return {"erro": str(e)}


# --------------------------------------------------------------
# 🔹 /consulta → Avalia fórmula existente
# --------------------------------------------------------------
@app.post("/consulta")
async def consultar(request: Request):
    try:
        body = await request.json()
        formulacao = body.get("formulacao", body)

        colunas_norm = {normalizar_nome(c): c for c in materias_primas_local.columns}
        proporcoes_validas = {}

        for mp, valor in formulacao.items():
            try:
                valor_float = float(valor)
                if valor_float > 0:
                    nome_norm = normalizar_nome(mp)
                    if nome_norm in colunas_norm:
                        proporcoes_validas[colunas_norm[nome_norm]] = valor_float
            except Exception:
                continue

        if not proporcoes_validas:
            raise ValueError("Nenhuma MP válida foi informada.")

        proporcoes = pd.Series(proporcoes_validas, dtype=float)
        proporcoes = proporcoes / proporcoes.sum()

        matriz_filtrada = materias_primas_local[proporcoes.index]
        matriz_sem_custo = matriz_filtrada.drop(index=CUSTO_ROW_NAME, errors="ignore")

        nutrientes = matriz_sem_custo.dot(proporcoes)
        custo_por_mp = matriz_filtrada.loc[CUSTO_ROW_NAME] * proporcoes
        custo_total = custo_por_mp.sum()

        return {
            "status": "OK",
            "nutrientes": [{"Nutriente": n, "Valor Obtido": v} for n, v in nutrientes.items()],
            "custos": [{"Matéria-Prima": mp, "Custo": custo} for mp, custo in custo_por_mp.items()],
            "custo_total": custo_total,
        }

    except Exception as e:
        print("❌ ERRO NA CONSULTA:", e)
        return {"erro": str(e)}
