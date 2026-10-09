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
