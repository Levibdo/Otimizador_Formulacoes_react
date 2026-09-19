from sqlalchemy import select


class RegulatorioRepository:
    def __init__(self, db):
        self.db = db

    def obter(self, model, identificador, bloquear=False):
        query = select(model).where(model.id == identificador).execution_options(populate_existing=True)
        if bloquear:
            query = query.with_for_update()
        return self.db.scalar(query)

    def listar(self, model, **filtros):
        query = select(model).order_by(model.id)
        for campo, valor in filtros.items():
            if valor is not None:
                query = query.where(getattr(model, campo) == valor)
        return list(self.db.scalars(query).all())

    def criar(self, model, **campos):
        item = model(**campos)
        self.db.add(item)
        self.db.flush()
        self.db.refresh(item)
        return item

    def atualizar(self, item, campos):
        for campo, valor in campos.items():
            setattr(item, campo, valor)
        self.db.flush()
        self.db.refresh(item)
        return item
