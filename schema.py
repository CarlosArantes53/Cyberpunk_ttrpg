"""
Schema de saida estruturada para o agente Anotador.
Segue a especificacao de JSON Schema aceita pela Gemini API:
type, properties, items, required, minItems, maxItems, enum, etc.
"""

ANOTADOR_SCHEMA = {
    "type": "object",
    "properties": {
        "itens": {
            "type": "array",
            "description": "Objetos, armas, cibernetica, drogas, equipamentos",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "tipo": {
                        "type": "string",
                        "enum": ["arma", "armadura", "cibernetica", "droga",
                                 "veiculo", "ferramenta", "dados", "consumivel",
                                 "outro"]
                    },
                    "descricao": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["nome", "tipo", "descricao"]
            }
        },
        "locais": {
            "type": "array",
            "description": "Bares, corporacoes, bairros, edificios",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "tipo": {
                        "type": "string",
                        "enum": ["bar", "corporacao", "bairro", "edificio",
                                 "combat_zone", "clinica", "loja", "rua", "outro"]
                    },
                    "descricao": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["nome", "tipo", "descricao"]
            }
        },
        "personagens": {
            "type": "array",
            "description": "NPCs, contatos, aliados, inimigos",
            "items": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string"},
                    "papel": {
                        "type": "string",
                        "enum": ["fixer", "ripperdoc", "corpo", "netrunner",
                                 "solo", "nomade", "rockerboy", "media",
                                 "techie", "medtech", "lawman", "npc_gerico",
                                 "outro"]
                    },
                    "descricao": {"type": "string"},
                    "relacao": {
                        "type": "string",
                        "enum": ["aliado", "inimigo", "neutro", "contato",
                                 "desconhecido"]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["nome", "papel", "descricao", "relacao"]
            }
        },
        "eventos": {
            "type": "array",
            "description": "Acontecimentos narrativos importantes",
            "items": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "resumo": {"type": "string"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["titulo", "resumo"]
            }
        }
    },
    "required": ["itens", "locais", "personagens", "eventos"]
}
