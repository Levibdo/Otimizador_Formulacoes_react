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
        c for c in unicodedata.normalize("NFD", str(nome))
        if unicodedata.category(c) != 'Mn'
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
# /data → Retorna MPs e nutrientes (Mongo ou local)
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
# CRUD de Matérias-Primas (MongoDB)
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
# /importar_materias_primas → Importar CSV/XLSX para MongoDB
# - Suporta planilha transposta (como a sua imagem) e formato vertical
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

        # lê sem header para inspecionar conteúdo
        if file.filename.lower().endswith(".xlsx") or file.filename.lower().endswith(".xls"):
            df_raw = pd.read_excel(io.BytesIO(content), header=None)
        elif file.filename.lower().endswith(".csv"):
            # tenta UTF-8 primeiro, cai para latin1 se der problema
            try:
                df_raw = pd.read_csv(io.BytesIO(content), header=None, encoding="utf-8")
            except Exception:
                df_raw = pd.read_csv(io.BytesIO(content), header=None, encoding="latin1")
        else:
            raise HTTPException(status_code=400, detail="Formato não suportado. Use .xlsx ou .csv")

        # Normaliza strings das primeiras células para decisão
        first_cell = ""
        try:
            first_cell = str(df_raw.iat[0, 0]).strip().lower()
        except Exception:
            first_cell = ""

        # Heurística: se a célula (0,0) estiver vazia ou não for 'nome' e a célula (1,0) contém 'custo',
        # assumimos estrutura transposta conforme sua imagem:
        # linha0: [blank, MP1, MP2, ...]
        # linha1: [Custo,  cost1, cost2, ...]
        # linha2+: [Nutriente, val_mp1, val_mp2, ...]
        transposto = False
        try:
            second_cell_first_col = str(df_raw.iat[1, 0]).strip().lower()
            if ("custo" in second_cell_first_col) or (first_cell == "" and df_raw.shape[1] > 1 and df_raw.shape[0] >= 2):
                # We'll do a more precise check below, but mark as possible transposed
                transposto = True
        except Exception:
            transposto = False

        materias_primas_docs = []

        if transposto:
            # Tratamento específico para o formato transposto mostrado
            # nomes das MPs: primeira linha, colunas a partir de 1
            col_names = df_raw.iloc[0, 1:].astype(str).tolist()

            # custos: segunda linha, colunas a partir de 1
            custos = df_raw.iloc[1, 1:].tolist()

            # nutrientes: a partir da linha 3
            dados = df_raw.iloc[2:, :].copy()
            # define cabeçalho: primeira coluna -> 'Nutriente', resto -> nomes das MPs
            header = ["Nutriente"] + col_names
            dados.columns = header
            dados = dados.reset_index(drop=True)

            # transforma coluna "Nutriente" em índice para fácil lookup
            nutr_df = dados.set_index("Nutriente")

            # monta documentos por MP
            for i, mp in enumerate(col_names):
                try:
                    custo_val = float(custos[i]) if pd.notna(custos[i]) else 0.0
                except Exception:
                    custo_val = 0.0

                # pega série de valores nutricionais daquela coluna (pode ter NaN)
                nutric_dict = {}
                if mp in nutr_df.columns:
                    serie = nutr_df[mp]
                    # convert to numeric where possible
                    serie = pd.to_numeric(serie, errors="coerce")
                    nutric_dict = {str(k): (float(v) if pd.notna(v) else 0.0) for k, v in serie.to_dict().items()}
                else:
                    # se nome da coluna tem algum caracter estranho, tenta buscar com aproximação
                    # (fall back: tentar col index)
                    col_index = i + 1
                    if col_index < df_raw.shape[1]:
                        serie = dados.iloc[:, col_index]
                        serie.index = dados["Nutriente"]
                        serie = pd.to_numeric(serie, errors="coerce")
                        nutric_dict = {str(k): (float(v) if pd.notna(v) else 0.0) for k, v in serie.to_dict().items()}

                doc = {
                    "usuario_id": usuario_id,
                    "nome": mp,
                    "Custo": custo_val,
                }
                # junta nutrientes como campos separados (mantive chave separada)
                # Se preferir, pode usar "nutrientes": nutric_dict
                # Aqui vou inserir todos os nutrientes como campos (compatível com o resto do app)
                for nutr_name, nutr_val in nutric_dict.items():
                    doc[str(nutr_name)] = nutr_val

                materias_primas_docs.append(doc)

        else:
            # Formato vertical / normal: assumimos que há header na primeira linha com col 'nome' e 'Custo'
            # Ler novamente com header=0 (primeira linha como colunas)
            try:
                if file.filename.lower().endswith(".csv"):
                    try:
                        df = pd.read_csv(io.BytesIO(content), header=0, encoding="utf-8")
                    except Exception:
                        df = pd.read_csv(io.BytesIO(content), header=0, encoding="latin1")
                else:
                    df = pd.read_excel(io.BytesIO(content), header=0)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Não foi possível ler o arquivo: {e}")

            # normalizar nomes de colunas
            df.columns = [str(c).strip() for c in df.columns]

            # Algumas planilhas podem usar 'nome' ou 'Matéria-Prima' etc; tentamos detectar coluna com nomes
            name_col = None
            for possible in ["nome", "Nome", "MATÉRIA-PRIMA", "Matéria-Prima", "Matéria prima", "matéria-prima"]:
                if possible in df.columns:
                    name_col = possible
                    break
            # fallback: primeira coluna
            if name_col is None:
                name_col = df.columns[0]

            # garantir que existe coluna Custo (pode estar com variações)
            custo_col = None
            for possible in ["Custo", "custo", "Cost", "Preço"]:
                if possible in df.columns:
                    custo_col = possible
                    break

            # monta docs direto dos registros
            for _, row in df.iterrows():
                nome_mp = str(row[name_col])
                try:
                    custo_val = float(row[custo_col]) if custo_col and pd.notna(row[custo_col]) else 0.0
                except Exception:
                    custo_val = 0.0

                doc = {"usuario_id": usuario_id, "nome": nome_mp, "Custo": custo_val}
                # adiciona demais colunas (nutrientes)
                for col in df.columns:
                    if col == name_col or col == custo_col:
                        continue
                    val = row[col]
                    try:
                        doc[str(col)] = float(val) if pd.notna(val) else 0.0
                    except Exception:
                        doc[str(col)] = val
                materias_primas_docs.append(doc)

        # Se não encontrou nada válido
        if not materias_primas_docs:
            raise HTTPException(status_code=400, detail="A planilha não contém dados válidos para importação.")

        # Insere no MongoDB: limpamos registros antigos do mesmo usuário antes (comportamento opcional)
        try:
            mp_collection.delete_many({"usuario_id": usuario_id})
            mp_collection.insert_many(materias_primas_docs)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao salvar no MongoDB: {e}")

        return {"mensagem": f"{len(materias_primas_docs)} registros importados com sucesso!"}

    except HTTPException:
        raise
    except Exception as e:
        # Retorna mensagem mais descritiva ao frontend
        raise HTTPException(status_code=500, detail=f"Erro ao processar planilha: {str(e)}")


# --------------------------------------------------------------
# /exportar_materias_primas → Exportar dados do usuário
# --------------------------------------------------------------
@app.get("/exportar_materias_primas")
async def exportar_materias_primas(usuario_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="MongoDB não configurado.")

    try:
        # Busca as MPs do usuário (sem o _id)
        mps = list(mp_collection.find({"usuario_id": usuario_id}, {"_id": 0}))
        if not mps:
            raise HTTPException(status_code=404, detail="Nenhuma matéria-prima encontrada para este usuário.")

        # Converte para DataFrame
        df = pd.DataFrame(mps)

        # Reordenar colunas para colocar 'nome' e 'usuario_id' no início (opcional)
        cols = df.columns.tolist()
        ordered = []
        for c in ["nome", "usuario_id", "Custo"]:
            if c in cols:
                ordered.append(c)
        for c in cols:
            if c not in ordered:
                ordered.append(c)
        df = df[ordered]

        # Converte em Excel (BytesIO)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="MateriasPrimas")
        output.seek(0)

        headers = {
            "Content-Disposition": f"attachment; filename=materias_primas_{usuario_id}.xlsx"
        }

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------
# /optimize → Otimização de fórmula
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
# /consulta → Avalia fórmula existente
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
