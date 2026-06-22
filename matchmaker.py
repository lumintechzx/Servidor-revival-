import uuid
import datetime
import logging

class Matchmaker:
    def __init__(self):
        self.active_rooms = {}

    def criar_sala_combate(self, host_uid, host_nick, nome_sala, mapa):
        """Gera uma sala de partida com ID único de 6 dígitos estilo Free Fire."""
        sala_id = str(uuid.uuid4().int)[:6] 
        
        nova_sala = {
            "sala_id": sala_id,
            "host_uid": host_uid,
            "host_nick": host_nick,
            "nome_sala": nome_sala,
            "mapa": mapa,
            "status": "LOBBY",  # LOBBY, EM_PARTIDA, FINALIZADA
            "safe_zone_radius": 500.0,
            "jogadores": {
                host_uid: {
                    "nick": host_nick,
                    "hp": 100,
                    "kills": 0,
                    "status": "VIVO", # VIVO, ABATIDO, DESCONECTADO
                    "posicao": {"x": 0.0, "y": 0.0, "z": 0.0}
                }
            },
            "max_players": 48,
            "criada_em": datetime.datetime.utcnow().isoformat()
        }
        
        self.active_rooms[sala_id] = nova_sala
        return nova_sala

    def entrar_na_sala(self, sala_id, player_uid, player_nick):
        """Adiciona um jogador ao lobby da sala."""
        if sala_id not in self.active_rooms:
            return {"success": False, "msg": "Sala não encontrada."}
        
        sala = self.active_rooms[sala_id]
        
        if len(sala["jogadores"]) >= sala["max_players"]:
            return {"success": False, "msg": "Sala cheia."}
            
        if sala["status"] != "LOBBY":
            return {"success": False, "msg": "A partida já começou."}

        sala["jogadores"][player_uid] = {
            "nick": player_nick,
            "hp": 100,
            "kills": 0,
            "status": "VIVO",
            "posicao": {"x": 0.0, "y": 0.0, "z": 0.0}
        }
        return {"success": True, "sala": sala}

    def processar_movimento(self, sala_id, player_uid, x, y, z):
        """Atualiza a posição 3D do player no servidor de partida."""
        if sala_id in self.active_rooms:
            sala = self.active_rooms[sala_id]
            if player_uid in sala["jogadores"]:
                sala["jogadores"][player_uid]["posicao"] = {"x": float(x), "y": float(y), "z": float(z)}
                return sala["jogadores"][player_uid]
        return None

    def processar_dano(self, sala_id, atacante_uid, vitima_uid, dano):
        """Aplica dano de tiro e computa abates (Kills)."""
        if sala_id not in self.active_rooms:
            return None
            
        sala = self.active_rooms[sala_id]
        if atacante_uid not in sala["jogadores"] or vitima_uid not in sala["jogadores"]:
            return None
            
        vitima = sala["jogadores"][vitima_uid]
        if vitima["status"] != "VIVO":
            return {"msg": "Alvo já eliminado."}

        vitima["hp"] = max(0, vitima["hp"] - int(dano))
        
        if vitima["hp"] == 0:
            vitima["status"] = "ABATIDO"
            sala["jogadores"][atacante_uid]["kills"] += 1
            logging.info(f"[COMBATE] {sala['jogadores'][atacante_uid]['nick']} abateu {vitima['nick']}")

        return sala

    def obter_salas(self):
        return self.active_rooms
        
