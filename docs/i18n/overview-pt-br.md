# Visão geral da Retra

A Retra foi reconstruída do zero para diminuir o trabalho feito quando um valor já está no
cache.

No cache em memória, o valor Python é guardado diretamente. Um acerto não usa Pickle, JSON, arquivo
ou SQLite. A assinatura da função é analisada somente quando o decorator é criado, e a Retra gera
uma função intermediária especializada para aquela assinatura.

As chaves diferenciam tipos que o Python normalmente considera iguais, como `True`, `1` e `1.0`.
Para invalidar muitos resultados, a Retra usa números de geração: incrementar um contador torna as
entradas antigas inválidas sem precisar percorrer toda a memória.

Existem três modos de concorrência:

- `single`: mais rápido, para uma única thread;
- `read_heavy`: leituras sem lock e escritas por cópia de pequenos shards;
- `balanced`: locks separados por shard para uso geral entre threads.

Arquivos e SQLite são opções explícitas. Um cache somente em memória nunca acessa o disco
escondidamente. O modo em camadas também é explícito, pois uma falha na camada de memória pode
consultar a camada persistente.

A biblioteca continua sendo Python puro. Ela reduz o custo da própria Retra, mas não promete tempo
real rígido nem substitui estado transacional crítico de ordens, posições ou risco.
