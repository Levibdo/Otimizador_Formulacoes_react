# Base regulatória híbrida para fórmulas enterais

## Escopo deste bloco

A revisão `20260919_06` cria a base cadastral do MVP regulatório híbrido. O modelo
suporta regras manuais sobre matérias-primas comerciais e sobre componentes que
podem estar presentes em várias matérias-primas. A categoria piloto é criada pela
própria migração, de forma reproduzível:

- código estável: `FORMULA_ENTERAL_PO`;
- nome: **Fórmula enteral em pó**.

Este bloco não aplica regras ao solver, não persiste execuções regulatórias e não
cria snapshots regulatórios. Também não interpreta textos normativos e não produz
alegação ou certificação automática de conformidade.

## Matéria-prima comercial e componente agregado

Uma regra de `MATERIA_PRIMA` limita diretamente o percentual de inclusão daquela
MP comercial na fórmula. Uma regra de `COMPONENTE` descreve um alvo agregado: sua
quantidade futura deverá considerar a soma das contribuições de todas as MPs que
o contêm. Ambas usam inicialmente percentual em massa da fórmula (`% m/m`).

As concentrações dos componentes nas MPs também são cadastradas em `% m/m` e
guardam data de referência. Cada registro possui uma situação explícita:

| Situação | Concentração | Significado |
| --- | --- | --- |
| `INFORMADO` | entre 0 e 100 | valor declarado e conhecido |
| `AUSENTE_CONFIRMADO` | exatamente 0 | ausência confirmada por uma fonte |
| `DESCONHECIDO` | nula | não há valor confiável; nunca equivale a zero |

Uma nova informação para a mesma MP e componente usa outra data de referência.
O conteúdo histórico não pode ser sobrescrito; pode ser desativado.

## Política cadastral

MPs sem regra individual podem participar pela política do MVP. O endpoint de
diagnóstico cadastral emite um alerta para cada MP ativa sem regra, deixando claro
que a participação permitida não representa conformidade normativa.

Quando existe regra ativa para um componente, o diagnóstico também aponta cada MP
ativa sem composição conhecida na data consultada. Ausência de registro e situação
`DESCONHECIDO` são alertas distintos. `AUSENTE_CONFIRMADO` com concentração zero
resolve o alerta para aquela data; o sistema não presume zero quando o dado falta.

O diagnóstico é somente cadastral e retorna o escopo
`CADASTRAL_SEM_AVALIACAO_DE_CONFORMIDADE`. Nenhuma regra é enviada ao otimizador.

## Integridade, vigências e histórico

- códigos de categorias e componentes são únicos, controlados e imutáveis;
- percentuais ficam entre 0 e 100, com mínimo menor ou igual ao máximo;
- `OBRIGATORIA` exige mínimo maior que zero;
- `PROIBIDA` é persistida com máximo zero e sem mínimo positivo;
- cada regra possui exatamente um alvo: MP ou componente;
- regras ativas do mesmo alvo e categoria não podem ter vigências sobrepostas;
- períodos sem início ou fim são tratados como ilimitados naquele lado;
- regras publicadas são desativadas ou recebem uma revisão sucessora;
- composições históricas recebem nova data de referência em vez de edição;
- categorias e componentes podem mudar nome, descrição e situação, mas não código;
- exclusão física dos quatro cadastros regulatórios é rejeitada por trigger;
- projetos anteriores continuam válidos com categoria nula;
- categorias inativas continuam legíveis por projetos existentes, mas não podem ser
  associadas a projetos novos nem receber novas regras.

As constraints de exclusão GiST protegem contra conflito de regras inclusive em
requisições concorrentes e SQL direto. A API também valida os conflitos para emitir
mensagens específicas antes do erro de banco.

## Endpoints

| Método e caminho | Uso |
| --- | --- |
| `GET/POST /api/v1/categorias-produto` | listar e cadastrar categorias |
| `GET/PATCH /api/v1/categorias-produto/{id}` | consultar, revisar dados ou desativar |
| `GET /api/v1/categorias-produto/{id}/diagnostico-cadastral` | alertas de classificação e concentração |
| `GET/POST /api/v1/componentes-regulatorios` | listar e cadastrar componentes |
| `GET/PATCH /api/v1/componentes-regulatorios/{id}` | consultar, revisar dados ou desativar |
| `GET/POST /api/v1/materias-primas/{id}/componentes-regulatorios` | histórico de composição da MP |
| `GET/PATCH /api/v1/composicoes-componentes-mp/{id}` | consultar ou ativar/desativar composição |
| `GET/POST /api/v1/regras-regulatorias` | listar, filtrar e cadastrar regras |
| `GET/PATCH /api/v1/regras-regulatorias/{id}` | consultar ou ativar/desativar regra |
| `POST /api/v1/regras-regulatorias/{id}/revisoes` | criar revisão sucessora |
| `POST/PATCH /api/v1/projetos` | aceita `categoria_produto_id` opcional |

Não existem endpoints `DELETE` para esses cadastros.

## Próximos passos

O próximo bloco deverá selecionar o projeto antes do cálculo, carregar as regras
vigentes no servidor e validar a completude das concentrações. Regras de MP serão
traduzidas em limites diretos de inclusão. Regras de componente deverão produzir
uma expressão agregada sobre todas as MPs. Somente depois disso devem ser criados
execuções persistidas e snapshots regulatórios imutáveis.

Até essa integração existir, a interface React permanece inalterada e a API não
deve apresentar os cadastros como avaliação normativa.
