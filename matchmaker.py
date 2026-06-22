import uuid
import datetime
import logging

class Matchmaker:
    def __init__(self):
        self.active_rooms = {}

    def criar_sala_combate(self, host_uid, host_nick, nome_sala, mapa):
        """Gera uma sala de partida única com ID numérico de 6 dígitos estilo FF."""
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
                    "coletes": 1,
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
        """Adiciona um jogador ao lobby de espera se houver vaga."""
        if sala_id not in self.active_rooms:
            return {"success": False, "msg": "Sala de combate não encontrada."}
        
        sala = self.active_rooms[sala_id]
        
        if len(sala["jogadores"]) >= sala["max_players"]:
            return {"success": False, "msg": "Esta sala já atingiu o limite de 48 jogadores."}
            
        if sala["status"] != "LOBBY":
            return {"success": False, "msg": "A partida já está em andamento."}

        sala["jogadores"][player_uid] = {
            "nick": player_nick,
            "hp": 100,
            "coletes": 1,
            "kills": 0,
            "status": "VIVO",
            "posicao": {"x": 0.0, "y": 0.0, "z": 0.0}
        }
        return {"success": True, "sala": sala}

    def processar_movimento(self, sala_id, player_uid, x, y, z):
        """Atualiza a posição do jogador no mapa 3D."""
        if sala_id in self.active_rooms:
            sala = self.active_rooms[sala_id]
            if player_uid in sala["jogadores"]:
                sala["jogadores"][player_uid]["posicao"] = {"x": float(x), "y": float(y), "z": float(z)}
                return sala["jogadores"][player_uid]
        return None

    def processar_dano(self, sala_id, atacante_uid, vitima_uid, dano):
        """Calcula a perda de vida (HP) e computa se houve abate (Kill)."""
        if sala_id not in self.active_rooms:
            return None
            
        sala = self.active_rooms[sala_id]
        if atacante_uid not in sala["jogadores"] or vitima_uid not in sala["jogadores"]:
            return None
            
        vitima = sala["jogadores"][vitima_uid]
        if vitima["status"] != "VIVO":
            return {"msg": "Jogador já está morto."}

        # Aplica o dano recebido pelo tiro
        vitima["hp"] = max(0, vitima["hp"] - int(dano))
        
        # Verifica abate
        if vitima["hp"] == 0:
            vitima["status"] = "ABATIDO"
            sala["jogadores"][atacante_uid]["kills"] += 1
            logging.info(f"[PARTIDA {sala_id}] {sala['jogadores'][atacante_uid]['nick']} ABATEU {vitima['nick']}")

        return sala

    def obter_salas(self):
        return self.active_rooms
      
