# roadmap-site — Spec

> Status: aprovado (Fase 2), revisado em 2026-11-27 após leitura da planilha real. Documento agnóstico de tecnologia: o "como" fica em `design.md`.
> Idioma: este documento está em português; **todo o conteúdo do site é em inglês**.

## Problem

A evolução do Lucas de Senior Data Engineer para AI Data Engineer está registrada numa planilha privada do Google Sheets ("Plano de Estudos"). A planilha mistura o plano de estudos com notas pessoais (sobre a busca de vaga, cursos retirados do plano, preparação para entrevistas) e está em português, com formatos pt-BR. Por isso não pode ser mostrada a recrutadores e gestores de fora do Brasil, e hoje não existe um jeito público e confiável de provar essa trilha.

## Goal and success metric

**Objetivo:** um site público, em inglês, que mostre em 1–2 minutos de leitura:
1. a trilha de estudos organizada por competência;
2. os projetos práticos ligados a cada competência;
3. os cursos e certificações (concluídos e em andamento);
4. o progresso em horas ao longo do tempo.

O conteúdo vem da planilha, que é a **única fonte de verdade**. O próprio pipeline planilha → site funciona como peça de portfólio de engenharia de dados.

**Métrica de sucesso:** até ~2027-01-26 (2 meses), o link do site está no CV e no LinkedIn e foi usado em candidaturas e conversas com recrutadores.

**Métricas de apoio (verificáveis):**
- O site fica no máximo 24h atrás da planilha em ≥ 95% dos dias.
- Zero ocorrências de conteúdo confidencial publicado (ver R8).

## Out of scope

- A coluna `Observação` e qualquer nota pessoal ou sobre busca de vaga.
- A aba `Entrevistas`.
- Cursos retirados do plano (bootcamps HermesAgent e Engenharia Agêntica).
- Login, multiusuário, edição de conteúdo pelo site.
- DevSpeak e o estudo de inglês.
- Qualquer informação sobre o cliente atual (projeto em que o Lucas está alocado hoje).
- Uso do site como produto por outras pessoas (template, SaaS).
- Versão em português do site.

## Personas and stakeholders

| Persona | Papel | O que precisa |
|---|---|---|
| **Recrutador estrangeiro** (principal) | Lê o site a partir do CV/LinkedIn, em 1–2 min, muitas vezes no celular | Entender rápido o foco (AI Data Engineering), o que já foi concluído e se há prova prática |
| **Gestor técnico / hiring manager** | Avalia profundidade técnica | Ver projetos, arquitetura, stack e o pipeline do próprio site |
| **Lucas** (dono/mantenedor) | Atualiza só a planilha | Nunca editar o site à mão; ter a garantia de que nada privado vaza; saber quando a atualização falhar |

## Functional requirements

### R1 — Trilha por competência
Como **recrutador**, quero ver as competências da trilha (ex. "LLM Engineering", "Spark & Databricks") com o status e o % de progresso de cada uma, para entender o foco e a maturidade em poucos segundos.
- **Given** que a aba `Publico` tem competências marcadas como públicas
  **When** o site é gerado
  **Then** cada competência aparece com nome e descrição em inglês, status (Not started / In progress / Done) e % de progresso.
- **Given** uma competência com cursos ligados no `Cronograma`
  **When** o % é calculado
  **Then** % = horas "Feito" ÷ (horas "Feito" + horas "A fazer") dos cursos ligados. Linhas "Não feito" (sessões perdidas) não entram em nenhum dos dois lados e nunca aparecem no site.
- **Given** uma competência sem nenhuma hora planejada
  **When** o site é gerado
  **Then** ela aparece sem barra de % e sem divisão por zero: "In progress" se tiver ao menos um projeto público ligado (trabalho prático em andamento), senão "Planned".
- **Given** uma competência com algum curso ligado já começado (In progress ou Done) mas nem todos concluídos
  **When** o site é gerado
  **Then** ela aparece como "In progress", e só vira "Done" quando todos os cursos ligados estiverem Done. *(revisão 2026-11-27, ADR-10)*
- **Given** a trilha `Spark & Databricks` pública e módulos mapeados **e marcados como públicos** na aba `Publico` (opcional: desde 2026-11-27 os módulos estão com `publicar=não`, para o site não ficar granular demais)
  **When** o site é gerado
  **Then** o card mostra a lista de módulos (nome em inglês + Done/Planned) como checklist, **sem horas**. Horas e % da trilha vêm só do `Cronograma`.

### R2 — Projetos práticos ligados
Como **gestor técnico**, quero ver os projetos práticos de cada competência, com descrição, stack e link, para avaliar se o estudo virou prática.
- **Given** um projeto público com repositório público
  **When** o site é gerado
  **Then** o card mostra título, descrição curta em inglês, stack, competência(s) ligada(s) e link para o repositório.
- **Given** um projeto com repositório privado (ex. `job-search-agent`)
  **When** o site é gerado
  **Then** o card leva a um **case escrito** no site (problema, arquitetura, stack, resultados) e não mostra link para o repositório.
- **Given** um projeto ligado a uma competência não pública
  **When** o site é gerado
  **Then** o projeto não aparece (ou aparece só nas competências públicas, se tiver mais de uma).

### R3 — Cursos e certificações
Como **recrutador**, quero ver a lista de cursos e certificações com status e, quando houver, um link de credencial, para validar a formação.
- **Given** um curso mapeado na aba `Publico` e marcado como público
  **When** o site é gerado
  **Then** aparece com nome em inglês, provedor, competência, status e horas (concluídas/planejadas).
- **Given** um curso concluído com URL de certificado
  **When** o site é gerado
  **Then** o link "View credential" aparece.
- **Given** um curso que existe no `Cronograma` mas não está mapeado na aba `Publico`
  **When** o site é gerado
  **Then** ele **não** aparece no site (ver R8).
- **Given** um curso feito fora do `Cronograma` (ex. concluído antes do plano, ou em andamento noutro ritmo), com status manual na aba `Publico` *(revisão 2026-11-27, ADR-10)*
  **When** o site é gerado
  **Then** aparece com o status manual. Se Done, mostra a carga total informada (ex. 70h). Se In progress, mostra feito/total informados (ex. 105/384h). Sem horas informadas, aparece sem horas. Essas horas entram nos KPIs e no % da competência.

### R4 — Progresso em horas
Como **recrutador**, quero ver números de progresso confiáveis, para perceber constância e volume de estudo.
- **Given** qualquer volume de histórico
  **When** o site é gerado
  **Then** o bloco mostra KPIs: horas concluídas, % do plano total, cursos concluídos / total e data de início dos estudos.
- **Given** que os estudos começaram antes do `Cronograma` existir *(revisão 2026-11-27)*
  **When** o site é gerado
  **Then** a data de início vem de um valor configurado (`studying_since`), e não da primeira linha do `Cronograma`.
- **Given** menos de 4 semanas de histórico com horas concluídas
  **When** o site é gerado
  **Then** o gráfico temporal **não** aparece; só os KPIs e as barras por competência.
- **Given** 4 semanas ou mais de histórico
  **When** o site é gerado
  **Then** aparece também um gráfico de horas concluídas acumuladas por semana.
- Só entram nos cálculos as linhas do `Cronograma` cujo curso é público (R8). Horas de cursos fora do escopo não somam nem no numerador nem no denominador.

### R5 — "How this site works"
Como **gestor técnico**, quero ver como o site é alimentado, para avaliar a skill de engenharia de dados por trás dele.
- **Given** o site publicado
  **When** o leitor abre a seção "How this site works"
  **Then** vê um diagrama curto do fluxo (planilha → validação → dados → site), a stack usada, o link para o repositório público do projeto e a data/hora da última atualização bem-sucedida.
- **Given** o site publicado *(revisão 2026-11-27, ADR-12)*
  **When** o leitor abre "How this site works" ou o case de um projeto que tem diagrama
  **Then** vê um diagrama de arquitetura em inglês (imagem estática, legível no celular e no desktop, com texto alternativo), sem links para código privado. O diagrama do case segue as mesmas regras de conteúdo do texto do case (R8).

### R6 — Atualização a partir da planilha
Como **Lucas**, quero que o site se atualize sozinho a partir da planilha, para nunca precisar editá-lo à mão.
- **Given** que a planilha mudou
  **When** passa a atualização diária agendada
  **Then** o site reflete a mudança em no máximo 24h.
- **Given** que o Lucas quer publicar já
  **When** ele dispara uma atualização manual
  **Then** o site é regerado com os dados atuais da planilha.
- **Given** que a planilha não mudou
  **When** a atualização roda
  **Then** o site publicado fica igual (a geração é idempotente e determinística).

### R7 — Validação e falha segura
Como **Lucas**, quero que dados inválidos bloqueiem a publicação, para que um recrutador nunca veja um site quebrado ou errado.
- **Given** um dado inválido (ver regras de qualidade em RNF-Q)
  **When** a atualização roda
  **Then** a publicação é **bloqueada**, o site continua com a última versão válida e o Lucas recebe um aviso dizendo qual aba, qual linha e qual regra falhou.
- **Given** uma atualização que falhou
  **When** a próxima atualização com dados válidos roda
  **Then** o site volta a ser atualizado normalmente.

### R8 — Publicação por allowlist e confidencialidade
Como **Lucas**, quero que só o conteúdo explicitamente marcado como público vá para o site, para garantir que nenhuma nota pessoal e nada sobre o cliente atual vaze.
- **Given** uma linha da aba `Publico` com flag de publicação ≠ "sim"
  **When** o site é gerado
  **Then** essa linha e tudo o que depende só dela não aparecem.
- **Given** qualquer conteúdo do site
  **When** o site é gerado
  **Then** nenhum texto vem da coluna `Observação`, da aba `Entrevistas` ou de colunas de texto livre do `Cronograma` (`Atividade`). Do `Cronograma`, o site só usa data, curso, horas e status.
- **Given** uma lista de termos proibidos mantida fora do repositório público (ex. nome do cliente atual)
  **When** a atualização roda
  **Then** se qualquer termo proibido aparecer no conteúdo a publicar, a publicação é bloqueada (R7).
- **Given** um case escrito de projeto *(revisão 2026-11-27)*
  **When** é publicado
  **Then** não nomeia plataformas de vagas (nem no texto nem no endereço da página) e não diz quais empresas o projeto exclui; regras de exclusão aparecem só de forma genérica ("filtro de empresas configurável").
- **Given** os dados intermediários e os logs da atualização
  **When** ficam disponíveis publicamente (repositório, artefatos)
  **Then** contêm só dados já filtrados pela allowlist.

### R9 — Leitura rápida e acessível
Como **recrutador**, quero ler o site em 1–2 min, inclusive no celular, para decidir rápido se vale uma conversa.
- **Given** a página inicial
  **When** é aberta
  **Then** o topo mostra nome, título-alvo ("Senior Data Engineer → AI Data Engineer"), resumo de 1–2 frases, links (LinkedIn, GitHub; CV fora do MVP) e os KPIs principais, sem precisar rolar a tela no desktop.
- **Given** que o público principal é recrutador estrangeiro *(revisão 2026-11-27, ADR-11)*
  **When** a página inicial é aberta
  **Then** o topo mostra uma linha de idioma ("English: B2 · ongoing coaching (speaking & writing)"), vinda da configuração, sem horas, sem % e sem o nome da escola de idiomas, que continua bloqueado (R8). O estudo de inglês não entra em competências, cursos nem KPIs.
- **Given** um celular (largura ≥ 360px)
  **When** o site é aberto
  **Then** todo o conteúdo fica legível, sem rolagem horizontal.
- **Given** o site publicado
  **When** é avaliado com uma ferramenta padrão de auditoria (ex. Lighthouse)
  **Then** tem nota ≥ 90 em Performance e Accessibility.

## Non-functional requirements

### Fontes e responsáveis
| Fonte | Responsável | Uso no site |
|---|---|---|
| Google Sheets "Plano de Estudos", aba `Publico` (nova, a criar) | Lucas | Mapeamento curado: competência → curso → projeto, textos em inglês, links, flag de publicação |
| Mesma planilha, aba `Cronograma` | Lucas | Só data, curso, horas e status |
| Mesma planilha, aba `Spark & Databricks` | Lucas | Só módulo, horas e status, e só se a trilha estiver mapeada na aba `Publico`. **Nunca** a coluna `Observação` |
| Cases escritos de projetos privados | Lucas | Markdown em inglês no repositório do site (ADR-05) |

### Volume e crescimento
Volume trivial: centenas de linhas/ano (~1 linha por dia de estudo, dezenas de cursos/projetos). Não há requisito de escala.

### Frequência e latência
- Batch diário agendado + disparo manual sob demanda (R6).
- SLO: site no máximo 24h atrás da planilha em ≥ 95% dos dias. Uma falha não é incidente urgente: o site continua no ar com a versão anterior.

### RNF-Q — Regras de qualidade de dados (bloqueiam a publicação, R7)
1. **Esquema:** as abas e os cabeçalhos esperados existem (`Cronograma` com cabeçalho na linha 4; as linhas 1–3 de totais são ignoradas).
2. **Datas:** `Data` no formato dd/mm é uma data de calendário válida. O ano é inferido pela ordem cronológica das linhas: o plano começa no ano de início configurado e, quando o mês "volta" (ex. 12 → 01), o ano avança. A data inferida não pode ficar mais de 1 dia no futuro, salvo nas linhas "A fazer".
3. **Horas:** `Horas` é um número pt-BR válido (vírgula decimal, ex. "2,0"), com 0 ≤ horas ≤ 12 por linha.
4. **Status:** só "Feito", "A fazer" ou "Não feito" (normalizado para Done / Planned / Missed). Missed não entra em cálculos nem no site.
5. **Integridade referencial:** todo curso público na aba `Publico` tem nome em inglês e competência válida; todo projeto público tem descrição em inglês e (link público **ou** case escrito).
6. **Unicidade:** IDs/nomes de competência, curso e projeto são únicos na aba `Publico`.
7. **Reconciliação:** as somas calculadas batem com os três totais das linhas 1–3 do `Cronograma` ("Horas planejadas", "Horas concluídas", "Horas não feitas"; tolerância de 0,1h), considerando todas as linhas antes do filtro de publicação. Se não bater, a publicação é bloqueada, porque isso indica que o parsing está errado.
8. **Confidencialidade:** nenhum termo proibido aparece no conteúdo a publicar (R8).

### Histórico e retenção
- A planilha é a fonte de verdade; o site não guarda estado próprio.
- Cada publicação bem-sucedida guarda um snapshot versionado dos dados publicados (permite comparar versões e voltar atrás).
- O histórico de horas vem do próprio `Cronograma` (não depende de snapshots).

### Privacidade, LGPD/GDPR e acesso
- Os únicos dados pessoais publicados são do próprio Lucas, com consentimento dele (nome, links profissionais). Nenhum dado de terceiros.
- A planilha continua privada. O acesso de leitura da atualização usa uma credencial de **somente leitura**, que nunca fica no repositório nem nos logs.
- Sem cookies de rastreio nem analytics que exijam banner de consentimento no MVP.

### Consumidores
Só o site estático público (navegador). Não há API, BI nem ML/LLM consumindo os dados.

### Custo
Meta de **R$ 0/mês** em infraestrutura (camadas gratuitas). Um domínio próprio, se for usado, é o único custo aceito (~US$ 10–15/ano), a decidir no design.

### Manutenção
- Fluxo do Lucas: editar a planilha e pronto. Nenhum passo manual obrigatório para publicar.
- Adicionar uma competência, curso ou projeto novo = adicionar uma linha na aba `Publico`, sem mudar código.

## Assumptions

- A1: O Lucas vai criar e manter a aba `Publico`, com todos os textos públicos escritos em inglês por ele. O site não traduz automaticamente.
- A2: O limite de 4 semanas para exibir o gráfico temporal (R4) é configurável. 4 semanas é o valor inicial.
- A3: O ano de início do plano é 2026 (configurável). A inferência de ano assume linhas em ordem cronológica no `Cronograma`.
- A4: A aba `Spark & Databricks` é o detalhamento de uma trilha que também aparece no `Cronograma`. Seus módulos entram no site só como subitens dessa trilha, se ela for pública.
- A5: O repositório do código do site será público (necessário para R5). Por isso nenhuma credencial, lista de termos proibidos ou dado bruto não filtrado pode ir para ele.
- A6: "Aviso" de falha (R7) = uma notificação que o Lucas já recebe sem configuração extra (ex. e-mail da própria plataforma de execução). O canal é decidido no design.

## Open questions

Todas as perguntas da Fase 2 foram resolvidas no design (2026-11-27):

| # | Pergunta | Resolução |
|---|---|---|
| Q1 | Hospedagem e domínio | GitHub Actions + GitHub Pages, subdomínio github.io (ADR-01) |
| Q2 | Formato visual da trilha | Cards por competência (ADR-06) |
| Q3 | Onde ficam os cases escritos | Markdown no repo, `content/cases/<project_id>.md` (ADR-05) |
| Q4 | Credencial do Google Sheets | Service account com escopo somente leitura, JSON em GitHub Secret (ADR-04) |
| Q5 | Lista de termos proibidos | GitHub Secret, testada com termos fictícios (ADR-04) |
| Q6 | Esquema da aba `Publico` | Ver `design.md`, "Data model" |
| Q7 | Ligação `Cronograma` ↔ cursos | Nome exato da coluna `Curso` (`cronograma_key`), validado (ADR-03) |
| Q8 | Link de CV | Fora do MVP |

Pendências novas estão em `design.md`, seção "Risks / Open items".
