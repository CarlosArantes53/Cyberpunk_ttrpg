# Night City RPG Assistant

Assistente Flask + Gemini para mesas de **Cyberpunk RPG**, com 3 agentes:

1. **Mestre** — ingere o PDF das regras e responde dúvidas de mecânica em tempo real.
2. **Anotador** — extrai itens, locais, NPCs e eventos em JSON estruturado e salva em `data/memoria.json`.
3. **Netrunner (ICE-9)** — IA-jogador que hackeia sistemas narrativamente, consultando a memória da campanha.

---

## Setup

```bash
# 1. instale deps
pip install -r requirements.txt

# 2. configure a chave
cp .env.example .env
# edite .env e coloque sua chave de https://aistudio.google.com/app/apikey

# 3. rode
python app.py
```

Acesse `http://localhost:5000`.

---

## Estrutura

```
rpg_assistant/
├── app.py              # Flask + rotas dos 3 agentes
├── prompts.py          # Prompts de sistema de cada persona
├── schema.py           # JSON Schema do anotador (saida estruturada Gemini)
├── memoria.py          # Persistencia em data/memoria.json
├── requirements.txt
├── .env.example
├── templates/
│   └── index.html      # UI com abas, estilo cyberpunk (neon)
└── data/
    └── memoria.json    # gerado automaticamente
```

---

## Fluxo de uso na mesa

1. Antes da sessão, o Mestre carrega o PDF na aba **Mestre**.
2. Durante o jogo, o Mestre consulta regras rapidamente por texto.
3. Depois de cenas importantes, o Mestre (ou um jogador) joga um parágrafo narrativo na aba **Anotador** — a memória da campanha cresce automaticamente.
4. Quando um jogador quer que a IA-netrunner entre em ação, usa a aba **Netrunner**. ICE-9 lembra de tudo que foi anotado e encaixa na narrativa.

---

## Modelo usado

Padrão: `gemini-2.5-flash` (suporta saída estruturada conforme PDF anexado).
Troque em `.env` → `GEMINI_MODEL=gemini-3.1-flash-lite-preview` para testar o preview.

## Notas técnicas

- O PDF das regras é enviado à **File API** do Gemini uma vez e reusado por handle nas perguntas seguintes (não reenviado a cada chamada).
- A saída do anotador usa `response_mime_type="application/json"` + `response_json_schema` — schema estrito com `enum` nos tipos para categorização consistente.
- O netrunner injeta a memória inteira como texto no `system_instruction` a cada chamada (sem vector DB, adequado para campanhas pequenas/médias).
- O estado do PDF carregado é **global em processo** — reinicie o server e recarregue o PDF se derrubar o Flask.
