# Pedidos TOTVS para Google Planilhas

Aplicativo Streamlit para ler um ou vários relatórios PDF **Pedidos de Suprimentos em Aberto**, consolidar os itens, remover duplicidades e adicionar somente registros novos a uma planilha Google.

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Configurar o Google Planilhas

1. No Google Cloud, crie um projeto e ative as APIs **Google Sheets** e **Google Drive**.
2. Crie uma conta de serviço e baixe a chave JSON.
3. Copie os campos da chave para `.streamlit/secrets.toml`, usando o exemplo fornecido.
4. Crie a planilha e compartilhe-a como **Editor** com o e-mail `client_email` da conta de serviço.
5. Informe o nome exato da planilha e da aba em `[google_sheets]`.

O arquivo real de secrets é ignorado pelo Git. Nunca publique a chave JSON no repositório.

## Publicar com GitHub e Streamlit Community Cloud

1. Crie um repositório no GitHub e envie esta pasta.
2. No Streamlit Community Cloud, escolha **Create app**, selecione o repositório e informe `app.py` como arquivo principal.
3. Em **Advanced settings → Secrets**, cole o conteúdo do seu `secrets.toml`.
4. Faça o deploy e teste com um PDF.

## Como a duplicidade é evitada

Cada item recebe `id_registro`, uma chave SHA-256 calculada a partir de empresa, pedido, pedido do fornecedor, código do produto, quantidade e valor. Antes de inserir, o aplicativo lê os IDs que já existem na aba e envia apenas os novos. Arquivos repetidos no mesmo upload também são consolidados.

