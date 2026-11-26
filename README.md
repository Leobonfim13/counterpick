# CounterPick — counters, builds e draft de League of Legends

Ferramenta local que recomenda **qual campeão escolher** contra o time inimigo, com runas, itens e ordem de habilidades do patch atual. Junta estatísticas do **op.gg** com dados oficiais da **Riot** e leva em conta os campeões que **você** joga bem.

Sem IA paga, sem servidor na nuvem: roda no seu PC e atualiza sozinho quando sai patch novo.

## Funcionalidades

- **Três modos**: só a minha lane (contra o oponente direto), composição inteira e **draft** (considera a ordem de escolha e o que o inimigo já pegou).
- **Recomendação personalizada**: cruza a força do campeão no confronto com o seu histórico (partidas, taxa de vitória, KDA) puxado pelo Riot ID.
- **Build do confronto**: com o seu campeão e o oponente definidos, busca runas, itens e dica **daquele confronto específico**.
- **Leitura de print**: mande um print da seleção de campeões ou do Tab e ele identifica os campeões de cada time com visão computacional (OpenCV), sem enviar a imagem para fora do PC.
- **Coleta da Riot**: soma partidas de alto elo do servidor BR às estatísticas.
- **Modo amigos**: amigos convidados acessam pela rede privada do **Tailscale**, com permissões menores que o dono.

## Segurança

| Ameaça | Defesa |
|---|---|
| Vazamento da chave da Riot | Chave só no `.env` (fora do Git), relida a cada pedido e **nunca** devolvida ao navegador |
| Acesso pela rede/internet | Servidor escuta só em `127.0.0.1`; no modo amigos, também no IP do Tailscale, e recusa qualquer IP fora dessas redes |
| DNS rebinding | Só atende requisições com `Host` deste computador |
| CSRF | API exige cabeçalho próprio (bloqueado entre sites pelo CORS) e confere a `Origin` |
| XSS | Interface montada com APIs do DOM (sem `innerHTML` de dados); CSP **sem script inline** |
| Abuso de cota | Limite de pedidos por pessoa e por rota; rotas que mexem nos dados são exclusivas do dono |
| Entradas malformadas | Tipos errados, `NaN`, infinito e listas gigantes viram vazio/limite, nunca derrubam o servidor |
| "Bomba" de imagem | Limite de pixels no OpenCV e recusa de proporções absurdas antes de redimensionar |
| Privacidade dos amigos | Registro de acessos guarda quem e quando, nunca o que foi digitado; fica fora do Git |

## Testes

```bash
python testes/test_seguranca.py
```

11 testes de segurança e robustez, executados **sem internet** sobre uma cópia do banco. Foram validados contra a versão anterior do código, na qual 3 deles falhavam.

`testes/medir_leitor.py` mede a precisão da leitura de prints usando o gabarito em `testes/prints/`.

## Como rodar

Requer Python 3.10+.

```bash
pip install -r requirements.txt
cp .env.exemplo .env     # opcional: coloque sua chave da Riot e seu Riot ID
python app.py
```

Abra `http://localhost:5002`. No primeiro uso ele baixa os dados do patch (alguns minutos, em segundo plano). Sem chave da Riot, tudo funciona com os dados do op.gg.

## Tecnologias

Python · Flask · SQLite · OpenCV · NumPy · HTML/CSS/JavaScript puro · Riot Games API · Data Dragon · op.gg

## Aviso legal

CounterPick isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.

Estatísticas de partidas e builds são de **op.gg**. Este é um projeto de fã, pessoal e sem fins lucrativos.
