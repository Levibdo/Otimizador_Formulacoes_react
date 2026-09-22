from routers.materias_primas import router as materias_primas_router
from routers.projetos import router as projetos_router
from routers.apresentacoes import router as apresentacoes_router
from routers.cenarios import router as cenarios_router
from routers.regulatorio import router as regulatorio_router
from routers.otimizacoes import router as otimizacoes_router
from routers.importacoes_cadastrais import router as importacoes_cadastrais_router

__all__ = [
    "apresentacoes_router",
    "cenarios_router",
    "materias_primas_router",
    "projetos_router",
    "regulatorio_router",
    "otimizacoes_router",
    "importacoes_cadastrais_router",
]
