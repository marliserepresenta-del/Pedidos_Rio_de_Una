# Pedidos TOTVS para Google Planilhas

Aplicativo Streamlit para ler um ou vários relatórios PDF **Pedidos de Suprimentos em Aberto**, consolidar os itens, remover duplicidades e armazenar cada envio no Supabase.

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

O primeiro cadastro com `ricardo.lidio@yahoo.com.br` fica ativo automaticamente. Os demais ficam pendentes até aprovação. Todos os usuários ativos são administradores e o banco impede mais de quatro contas ativas.

O arquivo real de secrets é ignorado pelo Git. Nunca publique o Client Secret no repositório.

## Publicar com GitHub e Streamlit Community Cloud

1. Crie um repositório no GitHub e envie esta pasta.
2. No Streamlit Community Cloud, escolha **Create app**, selecione o repositório e informe `app.py` como arquivo principal.
3. Em **Advanced settings → Secrets**, cole o conteúdo do seu `secrets.toml`.
4. No Supabase Authentication, cadastre `https://SEU-APP.streamlit.app` como Site URL.
5. Faça o deploy e teste o cadastro, a aprovação e um PDF.

## Como a duplicidade é evitada

Cada item recebe `id_registro`, uma chave SHA-256 calculada com todas as colunas, exceto `id_registro` e `arquivo`. O banco usa essa chave como identificador único global, impedindo reinserção em envios posteriores. Cada lote registra quantos itens foram incluídos e quantos foram ignorados como duplicados.
