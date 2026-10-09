# Learning Log

## 06/10 - Dia 1: app Python
- Fiz:
- Quebrou:
- Resolvi assim:
- Duvida aberta:
- Proximo passo: cf push no space dev

## 06/10 - Dia 1: app Python
- Fiz: API rodando local, fluxo completo no Swagger, 11 testes passando, ruff limpo
- Quebrou: removi a regra de fornecedor bloqueado e o teste pegou (assert 201 == 422)
- Resolvi assim: git diff para ver a mudança, git restore para voltar
- Duvida aberta: (o que ficou confuso na leitura)
- Proximo passo: manifest.yml e cf push no space dev

5.3. Payload inválido pelo Swagger. Com o uvicorn rodando, cria o fornecedor 1 de novo (os dados sumiram no restart) e manda em POST /purchase-orders:

json
{"supplier_id": 1, "items": [{"material": "MAT-001", "quantity": 0, "unit_price": 10}]}

Resposta 422 com um detail parecido com este:

json
{"type": "greater_than", "loc": ["body", "items", 0, "quantity"], "msg": "Input should be greater than 0"}

O loc é o caminho exato do erro: no corpo, lista items, posição 0, campo quantity. Esse formato é o que você vai ler no Message Monitoring da Integration Suite na semana 4, quando o iFlow mandar um pedido malformado para a API. Testa também "country": "BRA" num fornecedor e "items": [] num pedido para ver outras mensagens.

Repara na diferença entre os dois 422 que você viu hoje: o do fornecedor bloqueado vem da sua regra de negócio no router; o do quantity: 0 vem do Pydantic, antes do código do endpoint rodar.

Para o log de hoje, isso já é o segundo incidente de ferramenta: arquitetura de CPU incompatível. Vale registrar, porque a mesma classe de problema aparece com imagens Docker na semana 4 (imagem amd64 rodando em máquina arm64), e você já vai reconhecer o sintoma.

Comando	Resultado esperado	Se vier diferente
uname -m	arm64	Só informativo
no teminal "/usr/bin/pgrep -q oahd && echo "Rosetta: OK" || echo "Rosetta: NAO instalado" "verificação do Rosetta	Rosetta: OK	softwareupdate --install-rosetta --agree-to-license
which cf && cf version	Um caminho tipo /opt/homebrew/bin/cf e cf version 8.x	brew trust cloudfoundry/tap e depois brew link cloudfoundry/tap/cf-cli@8
cf plugins	Linha com multiapps e comandos como deploy, mtas, dmol	Com Rosetta OK, rodar cf install-plugin multiapps -f de novo
node --version	v20 ou superior	brew install node
npm --version	Qualquer versão	Vem junto com o Node
which mbt && mbt --version	Caminho e Cloud MTA Build Tool version 1.2.x	npm install -g mbt

bash
cf target

Aparecem org (algo terminando em trial) e space (dev). Hierarquia que você tem que saber de cor: global account > subaccount > org do Cloud Foundry > space > app. A org é criada quando o ambiente CF é habilitado no subaccount; os spaces separam ambientes dentro dela.

Check the health curl https://procurement-api-shy-lion-cd.cfapps.us10-001.hana.ondemand.com/health
__________________

BOM PARA USAR DE EXEMPLO NA ENTREVISTA :

Experimento de 5 minutos que vale fazer agora, porque responde uma pergunta clássica de entrevista:

bash
cf scale procurement-api -i 2

Com duas instâncias rodando, chama GET /suppliers várias vezes seguidas. Às vezes o fornecedor aparece, às vezes a lista vem vazia. O roteador do CF distribui as requisições entre as instâncias, e cada uma tem sua própria memória, então só a instância que recebeu o POST conhece o fornecedor. Nos logs, o sufixo [APP/PROC/WEB/0] ou [APP/PROC/WEB/1] mostra qual instância respondeu.

Isso demonstra o princípio de que apps em nuvem precisam ser stateless: o estado mora num serviço externo (banco, cache), nunca no processo. É por isso que escalar horizontalmente e reiniciar instâncias é seguro em produção, e é a justificativa do ADR que comentei no dia 1. Quando o app passar a usar um banco gerenciado, aí sim você vai ver os registros numa ferramenta do BTP (o Database Explorer, no caso do HANA Cloud).

Depois volta para uma instância, que o trial tem quota de memória limitada:

bash
cf scale procurement-api -i 1

Registra esse experimento no LEARNING_LOG.md; é uma das melhores histórias curtas do lab.

___________________

3.4. Variáveis de ambiente:

bash
cf env procurement-api

Repara no VCAP_APPLICATION (dados do app, rota, limites). Amanhã aparece também o VCAP_SERVICES, onde o CF injeta as credenciais do XSUAA quando você faz o binding. Entender o VCAP_SERVICES é metade do troubleshooting de serviço no BTP.


Parte 6: fixar a diferença
                                    cf push	                    cf deploy (MTA)
Unidade	                            Um app	                    Pacote com apps, serviços e dependências
Descritor	                        manifest.yml	            mta.yaml / mtad.yaml
Serviços(XSUAA, Destination)        Criados e vinculados à mão	Declarados no pacote e criados no deploy
Transporte via Cloud TMS	        Não	                        Sim
Uso típico	                        Teste rápido, protótipo	    Entrega em landscape SAP


XSUAA

XSUAA stands for Extended Services for User Account and Authentication. It is the central authentication and authorization service in SAP Business Technology Platform (SAP BTP) (formally part of Cloud Foundry, Kyma, and Neo environments).

What XSUAA Does

• Authentication: Verifies user identity using OAuth 2.0 and JSON Web Tokens (JWT).
• Authorization: Checks user permissions (scopes and roles) to decide if an action is allowed.
• No User Storage: XSUAA does not store real user master data. It delegates user management to trusted external Identity Providers (IdPs) such as the SAP ID Service or SAP Cloud Identity Services (IAS).
• Multi-Tenancy: Extends open-source Cloud Foundry UAA with enterprise features to support multi-tenant SaaS applications.

Core Architecture & Workflow

1. App Router: A single-entry-point Node.js component (xs-app.json) receives user requests and routes them to your backend microservices.
2. Token Issuance: The user logs in via the external IdP; XSUAA validates the credentials and issues a JWT access token.
3. Propagation: The App Router forwards the JWT token to downstream applications or CAP/Node.js services.
4. Enforcement: Microservices inspect the scopes inside the JWT token to allow or deny API operations.

Typical Security Configuration (xs-security.json)

When building an application (such as a CAP or Node.js app), you define your security model in an xs-security.json file:
• xsappname: Unique name for your application security domain.
• scopes: Technical permissions (e.g., $XSAPPNAME.Admin).
• role-templates: Groupings of scopes into logical developer-defined templates.
• role-collections: Business-facing collections assigned to users in the SAP BTP Cockpit.

Parte 1: o modelo mental (20 min)
Peça	        O que é	                                                                        Onde vive
Scope	        Permissão atômica que o código checa (Viewer, Admin)	                     xs-security.json
Role template	Agrupa scopes; é o "papel" definido pelo desenvolvedor	                     xs-security.json
Role collection	Agrupa roles; é o que o administrador atribui a pessoas	                     xs-security.json       ou     cockpit
Instância XSUAA	O servidor OAuth do seu app, criado a partir do xs-security.json	         Service instance no space
Binding	        Liga a instância ao app e injeta as credenciais em VCAP_SERVICES	         requires no mta.yaml
Token JWT	    Prova de identidade com os scopes dentro; o app valida a assinatura com sap-xssec	Header Authorization: Bearer ...



export CLIENTID='sb-procurement-ops-lab!t723779'
export CLIENTSECRET='f73ce68d-f2bf-42d9-a52d-9fdbf3635f86$RqVHlSVcjhZOOxmHrjRa81oLYa1cAuONyC0c3rmSIMo='
export UAA_URL='https://27485d6atrial.authentication.us10.hana.ondemand.com'
export API='https://27485d6atrial-dev-procurement-api.cfapps.us10-001.hana.ondemand.com'

TOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=client_credentials | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $TOKEN" $API/me
curl -s -H "Authorization: Bearer $TOKEN" $API/suppliers
curl -s -i -H "Authorization: Bearer $TOKEN" -X POST $API/suppliers \
  -H "Content-Type: application/json" -d '{"name":"Acme","country":"BR"}'


UTOKEN=$(curl -s -u "$CLIENTID:$CLIENTSECRET" "$UAA_URL/oauth/token" \
  -d grant_type=password -d username='matheusboneli@hotmail.com' --data-urlencode "password=$PASS" \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
curl -s -H "Authorization: Bearer $UTOKEN" $API/me

  
  ___________
  ## START BTP

  cf start procurement-api
cf app procurement-api
curl https://27485d6atrial-dev-procurement-api.cfapps.us10-001.hana.ondemand.com/health


Quando der problema de credentials =
Agora é outro token: o da sua sessão no cf CLI, que também é um JWT com validade e expirou. Faz login de novo:

bash
cf login

Ele lembra o endpoint da API; pede e-mail e senha, e se perguntar org e space, escolhe 27485d6atrial e dev. Se não lembrar o endpoint:

bash
cf login -a https://api.cf.us10-001.hana.ondemand.com

Depois segue de onde parou:

bash
cf service-key procurement-xsuaa lab-key
export CLIENTSECRET='cole-o-novo-aqui'
UTOKEN=$(gettoken)

Repara que hoje você esbarrou em três credenciais diferentes, cada uma com seu ciclo de vida: o secret da service key (morre quando a key é apagada), o token de usuário do XSUAA (expira em horas, é uma fotografia das roles) e o token do cf CLI (expira, e o cf login renova). Saber qual delas falhou é metade do diagnóstico, e a mensagem de erro sempre diz: invalid_client é a key; 401 no app é o token do XSUAA; “Please log back in” é o CLI.

Para pensar: o problema dos dois pipelines independentes

O GitHub Actions roda os testes. O CI/CD service faz o deploy. Nada liga um ao outro. Se você der push num código com um teste quebrado, o GitHub Actions fica vermelho, e mesmo assim o CI/CD service faz o deploy do código quebrado em dev.

Em dev isso é tolerável; em produção, seria um incidente. As soluções possíveis são:

Proteger a main, para só entrar código que passou no CI. Você faz isso no domingo.
Ter um único pipeline com testes e deploy em sequência (o CD do GitHub Actions de amanhã).
Rodar os testes dentro do próprio CI/CD service, usando a configuração por arquivo (.pipeline/config.yml), que dá mais flexibilidade (22/10).

É assim que se investiga “fiz push e o build não disparou”: primeiro olha o Recent Deliveries no lado de quem envia. Se a entrega nem saiu, é configuração do webhook no GitHub (evento errado, webhook inativo). Se saiu e voltou com erro, a resposta diz o motivo (secret, URL). Se voltou 2xx e mesmo assim não houve build, o problema está no serviço (branch diferente da do job, job desligado).

## 09/10 - Dia 5: SAP CI/CD service
- Fiz: subscription + role collections; credenciais github, cf e webhook; job com Build e Release; deploy disparado por push (0.2.1)
- Quebrou: webhook com secret errado (Recent Deliveries com erro, nenhum build); space inexistente (Release falhou, Build passou)
- Resolvi assim: Recent Deliveries para webhook; log da etapa para deploy
- Aprendi: GitHub Actions e CI/CD service não se conversam; deploy acontece mesmo com teste vermelho
- Limitação: CI/CD service não roda pytest no modelo de CAP; deploy usa minha conta pessoal (sem usuário técnico no trial)
- Duvida aberta:
- Parei em:
- Proximo passo: GitHub Actions (CD) + Destination (10/10)