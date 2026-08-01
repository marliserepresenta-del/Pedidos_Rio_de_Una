# Pedidos TOTVS para Google Planilhas

Aplicativo Streamlit para ler um ou vários relatórios PDF **Pedidos de Suprimentos em Aberto**, consolidar os itens, remover duplicidades e armazenar cada envio no Supabase.

Como o relatório não informa o preço unitário, o aplicativo calcula a coluna `valor_unitario` dividindo `valor_item` por `quantidade`, com quatro casas decimais.

A aba **Visão geral** reúne indicadores de valor e quantidade, análises por produto, loja, ano e mês/ano, filtros de período e demais campos do pedido, tabela detalhada e download do resultado filtrado em CSV. O período começa automaticamente na menor data de emissão disponível e termina na maior.

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Configurar o Supabase

1. Crie um projeto Supabase e preencha `[supabase]` com a Project URL e a publishable key.
2. Abra o **SQL Editor** do Supabase, cole todo o conteúdo de `schema.sql` e execute uma vez.
3. Em **Authentication**, mantenha o provedor Email habilitado.

Para o botão **Esqueci minha senha**, configure o template **Reset password** do Supabase com este link:

```text
{{ .SiteURL }}?token_hash={{ .TokenHash }}&type=recovery
```

O primeiro cadastro com `ricardo.lidio@yahoo.com.br` fica ativo automaticamente. Os demais ficam pendentes até aprovação. Todos os usuários ativos são administradores e o banco impede mais de quatro contas ativas.

O login permanece ativo por até 30 dias, inclusive depois de atualizar ou reabrir o navegador. Somente o token de renovação criptografado é guardado; a senha nunca é armazenada. O botão **Sair** apaga a sessão persistente.

O arquivo real de secrets é ignorado pelo Git. Nunca publique o Client Secret no repositório.

## Publicar com GitHub e Streamlit Community Cloud

1. Crie um repositório no GitHub e envie esta pasta.
2. No Streamlit Community Cloud, escolha **Create app**, selecione o repositório e informe `app.py` como arquivo principal.
3. Em **Advanced settings → Secrets**, cole o conteúdo do seu `secrets.toml`.
4. No Supabase Authentication, cadastre `https://SEU-APP.streamlit.app` como Site URL.
5. Faça o deploy e teste o cadastro, a aprovação e um PDF.

## Como a duplicidade é evitada

Cada item recebe `id_registro`, uma chave SHA-256 calculada com todas as colunas, exceto `id_registro` e `arquivo`. O banco usa essa chave como identificador único global, impedindo reinserção em envios posteriores. Cada lote registra quantos itens foram incluídos e quantos foram ignorados como duplicados.
