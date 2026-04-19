"""
Persistencia da memoria da campanha em arquivo JSON.
"""
import json
import os
from threading import Lock
from datetime import datetime

_LOCK = Lock()
MEMORIA_PATH = os.path.join(os.path.dirname(__file__), "data", "memoria.json")


def _estrutura_vazia():
    return {
        "itens": [],
        "locais": [],
        "personagens": [],
        "eventos": []
    }


def carregar():
    """Le a memoria do disco. Retorna estrutura vazia se nao existir."""
    with _LOCK:
        if not os.path.exists(MEMORIA_PATH):
            return _estrutura_vazia()
        try:
            with open(MEMORIA_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Garante que todas as chaves existem (compat com versoes antigas)
            base = _estrutura_vazia()
            base.update(data)
            return base
        except (json.JSONDecodeError, OSError):
            return _estrutura_vazia()


def _salvar(memoria: dict):
    os.makedirs(os.path.dirname(MEMORIA_PATH), exist_ok=True)
    with open(MEMORIA_PATH, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)


def adicionar(novas_anotacoes: dict):
    """
    Recebe a saida JSON do agente anotador e concatena na memoria existente.
    Adiciona timestamp em cada entrada nova.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    with _LOCK:
        memoria = carregar()
        for chave in ("itens", "locais", "personagens", "eventos"):
            for entrada in novas_anotacoes.get(chave, []):
                entrada["_adicionado_em"] = ts
                memoria[chave].append(entrada)
        _salvar(memoria)
        return memoria


def limpar():
    with _LOCK:
        _salvar(_estrutura_vazia())
        return _estrutura_vazia()


def resumo_para_netrunner() -> str:
    """
    Serializa a memoria num formato compacto para injetar no prompt do netrunner.
    """
    mem = carregar()
    if not any(mem[k] for k in mem):
        return "(memoria vazia — nenhuma anotacao ainda)"

    linhas = []
    if mem["itens"]:
        linhas.append("ITENS:")
        for i in mem["itens"]:
            linhas.append(f"  - {i['nome']} ({i['tipo']}): {i['descricao']}")
    if mem["locais"]:
        linhas.append("LOCAIS:")
        for l in mem["locais"]:
            linhas.append(f"  - {l['nome']} ({l['tipo']}): {l['descricao']}")
    if mem["personagens"]:
        linhas.append("PERSONAGENS:")
        for p in mem["personagens"]:
            linhas.append(f"  - {p['nome']} ({p['papel']}, {p['relacao']}): {p['descricao']}")
    if mem["eventos"]:
        linhas.append("EVENTOS:")
        for e in mem["eventos"]:
            linhas.append(f"  - {e['titulo']}: {e['resumo']}")
    return "\n".join(linhas)
