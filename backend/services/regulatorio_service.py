from datetime import date

from models import MateriaPrima
from models.regulatorio import CategoriaProduto, ComponenteRegulatorio, ComposicaoComponenteMP, RegraRegulatoria
from repositories.regulatorio_repository import RegulatorioRepository


class CadastroNaoEncontrado(ValueError):
    pass


class ConflitoRegulatorio(ValueError):
    pass


class RegulatorioService:
    def __init__(self, db):
        self.db = db
        self.repo = RegulatorioRepository(db)

    def obter(self, model, identificador, bloquear=False):
        item = self.repo.obter(model, identificador, bloquear)
        if item is None:
            raise CadastroNaoEncontrado(f'{model.__tablename__}: registro não encontrado.')
        return item

    def exigir_ativo(self, model, identificador, campo='ativo', bloquear=False):
        item = self.obter(model, identificador, bloquear)
        if not getattr(item, campo):
            raise ConflitoRegulatorio(f'{model.__tablename__}: registro inativo.')
        return item

    def criar_catalogo(self, model, dados):
        if self.repo.listar(model, codigo=dados.codigo):
            raise ConflitoRegulatorio('Código já cadastrado; use o cadastro existente.')
        return self.repo.criar(model, **dados.model_dump())

    def atualizar_catalogo(self, model, identificador, dados):
        item = self.obter(model, identificador, bloquear=True)
        return self.repo.atualizar(item, dados.model_dump(exclude_unset=True))

    def criar_composicao(self, mp_id, dados):
        self.exigir_ativo(MateriaPrima, mp_id, 'ativa')
        self.exigir_ativo(ComponenteRegulatorio, dados.componente_id)
        if self.repo.listar(ComposicaoComponenteMP, materia_prima_id=mp_id,
                            componente_id=dados.componente_id, data_referencia=dados.data_referencia):
            raise ConflitoRegulatorio('Já existe composição para esta MP, componente e data de referência.')
        return self.repo.criar(ComposicaoComponenteMP, materia_prima_id=mp_id, **dados.model_dump())

    def ativar_composicao(self, identificador, dados):
        item = self.obter(ComposicaoComponenteMP, identificador, bloquear=True)
        if dados.ativo:
            self.exigir_ativo(MateriaPrima, item.materia_prima_id, 'ativa')
            self.exigir_ativo(ComponenteRegulatorio, item.componente_id)
        return self.repo.atualizar(item, dados.model_dump())

    def validar_regra(self, dados, ignorar_id=None):
        self.exigir_ativo(CategoriaProduto, dados.categoria_id, 'ativa', bloquear=True)
        if dados.tipo_alvo == 'MATERIA_PRIMA':
            self.exigir_ativo(MateriaPrima, dados.materia_prima_id, 'ativa')
        else:
            self.exigir_ativo(ComponenteRegulatorio, dados.componente_id)
        existentes = self.repo.listar(RegraRegulatoria, categoria_id=dados.categoria_id, ativa=True,
                                     tipo_alvo=dados.tipo_alvo,
                                     materia_prima_id=dados.materia_prima_id,
                                     componente_id=dados.componente_id)
        inicio, fim = dados.vigencia_inicio or date.min, dados.vigencia_fim or date.max
        for regra in existentes:
            if regra.id != ignorar_id and (regra.vigencia_inicio or date.min) <= fim and inicio <= (regra.vigencia_fim or date.max):
                raise ConflitoRegulatorio('Já existe regra ativa para o mesmo alvo/categoria com vigência sobreposta.')

    def criar_regra(self, dados):
        self.validar_regra(dados)
        return self.repo.criar(RegraRegulatoria, **dados.model_dump())

    def ativar_regra(self, identificador, dados):
        regra = self.obter(RegraRegulatoria, identificador, bloquear=True)
        if dados.ativa:
            if self.repo.listar(RegraRegulatoria, regra_anterior_id=identificador):
                raise ConflitoRegulatorio('Regra substituída por revisão não pode ser reativada.')
            self.validar_regra(regra, ignorar_id=identificador)
        return self.repo.atualizar(regra, dados.model_dump())

    def revisar_regra(self, identificador, dados):
        anterior = self.obter(RegraRegulatoria, identificador, bloquear=True)
        if self.repo.listar(RegraRegulatoria, regra_anterior_id=identificador):
            raise ConflitoRegulatorio('Esta regra já possui revisão sucessora.')
        for campo in ('categoria_id', 'tipo_alvo', 'materia_prima_id', 'componente_id'):
            if getattr(anterior, campo) != getattr(dados, campo):
                raise ConflitoRegulatorio('Uma revisão deve manter a categoria e o alvo originais.')
        self.validar_regra(dados, ignorar_id=identificador)
        self.repo.atualizar(anterior, {'ativa': False})
        return self.repo.criar(RegraRegulatoria, **dados.model_dump(),
                               revisao=anterior.revisao + 1, regra_anterior_id=anterior.id)

    def diagnostico(self, categoria_id, referencia):
        self.obter(CategoriaProduto, categoria_id)
        regras = [r for r in self.repo.listar(RegraRegulatoria, categoria_id=categoria_id, ativa=True)
                  if (r.vigencia_inicio is None or r.vigencia_inicio <= referencia)
                  and (r.vigencia_fim is None or r.vigencia_fim >= referencia)]
        mps = self.repo.listar(MateriaPrima, ativa=True)
        classificados = {r.materia_prima_id for r in regras if r.tipo_alvo == 'MATERIA_PRIMA'}
        componentes = {r.componente_id for r in regras if r.tipo_alvo == 'COMPONENTE'}
        recentes = {}
        for item in self.repo.listar(ComposicaoComponenteMP, ativo=True):
            chave = (item.materia_prima_id, item.componente_id)
            if item.data_referencia <= referencia and (chave not in recentes or item.data_referencia > recentes[chave].data_referencia):
                recentes[chave] = item
        return {
            'categoria_id': categoria_id, 'data_referencia': referencia,
            'escopo': 'CADASTRAL_SEM_AVALIACAO_DE_CONFORMIDADE',
            'mps_sem_regra_individual': [
                {'materia_prima_id': mp.id, 'codigo': mp.codigo,
                 'alerta': 'MP sem regra individual: participação permitida pela política cadastral; não indica conformidade.'}
                for mp in mps if mp.id not in classificados
            ],
            'concentracoes_desconhecidas': [
                {'materia_prima_id': mp.id, 'componente_id': componente,
                 'motivo': 'SEM_REGISTRO' if (mp.id, componente) not in recentes else 'DESCONHECIDO',
                 'alerta': 'Concentração desconhecida não pode ser considerada zero.'}
                for mp in mps for componente in sorted(componentes)
                if (mp.id, componente) not in recentes or recentes[(mp.id, componente)].situacao == 'DESCONHECIDO'
            ],
        }
