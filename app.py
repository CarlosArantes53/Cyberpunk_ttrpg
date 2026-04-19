"""
Assistente de RPG Cyberpunk — Flask + Gemini API

Rotas:
  GET  /                      — interface com abas
  POST /api/mestre/upload     — upload do PDF de regras
  POST /api/mestre/perguntar  — pergunta ao juiz de regras
  POST /api/anotador          — extrai entidades em JSON e salva
  GET  /api/memoria           — retorna memoria atual
  POST /api/memoria/limpar    — zera a memoria
  POST /api/netrunner         — conversa com a IA netrunner (usa memoria)
"""
import os
import json
import tempfile
import mimetypes
from flask import Flask, request, jsonify, render_template, Response
from dotenv import load_dotenv
from google import genai
from google.genai import types
from faster_whisper import WhisperModel

import memoria
import prompts
import tts as tts_module
from schema import ANOTADOR_SCHEMA

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")

# Carregado sob demanda na primeira chamada de transcrição
_whisper = None

def get_whisper():
    global _whisper
    if _whisper is None:
        _whisper = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _whisper

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY nao definida. Copie .env.example para .env e preencha."
    )

client = genai.Client(api_key=API_KEY)

# Estado em memoria: referencia para o PDF de regras ja carregado no Gemini
# (File API retorna um handle que pode ser reutilizado entre chamadas)
_regras_file = None

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB


# =============================================================================
# TTS — Kokoro ONNX (PT-BR)
# =============================================================================
@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    data = request.get_json(force=True)
    text = (data.get("texto") or "").strip()
    voice = data.get("voz", "pf_dora")
    speed = float(data.get("velocidade", 1.0))

    if not text:
        return jsonify({"erro": "texto vazio"}), 400
    if voice not in ("pf_dora", "pm_alex"):
        return jsonify({"erro": "voz inválida, use pf_dora ou pm_alex"}), 400

    try:
        wav_bytes = tts_module.synthesize(text, voice=voice, speed=speed)
        return Response(wav_bytes, mimetype="audio/wav")
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# =============================================================================
# Transcrição — Faster Whisper
# =============================================================================
@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    if "audio" not in request.files:
        return jsonify({"erro": "Envie o audio no campo 'audio'"}), 400

    audio_file = request.files["audio"]
    suffix = ".webm"
    if audio_file.filename and "." in audio_file.filename:
        suffix = "." + audio_file.filename.rsplit(".", 1)[-1]

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = tmp.name
        audio_file.save(tmp_path)

    try:
        model = get_whisper()
        segments, _ = model.transcribe(tmp_path, language="pt", beam_size=5)
        texto = " ".join(seg.text.strip() for seg in segments).strip()
        return jsonify({"texto": texto})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500
    finally:
        os.unlink(tmp_path)


# =============================================================================
# Frontend
# =============================================================================
@app.route("/")
def index():
    return render_template("index.html")
@app.route("/regras-combate")
def regras_combate():
    return render_template("Regras_Combate_Cyberpunk.html")

@app.route("/regras-habilidades")
def regras_habilidades():
    return render_template("Regras_Habilidades_Cyberpunk.html")


# =============================================================================
# AGENTE 1 — Mestre
# =============================================================================
@app.route("/api/mestre/upload", methods=["POST"])
def upload_regras():
    """Faz upload do PDF de regras para a File API do Gemini."""
    global _regras_file

    if "pdf" not in request.files:
        return jsonify({"erro": "Envie o PDF no campo 'pdf'"}), 400

    arquivo = request.files["pdf"]
    if not arquivo.filename:
        return jsonify({"erro": "Arquivo sem nome"}), 400

    # Salva temporariamente e envia pra File API do Gemini
    tmp_path = os.path.join("data", "regras_tmp.pdf")
    os.makedirs("data", exist_ok=True)
    arquivo.save(tmp_path)

    try:
        _regras_file = client.files.upload(file=tmp_path)
        return jsonify({
            "status": "ok",
            "nome": arquivo.filename,
            "file_id": _regras_file.name
        })
    except Exception as e:
        return jsonify({"erro": f"Falha no upload: {e}"}), 500


@app.route("/api/mestre/perguntar", methods=["POST"])
def perguntar_mestre():
    data = request.get_json(force=True)
    pergunta = (data.get("pergunta") or "").strip()
    if not pergunta:
        return jsonify({"erro": "pergunta vazia"}), 400

    # Monta os contents: se houver PDF carregado, inclui
    contents = []
    if _regras_file is not None:
        contents.append(_regras_file)
    contents.append(pergunta)

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=prompts.MESTRE_PROMPT,
                temperature=0.3,
            ),
        )
        return jsonify({
            "resposta": resp.text,
            "tem_regras_carregadas": _regras_file is not None
        })
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


# =============================================================================
# AGENTE 2 — Anotador (saida estruturada)
# =============================================================================
@app.route("/api/anotador", methods=["POST"])
def anotar():
    data = request.get_json(force=True)
    descricao = (data.get("descricao") or "").strip()
    if not descricao:
        return jsonify({"erro": "descricao vazia"}), 400

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=descricao,
            config=types.GenerateContentConfig(
                system_instruction=prompts.ANOTADOR_PROMPT,
                response_mime_type="application/json",
                response_json_schema=ANOTADOR_SCHEMA,
                temperature=0.1,
            ),
        )
        extraido = json.loads(resp.text)
        memoria_atualizada = memoria.adicionar(extraido)
        return jsonify({
            "extraido": extraido,
            "memoria_total": memoria_atualizada
        })
    except json.JSONDecodeError as e:
        return jsonify({"erro": f"JSON invalido: {e}", "raw": resp.text}), 500
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


@app.route("/api/memoria", methods=["GET"])
def ver_memoria():
    return jsonify(memoria.carregar())


@app.route("/api/memoria/limpar", methods=["POST"])
def limpar_memoria():
    memoria.limpar()
    return jsonify({"status": "memoria zerada"})


# =============================================================================
# AGENTE 3 — Netrunner (usa memoria)
# =============================================================================
@app.route("/api/netrunner", methods=["POST"])
def netrunner():
    data = request.get_json(force=True)
    mensagem = (data.get("mensagem") or "").strip()
    historico = data.get("historico", [])  # lista de {role, text}

    if not mensagem:
        return jsonify({"erro": "mensagem vazia"}), 400

    # Monta prompt com memoria injetada
    mem_texto = memoria.resumo_para_netrunner()
    system_instruction = prompts.netrunner_prompt(mem_texto)

    # Reconstroi historico no formato do SDK
    contents = []
    for turno in historico:
        role = turno.get("role", "user")
        # SDK aceita role "user" ou "model"
        if role not in ("user", "model"):
            role = "user"
        contents.append(types.Content(
            role=role,
            parts=[types.Part.from_text(text=turno.get("text", ""))]
        ))
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=mensagem)]
    ))

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.9,  # mais criatividade pra narrativa
            ),
        )
        return jsonify({"resposta": resp.text})
    except Exception as e:
        return jsonify({"erro": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
