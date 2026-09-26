# Contrato da planilha cadastral 1.0

Este contrato cobre apenas a leitura e a validação estrutural de arquivos `.xlsx`.
O parser não consulta nem altera o PostgreSQL, não executa `commit` e não infere
operações. O importador legado de matérias-primas permanece disponível.

## Regras gerais

- versão do contrato: `1.0`;
- exatamente cinco abas: `LEIA_ME`, `MATERIAS_PRIMAS`, `NUTRIENTES`,
  `COMPOSICAO_NUTRICIONAL` e `PRECOS_MP`;
- o conjunto geral de ações é `CRIAR`, `ATUALIZAR` e `DESATIVAR`, limitado por aba conforme a tabela abaixo;
- cada linha de dados deve declarar sua ação;
- códigos são identificadores estáveis, não são gerados e não podem ser alterados;
- códigos começam por letra e contêm somente letras, números e `_`, com até 30 caracteres;
- células vazias em atualizações significam “não alterar” e nunca apagam dados;
- a ausência de uma composição no arquivo não solicita sua remoção;
- preços são novos períodos históricos, portanto `PRECOS_MP` aceita somente `CRIAR`;
- datas textuais usam exclusivamente ISO `AAAA-MM-DD`;
- booleanos aceitam exclusivamente os textos `SIM` e `NÃO`;
- códigos devem ser células de texto, preservam zeros e são normalizados para maiúsculas;
- decimais são normalizados como texto decimal, sem conversão para ponto flutuante pelo parser;
- fórmulas não são aceitas em nenhuma célula.

## Abas e colunas

| Aba | Colunas obrigatórias | Ações seguras | Chave de duplicidade no arquivo |
| --- | --- | --- | --- |
| `LEIA_ME` | `CHAVE`, `VALOR` | Não se aplica | `CHAVE` |
| `MATERIAS_PRIMAS` | `ACAO`, `CODIGO`, `NOME`, `ATIVA` | `CRIAR`, `ATUALIZAR`, `DESATIVAR` | `CODIGO` |
| `NUTRIENTES` | `ACAO`, `CODIGO`, `NOME`, `UNIDADE` | `CRIAR`, `ATUALIZAR` | `CODIGO` |
| `COMPOSICAO_NUTRICIONAL` | `ACAO`, `MATERIA_PRIMA_CODIGO`, `NUTRIENTE_CODIGO`, `VALOR` | `CRIAR`, `ATUALIZAR` | MP + nutriente |
| `PRECOS_MP` | `ACAO`, `MATERIA_PRIMA_CODIGO`, `PRECO_KG`, `VIGENCIA_INICIO`, `VIGENCIA_FIM` | `CRIAR` | MP + vigência inicial |

`LEIA_ME` deve possuir a chave `VERSAO_TEMPLATE` com valor textual `1.0`.
Cabeçalhos repetidos, ausentes ou desconhecidos invalidam a aba.

Em `MATERIAS_PRIMAS` e `NUTRIENTES`, `CRIAR` exige os campos cadastrais e
`ATUALIZAR` exige ao menos um campo mutável preenchido. Somente matérias-primas
aceitam `DESATIVAR`. Nutrientes não possuem estado ativo no schema atual.

Em `COMPOSICAO_NUTRICIONAL`, `CRIAR` e `ATUALIZAR` exigem valor não negativo.
Essa relação não possui estado ativo no schema atual, portanto `DESATIVAR` é
rejeitado. Uma composição que não apareça na planilha permanece inalterada.

Referências declaradas no próprio workbook são verificadas. Uma referência que
não consta nas abas cadastrais produz aviso, pois poderá apontar para um código
já existente no PostgreSQL; essa resolução pertence à futura pré-validação com o banco.

## Diagnósticos

Cada diagnóstico contém:

- `severidade`: `ERRO` ou `AVISO`;
- `aba`;
- `linha`;
- `coluna`;
- `codigo` relacionado;
- `mensagem` segura.

O resultado é válido apenas quando não possui diagnóstico de severidade `ERRO`.

## Limites de segurança

| Limite | Valor |
| --- | ---: |
| Arquivo compactado | 5 MiB |
| Conteúdo descomprimido | 30 MiB |
| Entradas internas no ZIP | 200 |
| Razão de compressão por entrada | 100:1 |
| Abas | 5 |
| Linhas por aba | 5.000 |
| Colunas por aba | 12 |
| Células no workbook | 100.000 |

Arquivos vazios, corrompidos, criptografados, com macros, caminhos internos
inválidos ou estrutura semelhante a ZIP bomb são rejeitados antes da leitura das
células.

## Template fictício

`GET /api/v1/importacoes-cadastrais/template` gera o template em memória. Os
exemplos usam somente códigos e nomes iniciados por `FICT_` ou explicitamente
descritos como fictícios. O download não consulta nem grava dados.

## Pré-validação contra o PostgreSQL

`POST /api/v1/importacoes-cadastrais/validar` recebe o arquivo no campo
multipart `arquivo`, aplica o parser estrutural e compara os códigos com o estado
atual do PostgreSQL. A operação executa somente consultas em lote. Ela não faz
`INSERT`, `UPDATE`, `DELETE`, `flush`, `commit` ou alteração de objetos da sessão.

A resposta contém:

- `versao`: versão encontrada no workbook;
- `sha256`: hash SHA-256 do arquivo integral recebido;
- `valido_para_confirmacao`: ausência de erros estruturais e cadastrais;
- `resumo`: contagens por aba de criações, atualizações, desativações, linhas sem
  alteração, avisos e erros;
- `operacoes`: ações que seriam executadas e os nomes dos campos que mudariam;
- `operacoes_total`: total anterior ao limite da resposta;
- `diagnosticos`: erros e avisos localizados;
- `diagnosticos_total`: total anterior ao limite da resposta;
- `resultado_truncado`: indica corte de diagnósticos ou operações.

A resposta expõe no máximo 200 diagnósticos e 500 operações. Contagens do resumo
sempre consideram o resultado completo. Mensagens não incluem SQL, stack trace,
credenciais, caminhos internos ou o conteúdo das células.

Valores destinados a colunas `Numeric(18,6)` devem caber em até 12 algarismos na
parte inteira e 6 casas decimais. A pré-validação rejeita excesso de precisão ou
escala, sem arredondamento silencioso.

### Comparação cadastral

- `MATERIAS_PRIMAS/CRIAR`: código ausente e nome sem conflito;
- `MATERIAS_PRIMAS/ATUALIZAR`: código existente, com lista dos campos realmente
  diferentes;
- `MATERIAS_PRIMAS/DESATIVAR`: MP ativa gera ação; MP já inativa gera
  `SEM_ALTERACAO`;
- `NUTRIENTES/CRIAR`: código ausente e nome sem conflito;
- `NUTRIENTES/ATUALIZAR`: código existente; mudança de unidade é rejeitada se o
  nutriente já participa de alguma composição;
- `COMPOSICAO_NUTRICIONAL/CRIAR`: o par de códigos deve ser novo;
- `COMPOSICAO_NUTRICIONAL/ATUALIZAR`: o par deve existir; valor idêntico gera
  `SEM_ALTERACAO`;
- `PRECOS_MP/CRIAR`: o intervalo não pode sobrepor outro intervalo do arquivo ou
  do banco. As duas extremidades são inclusivas: se um período termina em
  `2026-01-31`, outro iniciado em `2026-01-31` conflita; o início em `2026-02-01`
  é permitido. Um período sem data final conflita com qualquer período posterior
  da mesma matéria-prima, e dois períodos abertos sempre conflitam. Todas as
  sobreposições são diagnosticadas de modo determinístico, independentemente da
  ordem física das linhas; a pré-validação não fecha períodos automaticamente.

Entidades referenciadas podem ser resolvidas por uma ação `CRIAR` válida no mesmo
workbook ou pelo código exato existente no banco. Uma criação com qualquer erro
cadastral não torna seu código disponível para composições ou preços. Não há
associação por nome semelhante. Matérias-primas inativas ou desativadas no lote
não podem receber composição ou preço.

### Ausência de reserva

A pré-validação não cria token, staging, bloqueio ou reserva. O banco poderá mudar
imediatamente depois da resposta. O Bloco 3 deverá repetir integralmente as
validações dentro da mesma transação usada para confirmar o lote; um resultado
válido desta etapa não garante que a confirmação futura continuará válida.

## Preparação temporária

`POST /api/v1/importacoes-cadastrais/preparar` repete integralmente o parser e a
pré-validação. Uma planilha inválida não cria sessão. Para uma planilha válida, a
API persiste somente o payload normalizado, seu resumo e os avisos, sem aplicar
qualquer alteração cadastral e sem guardar os bytes do XLSX.

Cada preparação cria uma sessão independente, mesmo quando o arquivo e seu hash
são iguais. A resposta de criação é o único momento em que o token secreto é
exibido. O banco guarda apenas seu SHA-256. O token possui 256 bits aleatórios e
será comparado em tempo constante pela futura confirmação, que será idempotente
por sessão. A sessão começa como `PENDENTE` e expira após 24 horas.

`GET /api/v1/importacoes-cadastrais/{sessao_id}` retorna somente o UUID público,
estado, hash do arquivo, versão do contrato, resumo, total de operações, avisos e
datas. Nunca retorna token, digest do token ou payload normalizado. Uma sessão
pendente consultada depois do prazo passa logicamente a `EXPIRADA` sem alterar
matérias-primas, nutrientes, composições ou preços.

A decisão de vencimento usa o relógio do PostgreSQL. Consultar uma sessão
`PENDENTE` vencida pode alterar exclusivamente seu estado para `EXPIRADA`;
consultas seguintes são idempotentes. Sessões `CONFIRMADA`, `EXPIRADA` ou
`FALHOU` são finais e nunca expiram nem retornam a `PENDENTE`. Uma confirmação
futura deverá gravar `confirmado_em` e `resultado` na mesma transição. Uma falha
futura deverá guardar apenas um diagnóstico seguro em `resultado`.

O Bloco 3A não possui endpoint de confirmação. Portanto, nenhuma operação
cadastral pode ser aplicada a partir de uma sessão preparada nesta etapa.

## Confirmação transacional

`POST /api/v1/importacoes-cadastrais/{sessao_id}/confirmar` recebe somente o
`token`. A sessão é bloqueada com `SELECT FOR UPDATE`; o token é comparado em
tempo constante e nunca é persistido ou retornado. UUID inexistente e token
incorreto recebem a mesma resposta genérica.

A confirmação bloqueia, nesta ordem, `nutrientes`, `materias_primas`,
`composicoes_materias_primas` e `precos_materias_primas` em modo
`SHARE ROW EXCLUSIVE`. O bloqueio serializa escritores durante a revalidação e a
aplicação, protegendo especialmente intervalos de preços, que não possuem uma
constraint de exclusão. O custo é reduzir temporariamente a concorrência de
escrita cadastral; consultas permanecem disponíveis.

O XLSX não é armazenado nem reutilizado. O servidor reconstrói o contrato a
partir do payload canônico, revalida códigos e regras contra o PostgreSQL e
aplica, em transação única, nutrientes, matérias-primas, composições, preços e,
por último, desativações. Revalidação conflitante marca a sessão como `FALHOU`
sem alterar cadastros. Falha técnica desfaz primeiro toda a transação e registra
um diagnóstico genérico em transação separada.

Uma sessão `CONFIRMADA` com o token correto retorna o resultado persistido sem
reaplicar operações. Assim, confirmações repetidas e concorrentes da mesma
sessão são idempotentes.
