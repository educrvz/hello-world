# Política de Privacidade — SoroJá

**Última atualização:** 21 de abril de 2026

O SoroJá é uma ferramenta gratuita, de código aberto e sem fins lucrativos que ajuda pessoas a localizar os hospitais de referência do SUS mais próximos, que mantêm soro antiveneno contra acidentes por animais peçonhentos. Esta Política explica, em linguagem simples, o que acontece com seus dados quando você usa o site.

## 1. Quem é o responsável

O SoroJá é mantido de forma voluntária por Eduardo Cruz ("Edu Cruz"), pessoa física. Contato para qualquer dúvida sobre esta Política ou para exercer direitos da LGPD:

- E-mail: contato.soroja@gmail.com
- GitHub: https://github.com/educrvz/sos-antiveneno

## 2. Que dados a gente usa

### 2.1 Sua localização geográfica (GPS / rede)

Quando você autoriza o compartilhamento da sua localização no navegador, o SoroJá usa a latitude/longitude **apenas** no próprio aparelho para calcular a distância entre você e cada hospital da base. Essa informação **não é enviada aos nossos servidores**, não é armazenada em cookies, não é salva em localStorage e não é compartilhada com terceiros para fins de análise, publicidade ou marketing.

Base legal (LGPD, art. 11, II, "f"): tratamento de dado pessoal sensível necessário para a **tutela da saúde**, em procedimento realizado por meio de serviço de saúde disponível ao cidadão.

### 2.2 Dados que seu navegador envia automaticamente a terceiros

Como qualquer site moderno, o SoroJá carrega alguns recursos técnicos de serviços externos, que — por funcionamento normal da internet — recebem seu endereço IP e informações básicas do navegador:

- **Mapa (OpenStreetMap):** ao visualizar o mapa, seu navegador solicita "tiles" (imagens de mapa) de `tile.openstreetmap.org`. Com isso, o servidor do OpenStreetMap fica sabendo a região aproximada que você está consultando.
- **Biblioteca de mapa (Leaflet, via unpkg.com):** o código do mapa é carregado do CDN unpkg.com (CloudFlare), que registra logs técnicos de acesso contendo seu IP.
- **"Como chegar" (Google Maps):** ao clicar em **Como Chegar**, seu navegador abre o Google Maps com o endereço do hospital destino. O Google recebe essa informação e aplica a sua [Política de Privacidade](https://policies.google.com/privacy) e os Termos do Google Maps.
- **Compartilhar (WhatsApp, Facebook, X, Instagram):** só quando você clica nos botões de compartilhamento, você é redirecionado para a plataforma correspondente, que passa a aplicar a política de privacidade dela.

O SoroJá não utiliza Google Analytics, Meta Pixel, Hotjar, nem qualquer ferramenta de rastreamento de usuário.

### 2.3 Cookies

O SoroJá **não usa cookies próprios**. Os recursos de terceiros citados acima podem definir cookies técnicos em seu próprio domínio quando acionados.

## 3. O que NÃO fazemos

- Não armazenamos sua localização em banco de dados.
- Não vendemos, alugamos ou compartilhamos seus dados com anunciantes.
- Não fazemos perfil de usuário.
- Não enviamos e-mails de marketing.
- Não cruzamos seus dados com outros bancos.

## 4. Origem dos dados dos hospitais

A lista de hospitais apresentada é construída a partir de dados públicos do **Ministério da Saúde** ("Hospitais de Referência para Atendimento a Acidentes por Animais Peçonhentos"), complementada quando disponível por bases estaduais (Secretarias Estaduais de Saúde e CIATox) e por geocodificação via Google Maps API (realizada off-line pelo mantenedor, sem uso de dados do usuário).

## 5. Seus direitos (LGPD)

Mesmo que o SoroJá não armazene dados seus, você tem direitos sobre informações pessoais em geral (art. 18 da LGPD), incluindo o direito de pedir confirmação do tratamento, acesso, correção, anonimização, eliminação e portabilidade. Para exercê-los, envie um pedido para o contato do item 1.

## 6. Limitação de responsabilidade

O SoroJá é uma ferramenta **informativa**, sem vínculo oficial com o Ministério da Saúde, Secretarias Estaduais, Butantan ou CIATox. Em caso de emergência, **sempre ligue 192 (SAMU) ou 193 (Bombeiros)**. Ligue também para o hospital ANTES de se deslocar, para confirmar que o soro específico está disponível no momento — o site mostra os pontos cadastrados como referência pelo Ministério da Saúde, mas a disponibilidade de estoque pode variar.

A indicação, dose e aplicação do soro antiveneno são atos privativos de profissionais de saúde habilitados.

## 7. Alterações desta Política

Podemos atualizar esta Política quando a ferramenta mudar. A versão mais recente fica sempre no rodapé do site, com a data da última atualização no topo deste documento.

## 8. Segurança

O site é servido exclusivamente via HTTPS. O código-fonte é aberto e auditável em https://github.com/educrvz/sos-antiveneno — qualquer pessoa pode verificar o que o SoroJá faz (e não faz) com seus dados.

---

*Para sugestões ou reporte de problemas nesta Política, abra uma issue no repositório ou escreva para o contato do item 1.*
