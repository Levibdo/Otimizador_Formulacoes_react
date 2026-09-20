from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.session import get_db
from schemas.otimizacao import ExecucaoOtimizacaoRead, OtimizacaoCreate, OtimizacaoResponse
from services.otimizacao_service import OtimizacaoInvalida, OtimizacaoNaoEncontrada, OtimizacaoService

router = APIRouter(prefix="/api/v1", tags=["Otimização server-side"])


def _resposta(item):
    diagnostico = item.resultado_diagnostico
    resultado = diagnostico.get("resultado", {})
    return OtimizacaoResponse(
        execucao_id=item.id,
        status=item.status,
        status_solver=diagnostico.get("status_solver"),
        inclusoes=resultado.get("inclusoes", {}),
        composicao=resultado.get("conferencia_nutricional", {}),
        componentes=resultado.get("componentes_regulatorios", {}),
        custo_total=resultado.get("custo_total"),
        custos_individuais=resultado.get("custos_individuais", {}),
        regras_aplicadas=item.regras_regulatorias_usadas,
        limites_efetivos=item.limites_efetivos,
        alertas=item.alertas,
        pendencias=item.pendencias,
        diagnostico={"erros": diagnostico.get("erros", [])},
    )


@router.post("/projetos/{projeto_id}/otimizacoes", response_model=OtimizacaoResponse, status_code=201)
def executar_otimizacao(projeto_id: int, dados: OtimizacaoCreate, db: Session = Depends(get_db)):
    try:
        item = OtimizacaoService(db).executar(projeto_id, dados)
        db.commit()
        return _resposta(item)
    except OtimizacaoNaoEncontrada as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from exc
    except OtimizacaoInvalida as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Conflito ao persistir a execução de otimização.") from exc


@router.get("/otimizacoes/{execucao_id}", response_model=ExecucaoOtimizacaoRead)
def obter_otimizacao(execucao_id: int, db: Session = Depends(get_db)):
    try:
        return OtimizacaoService(db).obter(execucao_id)
    except OtimizacaoNaoEncontrada as exc:
        raise HTTPException(404, str(exc)) from exc
