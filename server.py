import os
import json
import logging
import datetime
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import firebase_admin
from firebase_admin import credentials, db, auth
from matchmaker import Matchmaker

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'revival_secret_key_777!')

# Configurado de modo simples (o gunicorn vai gerenciar o paralelismo por fora)
socketio = SocketIO(app, cors_allowed_origins="*")
server_matchmaker = Matchmaker()

# ==================== CONFIGURAÇÃO FIREBASE ====================
if os.environ.get('FIREBASE_CREDENTIALS'):
    cred_json = json.loads(os.environ.get('FIREBASE_CREDENTIALS'))
    cred = credentials.Certificate(cred_json)
else:
    try:
        cred = credentials.Certificate("credenciais.json")
    except Exception:
        cred = None

if cred:
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://project-revival-29e2b-default-rtdb.firebaseio.com'
    })

# ==================== ROTAS HTTP (LOBBY/API) ====================

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "engine": "Project Revival Core",
        "version": "3.1.0-STABLE",
        "active_matches": len(server_matchmaker.obter_salas())
    }), 200

@app.route('/api/v1/auth/login', methods=['POST'])
def player_login():
    data = request.get_json() or {}
    email = data.get('email')

    if not email:
        return jsonify({"success": False, "msg": "E-mail ausente."}), 400

    try:
        user = auth.get_user_by_email(email)
        uid = user.uid
        user_ref = db.reference(f'users/{uid}')
        player = user_ref.get()

        if not player:
            return jsonify({"success": False, "msg": "Perfil não encontrado no servidor."}), 404

        if player.get('banido', False):
            return jsonify({"success": False, "msg": "Acesso Suspenso. Esta conta está banida."}), 403

        user_ref.update({
            'status': 'online',
            'ultima_conexao': datetime.datetime.utcnow().isoformat()
        })

        return jsonify({
            "success": True,
            "profile": {
                "uid": uid,
                "nick": player.get('nick', 'Recruta'),
                "nivel": player.get('nivel', 1),
                "ouro": player.get('moedas', 0),
                "diamantes": player.get('diamantes', 0),
                "salas_personalizadas": player.get('salas_personalizadas', 0)
            }
        }), 200
    except Exception as e:
        return jsonify({"success": False, "msg": "Erro de Autenticação.", "error": str(e)}), 401

# ==================== ROTAS WEBSOCKET (REALTIME GAMEPLAY) ====================

@socketio.on('join_game_lobby')
def on_join(data):
    sala_id = data.get('sala_id')
    uid = data.get('uid')
    nick = data.get('nick', 'Jogador')
    
    join_room(sala_id)
    resultado = server_matchmaker.entrar_na_sala(sala_id, uid, nick)
    
    if resultado["success"]:
        db.reference(f'lobby_global/{sala_id}').set(resultado["sala"])
        emit('player_joined', {"nick": nick, "uid": uid, "sala": resultado["sala"]}, to=sala_id)
    else:
        emit('error', {"msg": resultado["msg"]})

@socketio.on('update_position')
def on_move(data):
    sala_id = data.get('sala_id')
    uid = data.get('uid')
    x, y, z = data.get('x'), data.get('y'), data.get('z')
    
    player_data = server_matchmaker.processar_movimento(sala_id, uid, x, y, z)
    if player_data:
        emit('player_moved', {"uid": uid, "posicao": player_data["posicao"]}, to=sala_id, include_self=False)

@socketio.on('fire_weapon')
def on_fire(data):
    sala_id = data.get('sala_id')
    atacante_uid = data.get('uid')
    vitima_uid = data.get('vitima_uid')
    dano = data.get('dano', 25)
    
    sala_atualizada = server_matchmaker.processar_dano(sala_id, atacante_uid, vitima_uid, dano)
    if sala_atualizada:
        db.reference(f'lobby_global/{sala_id}').set(sala_atualizada)
        emit('match_state_update', sala_atualizada, to=sala_id)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
    
