# Pedidos TOTVS para Google Planilhas

Aplicativo Streamlit para ler um ou vários relatórios PDF **Pedidos de Suprimentos em Aberto**, consolidar os itens, remover duplicidades e criar um novo arquivo Google Planilhas a cada envio finalizado.

## Executar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run app.py
```

## Configurar o Google e o login

1. No Google Cloud, crie um projeto e ative as APIs **Google Sheets** e **Google Drive**.
2. No Google Auth Platform, crie um cliente OAuth do tipo **Aplicativo da Web**.
3. Cadastre `http://localhost:8501` como URI de redirecionamento autorizada para uso local.
4. Preencha `[google_oauth]` com o Client ID, Client Secret, a mesma URI e uma chave aleatória longa em `state_secret`.
5. Cadastre os usuários autorizados em `[access].allowed_emails`.

O login identifica o usuário e solicita autorização para criar a planilha no Drive dele. O aplicativo não recebe nem armazena senhas.

O arquivo real de secrets é ignorado pelo Git. Nunca publique o Client Secret no repositório.

## Publicar com GitHub e Streamlit Community Cloud

1. Crie um repositório no GitHub e envie esta pasta.
2. No Streamlit Community Cloud, escolha **Create app**, selecione o repositório e informe `app.py` como arquivo principal.
3. Cadastre `https://SEU-APP.streamlit.app` como URI OAuth autorizada e atualize `redirect_uri` nos Secrets.
4. Em **Advanced settings → Secrets**, cole o conteúdo do seu `secrets.toml`.
5. Faça o deploy e teste com um PDF.

## Como a duplicidade é evitada

Cada item recebe `id_registro`, uma chave SHA-256 calculada a partir de empresa, pedido, pedido do fornecedor, código do produto, quantidade e valor. Arquivos repetidos dentro do mesmo envio são consolidados antes da criação da planilha.
