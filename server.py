import os
import json
import logging
import datetime
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import firebase_admin
from firebase_admin import credentials, db, auth
from matchmaker import Matchmaker

# Configuração de Logs Profissionais
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'revival_secret_key_132!')

# Inicializa o SocketIO para conexões de baixa latência em tempo real
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent' if os.environ.get('PORT') else 'threading')
server_matchmaker = Matchmaker()

# ==================== CONEXÃO SEGURA FIREBASE ====================
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

# ==================== ROTAS DA API NORMAL (HTTP) ====================

@app.route('/')
def status():
    return jsonify({
        "status": "online",
        "engine": "Project Revival Core",
        "version": "3.0.0-PRO",
        "active_games": len(server_matchmaker.obter_salas())
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
            return jsonify({"success": False, "msg": "Conta não registrada no jogo."}), 404

        if player.get('banido', False):
            return jsonify({"success": False, "msg": "Esta conta encontra-se BANIDA."}), 403

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

# ==================== ENGINE EM TEMPO REAL (WEBSOCKETS) ====================

@socketio.on('join_game_lobby')
def on_join(data):
    """Acionado quando o celular do jogador entra no lobby de uma partida."""
    sala_id = data.get('sala_id')
    uid = data.get('uid')
    nick = data.get('nick', 'Jogador')
    
    join_room(sala_id)
    resultado = server_matchmaker.entrar_na_sala(sala_id, uid, nick)
    
    if resultado["success"]:
        # Atualiza o espelho no Firebase para o Painel Web Administrativo acompanhar
        db.reference(f'lobby_global/{sala_id}').set(resultado["sala"])
        # Alerta todos na sala de que um novo oponente entrou
        emit('player_joined', {"nick": nick, "uid": uid, "sala": resultado["sala"]}, to=sala_id)
    else:
        emit('error', {"msg": resultado["msg"]})

@socketio.on('update_position')
def on_move(data):
    """Recebe a posição X,Y,Z do jogador e replica para todos os outros na partida instantaneamente."""
    sala_id = data.get('sala_id')
    uid = data.get('uid')
    x, y, z = data.get('x'), data.get('y'), data.get('z')
    
    player_data = server_matchmaker.processar_movimento(sala_id, uid, x, y, z)
    if player_data:
        # Envia a nova posição apenas para os outros jogadores da mesma sala
        emit('player_moved', {"uid": uid, "posicao": player_data["posicao"]}, to=sala_id, include_self=False)

@socketio.on('fire_weapon')
def on_fire(data):
    """Processa o disparo de um tiro e calcula se houve acerto crítico."""
    sala_id = data.get('sala_id')
    atacante_uid = data.get('uid')
    vitima_uid = data.get('vitima_uid')
    dano = data.get('dano', 25)
    
    sala_atualizada = server_matchmaker.processar_dano(sala_id, atacante_uid, vitima_uid, dano)
    if sala_atualizada:
        db.reference(f'lobby_global/{sala_id}').set(sala_atualizada)
        emit('match_state_update', sala_atualizada, to=sala_id)

@socketio.on('disconnect_player')
def on_disconnect(data):
    sala_id = data.get('sala_id')
    uid = data.get('uid')
    leave_room(sala_id)
    logging.info(f"Jogador {uid} saiu da sala de partida {sala_id}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Inicia o servidor com suporte a WebSockets ativos
    socketio.run(app, host='0.0.0.0', port=port)
  
