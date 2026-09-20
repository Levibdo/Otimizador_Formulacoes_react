from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from models import (
    ComponenteRegulatorio, ComposicaoComponenteMP, ComposicaoMateriaPrima,
    ExecucaoOtimizacao, MateriaPrima, Nutriente, PrecoMateriaPrima, Projeto,
    RegraRegulatoria,
)
from optimization_engine import otimizar_formula


VERSAO_MOTOR = "regulatorio-1.0"


class OtimizacaoNaoEncontrada(ValueError):
    pass


class OtimizacaoInvalida(ValueError):
    pass


def _numero(valor):
    return None if valor is None else float(valor)


class OtimizacaoService:
    def __init__(self, db):
        self.db = db

    def obter(self, execucao_id):
        execucao = self.db.get(ExecucaoOtimizacao, execucao_id)
        if execucao is None:
            raise OtimizacaoNaoEncontrada("Execução de otimização não encontrada.")
        return execucao

    def _persistir(self, projeto, status, contexto, requisitos, regras, limites,
                   alertas, pendencias, resultado, precos):
        item = ExecucaoOtimizacao(
            projeto_id=projeto.id, status=status, versao_motor=VERSAO_MOTOR,
            entradas_contexto=contexto, requisitos_usados=requisitos,
            regras_regulatorias_usadas=regras, limites_efetivos=limites,
            alertas=alertas, pendencias=pendencias,
            resultado_diagnostico=resultado, referencia_precos=precos,
        )
        self.db.add(item)
        self.db.flush()
        return item

    def executar(self, projeto_id, dados):
        hoje = dados.data_referencia or date.today()
        projeto = self.db.get(Projeto, projeto_id)
        if projeto is None:
            raise OtimizacaoNaoEncontrada("Projeto não encontrado.")

        query = select(MateriaPrima).options(
            selectinload(MateriaPrima.precos),
            selectinload(MateriaPrima.composicao).selectinload(ComposicaoMateriaPrima.nutriente),
        )
        if dados.materias_primas_ids is not None:
            query = query.where(MateriaPrima.id.in_(dados.materias_primas_ids))
        candidatas = list(self.db.scalars(query.order_by(MateriaPrima.id)).all())
        solicitadas = set(dados.materias_primas_ids or [])
        encontradas = {mp.id for mp in candidatas}
        inexistentes = sorted(solicitadas - encontradas)
        if inexistentes:
            raise OtimizacaoInvalida(f"Matérias-primas inexistentes: {inexistentes}.")

        precos = {}
        aptas = []
        indisponiveis_solicitadas = []
        for mp in candidatas:
            if not mp.ativa:
                if mp.id in solicitadas:
                    indisponiveis_solicitadas.append(f"Matéria-prima candidata {mp.codigo} está inativa.")
                continue
            vigentes = [p for p in mp.precos if p.vigencia_inicio <= hoje and (p.vigencia_fim is None or p.vigencia_fim >= hoje)]
            if vigentes:
                preco = max(vigentes, key=lambda p: (p.vigencia_inicio, p.id))
                precos[mp.id] = preco
                aptas.append(mp)
            elif mp.id in solicitadas:
                indisponiveis_solicitadas.append(f"Matéria-prima candidata {mp.codigo} não possui preço vigente.")
        if not aptas:
            raise OtimizacaoInvalida("Nenhuma matéria-prima ativa possui preço vigente.")

        regras = []
        if projeto.categoria_produto_id is not None:
            regras = list(self.db.scalars(select(RegraRegulatoria).where(
                RegraRegulatoria.categoria_id == projeto.categoria_produto_id,
                RegraRegulatoria.ativa.is_(True),
                or_(RegraRegulatoria.vigencia_inicio.is_(None), RegraRegulatoria.vigencia_inicio <= hoje),
                or_(RegraRegulatoria.vigencia_fim.is_(None), RegraRegulatoria.vigencia_fim >= hoje),
            ).order_by(RegraRegulatoria.id)).all())

        por_id = {mp.id: mp for mp in aptas}
        limites = {mp.id: {"minimo": 0.0, "maximo": 100.0, "fontes": []} for mp in aptas}
        alertas, pendencias, erros = [], [], list(indisponiveis_solicitadas)

        for limite in dados.limites_tecnicos:
            if limite.materia_prima_id not in por_id:
                erros.append(f"Limite técnico referencia MP inativa, inexistente ou sem preço: {limite.materia_prima_id}.")
                continue
            alvo = limites[limite.materia_prima_id]
            if limite.minimo is not None:
                alvo["minimo"] = max(alvo["minimo"], float(limite.minimo))
            if limite.maximo is not None:
                alvo["maximo"] = min(alvo["maximo"], float(limite.maximo))
            alvo["fontes"].append("LIMITE_TECNICO_CLIENTE")

        regras_mp = {r.materia_prima_id: r for r in regras if r.tipo_alvo == "MATERIA_PRIMA"}
        for regra in regras_mp.values():
            if regra.materia_prima_id not in por_id:
                if regra.tratamento == "OBRIGATORIA":
                    erros.append(f"MP obrigatória {regra.materia_prima_id} está inativa, fora das candidatas ou sem preço vigente.")
                continue
            alvo = limites[regra.materia_prima_id]
            minimo, maximo = _numero(regra.minimo), _numero(regra.maximo)
            if regra.tratamento == "PROIBIDA":
                maximo = 0.0
            if minimo is not None:
                alvo["minimo"] = max(alvo["minimo"], minimo)
            if maximo is not None:
                alvo["maximo"] = min(alvo["maximo"], maximo)
            alvo["fontes"].append(f"REGRA:{regra.id}")
        for mp in aptas:
            if mp.id not in regras_mp and projeto.categoria_produto_id is not None:
                alertas.append(f"Matéria-prima {mp.codigo} sem classificação regulatória individual.")

        metas, custo_max = {}, None
        nutrientes = list(self.db.scalars(select(Nutriente)).all())
        nutrientes_por_chave = {n.codigo.casefold(): n for n in nutrientes} | {n.nome.casefold(): n for n in nutrientes}
        mps_por_chave = {mp.codigo.casefold(): mp for mp in aptas} | {mp.nome.casefold(): mp for mp in aptas}
        requisitos_snapshot = list(projeto.requisitos)
        for req in requisitos_snapshot:
            tipo, chave = req["tipo_item"], str(req["item"]).casefold()
            if tipo == "NUTRIENTE":
                nutriente = nutrientes_por_chave.get(chave)
                if nutriente is None:
                    erros.append(f"Requisito referencia nutriente inexistente: {req['item']}.")
                elif req.get("unidade") and req["unidade"] != nutriente.unidade:
                    erros.append(f"Unidade incompatível para {req['item']}: esperado {nutriente.unidade}.")
                else:
                    minimo_atual, maximo_atual = metas.get(nutriente.nome, (None, None))
                    novo_minimo, novo_maximo = _numero(req.get("minimo")), _numero(req.get("maximo"))
                    metas[nutriente.nome] = (
                        novo_minimo if minimo_atual is None else minimo_atual if novo_minimo is None else max(minimo_atual, novo_minimo),
                        novo_maximo if maximo_atual is None else maximo_atual if novo_maximo is None else min(maximo_atual, novo_maximo),
                    )
            elif tipo in ("MP", "MATERIA_PRIMA"):
                mp = mps_por_chave.get(chave)
                if mp is None:
                    erros.append(f"Requisito referencia matéria-prima inexistente ou indisponível: {req['item']}.")
                elif req.get("unidade") not in (None, "%"):
                    erros.append(f"Unidade incompatível para inclusão de {req['item']}; use %.")
                else:
                    alvo = limites[mp.id]
                    if req.get("minimo") is not None:
                        alvo["minimo"] = max(alvo["minimo"], float(req["minimo"]))
                    if req.get("maximo") is not None:
                        alvo["maximo"] = min(alvo["maximo"], float(req["maximo"]))
                    alvo["fontes"].append("REQUISITO_PROJETO")
            elif tipo == "CUSTO":
                if chave not in ("custo", "custo total"):
                    erros.append(f"Requisito referencia item de custo inexistente: {req['item']}.")
                if req.get("unidade") not in (None, "R$/kg"):
                    erros.append("Unidade incompatível para custo; use R$/kg.")
                if req.get("minimo") is not None:
                    erros.append("Mínimo de custo não é suportado.")
                if req.get("maximo") is not None:
                    novo_teto = float(req["maximo"])
                    custo_max = novo_teto if custo_max is None else min(custo_max, novo_teto)
            else:
                erros.append(f"Tipo de requisito não suportado: {tipo}.")

        for nome, (minimo, maximo) in metas.items():
            if minimo is not None and maximo is not None and minimo > maximo:
                erros.append(f"Mínimo efetivo supera máximo para nutriente {nome}.")

        for mp_id, intervalo in limites.items():
            if intervalo["minimo"] > intervalo["maximo"]:
                erros.append(f"Mínimo efetivo supera máximo para MP {por_id[mp_id].codigo}.")
        if sum(v["minimo"] for v in limites.values()) > 100:
            erros.append("A soma dos mínimos efetivos supera 100%.")
        if sum(v["maximo"] for v in limites.values()) < 100:
            erros.append("A soma dos máximos efetivos é inferior a 100%.")

        agregadas, componentes_snapshot = {}, []
        for regra in (r for r in regras if r.tipo_alvo == "COMPONENTE"):
            componente = self.db.get(ComponenteRegulatorio, regra.componente_id)
            if componente is None or not componente.ativo:
                erros.append(f"Regra {regra.id} referencia componente inexistente ou inativo.")
                continue
            if regra.unidade != "%" or regra.base != "MASSA_MASSA":
                erros.append(f"Unidade/base incompatível na regra {regra.id}.")
                continue
            coeficientes = {}
            for mp in aptas:
                composicoes = list(self.db.scalars(select(ComposicaoComponenteMP).where(
                    ComposicaoComponenteMP.materia_prima_id == mp.id,
                    ComposicaoComponenteMP.componente_id == componente.id,
                    ComposicaoComponenteMP.ativo.is_(True),
                    ComposicaoComponenteMP.data_referencia <= hoje,
                ).order_by(ComposicaoComponenteMP.data_referencia.desc(), ComposicaoComponenteMP.id.desc())).all())
                composicao = composicoes[0] if composicoes else None
                if composicao is None or composicao.situacao == "DESCONHECIDO":
                    pendencias.append(f"Concentração de {componente.codigo} desconhecida para {mp.codigo}.")
                else:
                    coeficientes[mp.nome] = float(composicao.concentracao)
                    componentes_snapshot.append({"componente_id": componente.id, "codigo": componente.codigo, "nome": componente.nome, "materia_prima_id": mp.id, "materia_prima_codigo": mp.codigo, "situacao": composicao.situacao, "concentracao": float(composicao.concentracao), "data_referencia": composicao.data_referencia.isoformat()})
            agregadas[componente.codigo] = (coeficientes, _numero(regra.minimo), _numero(regra.maximo))

        matriz_dict = {}
        for mp in aptas:
            linha = {"Custo": float(precos[mp.id].preco_kg)}
            linha.update({c.nutriente.nome: float(c.valor) for c in mp.composicao})
            matriz_dict[mp.nome] = linha
        regras_snapshot = [{"id": r.id, "revisao": r.revisao, "tipo_alvo": r.tipo_alvo, "tratamento": r.tratamento, "materia_prima_id": r.materia_prima_id, "componente_id": r.componente_id, "minimo": _numero(r.minimo), "maximo": _numero(r.maximo), "unidade": r.unidade, "base": r.base} for r in regras]
        limites_snapshot = {por_id[i].codigo: v for i, v in limites.items()}
        contexto = {"data_referencia": hoje.isoformat(), "categoria_produto_id": projeto.categoria_produto_id, "materias_primas": [{"id": mp.id, "codigo": mp.codigo, "nome": mp.nome, "preco": float(precos[mp.id].preco_kg), "composicao": matriz_dict[mp.nome]} for mp in aptas], "componentes": componentes_snapshot, "escolhas_cliente": dados.model_dump(mode="json")}
        precos_snapshot = {por_id[i].codigo: {"preco_id": p.id, "preco_kg": float(p.preco_kg), "vigencia_inicio": p.vigencia_inicio.isoformat(), "vigencia_fim": p.vigencia_fim.isoformat() if p.vigencia_fim else None} for i, p in precos.items() if i in por_id}

        if erros or pendencias:
            status = "INCONCLUSIVA" if pendencias else "INVIAVEL"
            diagnostico = {"status_solver": None, "erros": erros, "resultado": {}}
        else:
            matriz = pd.DataFrame(matriz_dict)
            try:
                resultado_solver = otimizar_formula(
                    matriz,
                    {por_id[i].nome: (v["minimo"], v["maximo"]) for i, v in limites.items()},
                    metas, custo_max, agregadas,
                )
            except Exception:
                status = "ERRO_TECNICO"
                diagnostico = {
                    "status_solver": None,
                    "erros": ["Falha técnica ao executar o solver."],
                    "resultado": {},
                }
                execucao = self._persistir(
                    projeto, status, contexto, requisitos_snapshot, regras_snapshot,
                    limites_snapshot, alertas, pendencias, diagnostico, precos_snapshot,
                )
                return execucao
            if resultado_solver["status"] != "Optimal":
                status = "INVIAVEL"
                diagnostico = {"status_solver": resultado_solver["status"], "erros": ["O modelo matemático é inviável; não há causa específica comprovada além das restrições registradas."], "resultado": resultado_solver}
            else:
                inclusoes_brutas = resultado_solver["resultado_bruto"]["inclusoes"]
                componentes_resultado = {codigo: sum(coefs.get(mp, 0) * inclusoes_brutas[mp] / 100 for mp in inclusoes_brutas) for codigo, (coefs, _, _) in agregadas.items()}
                resultado_solver["componentes_regulatorios"] = componentes_resultado
                resultado_solver["resultado_bruto"]["componentes_regulatorios"] = componentes_resultado
                status = "SEM_AVALIACAO_REGULATORIA" if projeto.categoria_produto_id is None else ("ATENDE_COM_ALERTAS" if alertas else "ATENDE")
                diagnostico = {"status_solver": resultado_solver["status"], "erros": [], "resultado": resultado_solver}

        execucao = self._persistir(projeto, status, contexto, requisitos_snapshot, regras_snapshot, limites_snapshot, alertas, pendencias, diagnostico, precos_snapshot)
        return execucao
