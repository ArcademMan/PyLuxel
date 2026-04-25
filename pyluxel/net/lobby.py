"""pyluxel.net.lobby -- Gestione lobby/stanze.

Per UDP usa un sistema di codici (base36 di ip:port).
Per Steam wrappa ISteamMatchmaking (lobby native, inviti, "Join Game").
"""

import socket
import struct
import sys
from typing import Callable

from pyluxel.debug import cprint


def _ip_to_code(ip: str, port: int) -> str:
    """Converti IP:port in un codice breve (base36)."""
    parts = ip.split(".")
    num = 0
    for p in parts:
        num = (num << 8) | int(p)
    num = (num << 16) | port

    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if num == 0:
        return "0"
    result = []
    while num > 0:
        result.append(chars[num % 36])
        num //= 36
    return "".join(reversed(result))


def _code_to_ip(code: str) -> tuple[str, int]:
    """Decodifica un codice base36 in (ip, port)."""
    chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    num = 0
    for c in code.upper():
        num = num * 36 + chars.index(c)

    port = num & 0xFFFF
    num >>= 16
    parts = []
    for _ in range(4):
        parts.append(str(num & 0xFF))
        num >>= 8
    ip = ".".join(reversed(parts))
    return ip, port


class LobbyManager:
    """Gestore lobby. Funziona con UDP (codici) e Steam (lobby native).

    Con Steam:
    - ``create()`` crea una Steam Lobby visibile agli amici
    - Gli amici vedono "Join Game" nella friends list di Steam
    - ``invite(steam_id)`` invia un invito diretto
    - ``get_friends()`` ritorna la lista amici online
    - ``get_members()`` ritorna chi e' nella lobby

    Con UDP:
    - ``create()`` genera un codice da condividere
    - ``join_code(code)`` decodifica il codice e connette
    """

    def __init__(self, net_manager):
        self._net = net_manager
        self._name: str = ""
        self._max_players: int = 4
        self._code: str | None = None
        self._in_lobby: bool = False
        self._on_created: list[Callable] = []
        self._on_joined: list[Callable] = []

    def create(self, name: str = "", max_players: int = 4, *,
               public: bool = False,
               on_created: Callable | None = None) -> None:
        """Crea una lobby e avvia l'host.

        Con Steam: crea una Steam Lobby (visibile agli amici di default).
        Con UDP: genera un codice da condividere manualmente.

        Args:
            name: Nome della stanza.
            max_players: Numero massimo di giocatori.
            public: Se True, lobby pubblica (visibile a tutti). Default: solo amici.
            on_created: Callback fn(lobby_id, result) chiamata quando la lobby
                e' pronta. lobby_id e' l'ID della lobby, result e' 1 se ok.
        """
        self._name = name or "PyLuxel Game"
        self._max_players = max_players

        if on_created:
            self._on_created.append(on_created)

        # Avvia host se non gia' connesso
        if not self._net.is_connected:
            self._net.host()

        transport = self._net._transport
        transport_kind = self._net._transport_kind

        if transport_kind == "steam" and hasattr(transport, "create_lobby"):
            # Steam: crea lobby nativa
            from pyluxel.net.transport_steam import (
                LOBBY_TYPE_PUBLIC, LOBBY_TYPE_FRIENDS_ONLY)

            lobby_type = LOBBY_TYPE_PUBLIC if public else LOBBY_TYPE_FRIENDS_ONLY

            def _on_lobby_created(lobby_id):
                transport.set_lobby_data("name", self._name)
                transport.set_lobby_data("max_players", str(max_players))
                self._code = str(lobby_id)
                self._in_lobby = True
                # Rich Presence: abilita "Unisciti" su Steam
                if hasattr(transport, "set_rich_presence"):
                    transport.set_rich_presence("connect", str(lobby_id))
                    transport.set_rich_presence("status", "In Lobby")
                cprint.ok(f"Lobby Steam creata: {self._name} "
                          f"(ID: {lobby_id})")
                for cb in self._on_created:
                    try:
                        cb(lobby_id, 1)
                    except Exception as e:
                        cprint.warning(f"Lobby on_created error: {e}")
                self._on_created.clear()

            transport.create_lobby(lobby_type, max_players,
                                   callback=_on_lobby_created)
        else:
            # UDP: genera codice
            if transport:
                _, port = transport.get_local_address()
                try:
                    ip = _get_local_ip()
                except Exception:
                    ip = "127.0.0.1"
                self._code = _ip_to_code(ip, port)

            self._in_lobby = True
            cprint.info(f"Lobby creata: {self._name} | Codice: {self._code}")

            # lobby_id: per UDP usiamo il codice, per Steam l'ID numerico
            _lobby_id = self._code or ""
            for cb in self._on_created:
                try:
                    cb(_lobby_id, 1)
                except Exception as e:
                    cprint.warning(f"Lobby on_created error: {e}")
            self._on_created.clear()

    def join_code(self, code: str, *,
                  on_joined: Callable | None = None) -> None:
        """Unisciti a una lobby tramite codice.

        Per UDP: decodifica il codice base36 in IP:port.
        Per Steam: il codice e' il lobby_id numerico.

        Args:
            code: Codice lobby (UDP: "A3X7K", Steam: "12345678").
            on_joined: Callback fn() chiamata quando il join e' completato.
        """
        if on_joined:
            self._on_joined.append(on_joined)

        transport_kind = self._net._transport_kind

        if transport_kind == "steam" or (
                not transport_kind
                and self._net._transport is None
                and self._net._default_transport == "steam"):
            # Steam: il codice e' il lobby_id
            try:
                lobby_id = int(code)
            except ValueError:
                cprint.error(f"Codice lobby Steam non valido: {code}")
                return

            if self._net._transport is None:
                # Crea il transport Steam senza hosting
                transport = self._net._create_transport("steam", 480)
                self._net._transport = transport
                self._net._transport_kind = "steam"
                # Inizializza Steam (lazy)
                transport._init_steam()

            transport = self._net._transport
            self._net._is_host = False
            self._net._connected = True

            if hasattr(transport, "join_lobby"):
                net = self._net

                def _on_lobby_joined(lid):
                    self._in_lobby = True
                    self._code = str(lid)
                    # Aggiorna local_id dal transport
                    if hasattr(transport, "local_id"):
                        net._local_id = transport.local_id
                    # Rich Presence
                    if hasattr(transport, "set_rich_presence"):
                        transport.set_rich_presence("connect", str(lid))
                        transport.set_rich_presence("status", "In Game")
                    for cb in self._on_joined:
                        try:
                            cb(lid, 1)
                        except Exception as e:
                            cprint.warning(f"Lobby on_joined error: {e}")
                    self._on_joined.clear()

                transport.join_lobby(lobby_id, callback=_on_lobby_joined)
                cprint.info(f"Joining Steam lobby {lobby_id}...")
            return

        # UDP: decodifica codice
        try:
            ip, port = _code_to_ip(code)
        except (ValueError, IndexError):
            cprint.error(f"Codice lobby non valido: {code}")
            return

        if not self._net.is_connected:
            transport = self._net._transport_kind or "udp"
            self._net.join(ip, port, transport=transport)

        self._in_lobby = True
        cprint.info(f"Joining lobby con codice {code} -> {ip}:{port}")

        for cb in self._on_joined:
            try:
                cb(code, 1)
            except Exception as e:
                cprint.warning(f"Lobby on_joined error: {e}")
        self._on_joined.clear()

    def invite(self, steam_id: int) -> bool:
        """Invita un amico alla lobby (solo Steam).

        L'amico riceve una notifica nell'overlay Steam e puo'
        cliccare per unirsi direttamente.

        Args:
            steam_id: Steam ID dell'amico.

        Returns:
            True se l'invito e' stato inviato.
        """
        transport = self._net._transport
        if hasattr(transport, "invite_friend"):
            return transport.invite_friend(steam_id)
        cprint.warning("Lobby.invite() richiede transport Steam")
        return False

    def leave(self) -> None:
        """Esci dalla lobby."""
        if self._in_lobby:
            transport = self._net._transport
            if hasattr(transport, "clear_rich_presence"):
                transport.clear_rich_presence()
            if hasattr(transport, "leave_lobby"):
                transport.leave_lobby()
            self._net.disconnect()
            self._in_lobby = False
            self._code = None

    def get_friends(self) -> list[dict]:
        """Ritorna la lista amici Steam online (solo Steam).

        Returns:
            Lista di dict: ``[{"steam_id": int, "name": str,
                              "state": int, "online": bool}, ...]``
        """
        transport = self._net._transport
        if hasattr(transport, "get_friend_list"):
            return transport.get_friend_list()
        return []

    def get_members(self) -> list[dict]:
        """Ritorna i membri della lobby corrente (solo Steam).

        Returns:
            Lista di dict: ``[{"steam_id": int, "name": str,
                              "is_host": bool}, ...]``
        """
        transport = self._net._transport
        if hasattr(transport, "get_lobby_members"):
            return transport.get_lobby_members()
        return []

    def show_invite_overlay(self) -> None:
        """Apre l'overlay Steam per invitare amici alla lobby.

        Funziona solo con transport Steam e una lobby attiva.
        """
        transport = self._net._transport
        if hasattr(transport, "show_invite_overlay"):
            transport.show_invite_overlay()
        else:
            cprint.warning("Lobby.show_invite_overlay() richiede transport Steam")

    def check_launch_args(self) -> str | None:
        """Cerca ``+connect_lobby <id>`` negli argomenti di lancio.

        Steam passa questo argomento quando un utente clicca "Unisciti"
        dal profilo di un amico o accetta un invito.

        Returns:
            Il lobby ID come stringa, o None se non trovato.
        """
        for i, arg in enumerate(sys.argv):
            if arg == "+connect_lobby" and i + 1 < len(sys.argv):
                return sys.argv[i + 1]
        return None

    def set_data(self, key: str, value: str) -> bool:
        """Imposta metadata nella lobby (solo Steam).

        Visibile a tutti i membri. Utile per game mode, mappa, ecc.
        """
        transport = self._net._transport
        if hasattr(transport, "set_lobby_data"):
            return transport.set_lobby_data(key, value)
        return False

    def get_data(self, key: str) -> str:
        """Legge metadata dalla lobby (solo Steam)."""
        transport = self._net._transport
        if hasattr(transport, "get_lobby_data"):
            return transport.get_lobby_data(key)
        return ""

    @property
    def code(self) -> str | None:
        """Codice della lobby.

        UDP: codice base36 (es. "A3X7K").
        Steam: lobby ID come stringa (es. "109775241052639").
        """
        return self._code

    @property
    def name(self) -> str:
        return self._name

    @property
    def max_players(self) -> int:
        return self._max_players

    @property
    def player_count(self) -> int:
        return self._net.peer_count + (1 if self._net.is_connected else 0)

    @property
    def is_in_lobby(self) -> bool:
        return self._in_lobby

    @property
    def is_full(self) -> bool:
        return self.player_count >= self._max_players

    @property
    def is_steam(self) -> bool:
        """True se la lobby usa Steam."""
        return self._net._transport_kind == "steam"


def _get_local_ip() -> str:
    """Ottieni l'IP locale della macchina."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()
