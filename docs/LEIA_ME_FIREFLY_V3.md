# Firefly v3

## Aplicar sem substituir a versão aprovada

1. Pare o Streamlit anterior com Ctrl+C.
2. Salve aplicar_firefly_v3.py na raiz C:\Projetos\flame-freefall.
3. Na .venv do PyCharm, execute `python aplicar_firefly_v3.py`.

O script cria app_firefly_v3.py, iniciar_firefly_v3.py, testar_firefly_v3.py e o
pacote src/ui/firefly_v3. Antes disso, faz uma cópia dos arquivos existentes de
app_firefly_v2.py, testar_firefly_v2.py, src/ui/firefly_v2 e .streamlit/config.toml
para work/firefly_v2_preservada_<data>. Não faz pip install, download ou execução
da aplicação. Não modifica PDFs, dados processados ou Chroma. Arquivos v3 já
existentes com conteúdo diferente causam interrupção, não sobrescrita.

Execute:

```powershell
python testar_firefly_v3.py
python iniciar_firefly_v3.py
```

São 20 testes de apresentação/contratos com dados artificiais somente nos testes.
A aplicação usa os leitores reais existentes, nunca esses dados de teste.

O segundo comando inicia Streamlit e aplica as cores por argumentos dessa
execução. Não altera o tema global em .streamlit/config.toml. Para voltar à v2,
pare o servidor e execute `python -m streamlit run app_firefly_v2.py`.

## Logotipo e cores

O carregador procura assets/firefly_logo.png, .svg, .jpg ou .jpeg, nessa ordem.
A imagem existente é exibida sem alteração. PNG/JPG são amostrados apenas em
memória para identificar o azul e o laranja predominantes. SVG: são lidas cores
hexadecimais literais, sem renderizador adicional. Cores não reconhecidas usam a
paleta anterior como fallback. O iniciador imprime caminho e cores detectadas.

O azul da marca será usado em seleção/botões/links e gráficos; o laranja em
destaques e gráficos. O fundo continua branco, e textos longos ficam em
azul-marinho para legibilidade. O título de uma marca não precisa ter a mesma
cor de todo o texto de leitura. A logotipo nunca é recolorida. A detecção não
substitui a conferência visual do arquivo original no notebook.

Se trocar a imagem, reinicie o iniciador para recalcular as cores. Não é preciso
instalar nada: Pillow já acompanha o ambiente Streamlit utilizado no projeto.

## Nova página Investigations / Investigações

- BASS-II: referências das tabelas 5.1 e 7.1, contagens locais e cartões sobre
  propagação não rastreada, ressalvas de oxigênio e reutilização.
- BASS: somente os registros PSI-26 do recorte carregado, sem descrever essa
  seleção como a investigação inteira.
- Saffire: síntese editorial, separação das missões e cartões para o resultado
  da página 8 e a divergência com o DoD. Recortes são procurados pelo ID no acervo
  já conferido; ausência de um recorte gera aviso, não evidência inventada.

Os resumos não são respostas do LLM. Não há ranking de risco, certificação de
segurança ou investigação inventada. O guia é fonte contextual, não experimento.
Para Saffire, permanecem fontes documentais e não séries de telemetria importadas.

## Conferência depois da atualização

- Logo visível na lateral e caminho correto impresso no terminal.
- cores detectadas blue/orange com origin=logo; se fallback ou logo_partial,
  conferir o formato antes de assumir que houve correspondência completa.
- abrir Investigations e alternar BASS-II, BASS e Saffire, nos dois idiomas.
- BASS-II: 27 registros SIBAL e 20 testes PMMA; quatro condições sem propagação.
- BASS: quatro registros SIBAL; não atribuir os registros BASS-II a essa ficha.
- Saffire: 25 cm/s e 2,32 mm/s no artigo; 30 cm/s no DoD em linguagem prospectiva.
- abrir evidência original, conferir páginas e testar botões para os exploradores.
- confirmar que filtros, busca, exportações e calculadora anteriores permanecem.

## Limites dos testes

Os testes verificam interface, cálculo, associação de fontes, detecção de cores e
preservação de dados. Não executam o índice real do notebook nem verificam a
logotipo que só está naquele computador. A revisão científica dos textos deve
continuar vinculada aos PDFs citados. As versões compartilham leitores e acervo;
preservar o código da interface não congela dependências ou versões dos dados.
