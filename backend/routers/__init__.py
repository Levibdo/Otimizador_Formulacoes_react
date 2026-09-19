from routers.materias_primas import router as materias_primas_router
from routers.projetos import router as projetos_router
from routers.apresentacoes import router as apresentacoes_router
from routers.cenarios import router as cenarios_router
from routers.regulatorio import router as regulatorio_router

__all__ = [
    "apresentacoes_router",
    "cenarios_router",
    "materias_primas_router",
    "projetos_router",
    "regulatorio_router",
]
