"""pyluxel.net.steam_api -- Wrapper ctypes completo per Steamworks flat API.

Sostituisce py_steam_net. Usa la Manual Dispatch API per i callback,
pensata per linguaggi non-C++.

Richiede steam_api64.dll nella directory del gioco + steam_appid.txt.
"""

import ctypes
import ctypes.util
import os
import sys
from typing import Callable

from pyluxel.debug import cprint

# ── Lobby types (ISteamMatchmaking) ──
LOBBY_TYPE_PRIVATE = 0
LOBBY_TYPE_FRIENDS_ONLY = 1
LOBBY_TYPE_PUBLIC = 2
LOBBY_TYPE_INVISIBLE = 3

# ── Callback IDs ──
_CB_LOBBY_ENTER = 504
_CB_LOBBY_CHAT_UPDATE = 506
_CB_LOBBY_CREATED = 513
_CB_P2P_SESSION_REQUEST = 1202
_CB_API_CALL_COMPLETED = 703  # SteamAPICallCompleted_t


# ── Callback structures ──

class _CallbackMsg(ctypes.Structure):
    """CallbackMsg_t -- restituita da ManualDispatch_GetNextCallback."""
    _fields_ = [
        ("m_hSteamUser", ctypes.c_int32),
        ("m_iCallback", ctypes.c_int32),
        ("m_pubParam", ctypes.c_void_p),
        ("m_cubParam", ctypes.c_int32),
    ]


class _LobbyCreated(ctypes.Structure):
    """LobbyCreated_t (ID 513)."""
    _fields_ = [
        ("m_eResult", ctypes.c_int32),
        ("m_ulSteamIDLobby", ctypes.c_uint64),
    ]


class _LobbyEnter(ctypes.Structure):
    """LobbyEnter_t (ID 504)."""
    _fields_ = [
        ("m_ulSteamIDLobby", ctypes.c_uint64),
        ("m_rgfChatPermissions", ctypes.c_uint32),
        ("m_bLocked", ctypes.c_bool),
        ("m_EChatRoomEnterResponse", ctypes.c_uint32),
    ]


class _LobbyChatUpdate(ctypes.Structure):
    """LobbyChatUpdate_t (ID 506)."""
    _fields_ = [
        ("m_ulSteamIDLobby", ctypes.c_uint64),
        ("m_ulSteamIDUserChanged", ctypes.c_uint64),
        ("m_ulSteamIDMakingChange", ctypes.c_uint64),
        ("m_rgfChatMemberStateChange", ctypes.c_uint32),
    ]


class _P2PSessionRequest(ctypes.Structure):
    """P2PSessionRequest_t (ID 1202)."""
    _fields_ = [
        ("m_steamIDRemote", ctypes.c_uint64),
    ]


class _APICallCompleted(ctypes.Structure):
    """SteamAPICallCompleted_t (ID 703) -- segnala che un CallResult e' pronto."""
    _fields_ = [
        ("m_hAsyncCall", ctypes.c_uint64),    # SteamAPICall_t
        ("m_iCallback", ctypes.c_int32),       # callback ID atteso
        ("m_cubParam", ctypes.c_uint32),       # dimensione del risultato
    ]


# ── DLL loading ──

def _find_dll() -> ctypes.CDLL | None:
    """Carica steam_api64.dll."""
    # 1. Gia' in memoria
    for name in ("steam_api64", "steam_api64.dll"):
        try:
            return ctypes.CDLL(name)
        except OSError as e:
            cprint.warning(e)

    # 2. Percorsi espliciti
    dirs = []
    if sys.argv[0]:
        dirs.append(os.path.dirname(os.path.abspath(sys.argv[0])))
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        dirs.append(sys._MEIPASS)
    dirs.append(os.getcwd())

    for d in dirs:
        path = os.path.join(d, "steam_api64.dll")
        if os.path.exists(path):
            try:
                return ctypes.CDLL(path)
            except OSError as e:
                cprint.warning(e)

    cprint.error("SteamAPI: steam_api64.dll non trovata")
    return None


# ── Helpers per trovare interface pointers ──

def _get_accessor(dll, names: list[str]):
    """Prova piu' nomi per un accessor e ritorna il puntatore."""
    for name in names:
        try:
            fn = getattr(dll, name)
            fn.restype = ctypes.c_void_p
            fn.argtypes = []
            ptr = fn()
            if ptr:
                return ptr
        except (AttributeError, OSError):
            continue
    return None


class SteamAPI:
    """Wrapper ctypes per Steamworks: init, user, matchmaking, callbacks.

    Usa la Manual Dispatch API per processare callback e CallResult
    senza bisogno di strutture vtable C++.
    """

    def __init__(self):
        self._dll: ctypes.CDLL | None = None
        self._ready: bool = False
        self._pipe: int = 0  # HSteamPipe

        # Interface pointers
        self._user_ptr = None       # ISteamUser*
        self._matchmaking_ptr = None  # ISteamMatchmaking*
        self._friends_ptr = None    # ISteamFriends*

        # Pending CallResults: {api_call_handle: (expected_cb_id, callback_fn)}
        self._pending_calls: dict[int, tuple[int, Callable]] = {}

        # Broadcast callback listeners: {callback_id: [fn, ...]}
        self._listeners: dict[int, list[Callable]] = {}

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def _dump_dll_exports(self, filters: list[str]):
        """Stampa gli export della DLL che contengono una delle keyword."""
        import struct
        try:
            dll_path = self._dll._name
            with open(dll_path, "rb") as f:
                data = f.read()
            # Parse PE
            pe_off = struct.unpack_from("<I", data, 0x3C)[0]
            export_rva = struct.unpack_from("<I", data, pe_off + 0x78)[0]
            n_sections = struct.unpack_from("<H", data, pe_off + 6)[0]
            sec_off = pe_off + 0x18 + struct.unpack_from("<H", data, pe_off + 0x14)[0]
            # Trova sezione che contiene l'export RVA
            raw_off = 0
            for i in range(n_sections):
                s = sec_off + i * 40
                va = struct.unpack_from("<I", data, s + 12)[0]
                vs = struct.unpack_from("<I", data, s + 8)[0]
                rd = struct.unpack_from("<I", data, s + 20)[0]
                if va <= export_rva < va + vs:
                    raw_off = export_rva - va + rd
                    base_va, base_rd = va, rd
                    break
            if not raw_off:
                return
            n_names = struct.unpack_from("<I", data, raw_off + 24)[0]
            names_rva = struct.unpack_from("<I", data, raw_off + 32)[0]
            names_raw = names_rva - base_va + base_rd
            for i in range(n_names):
                name_rva = struct.unpack_from("<I", data, names_raw + i * 4)[0]
                name_raw = name_rva - base_va + base_rd
                end = data.index(b"\x00", name_raw)
                name = data[name_raw:end].decode("ascii", errors="replace")
                if any(f in name for f in filters):
                    cprint.info(f"DLL export: {name}")
        except Exception as e:
            cprint.warning(f"SteamAPI: export dump fallito: {e}")

    # ------------------------------------------------------------------
    # Init / Shutdown
    # ------------------------------------------------------------------

    def init(self, app_id: int = 480) -> bool:
        """Inizializza Steam API.

        Args:
            app_id: Steam App ID (480 = Spacewar per dev gratuito).

        Returns:
            True se Steam e' pronto.
        """
        if self._ready:
            return True

        # Scrivi steam_appid.txt se non esiste
        _ensure_appid_file(app_id)

        # DLL search path
        _setup_dll_path()

        self._dll = _find_dll()
        if self._dll is None:
            return False

        # SteamAPI_Init (prova InitFlat per SDK recenti, poi Init legacy)
        if not self._steam_init():
            return False

        # Abilita Manual Dispatch
        try:
            fn_md_init = self._dll.SteamAPI_ManualDispatch_Init
            fn_md_init.restype = None
            fn_md_init.argtypes = []
            fn_md_init()
        except (AttributeError, OSError) as e:
            cprint.error(f"SteamAPI: ManualDispatch_Init non trovato: {e}")
            self.shutdown()
            return False

        # HSteamPipe
        try:
            fn_pipe = self._dll.SteamAPI_GetHSteamPipe
            fn_pipe.restype = ctypes.c_int32
            fn_pipe.argtypes = []
            self._pipe = fn_pipe()
            if not self._pipe:
                cprint.error("SteamAPI: HSteamPipe NULL")
                self.shutdown()
                return False
        except (AttributeError, OSError) as e:
            cprint.error(f"SteamAPI: GetHSteamPipe non trovato: {e}")
            self.shutdown()
            return False

        # Ottieni interface pointers
        self._user_ptr = _get_accessor(self._dll, [
            "SteamAPI_SteamUser_v023",
            "SteamAPI_SteamUser_v021",
            "SteamAPI_SteamUser",
        ])
        self._matchmaking_ptr = _get_accessor(self._dll, [
            "SteamAPI_SteamMatchmaking_v009",
            "SteamAPI_SteamMatchmaking",
        ])

        self._friends_ptr = _get_accessor(self._dll, [
            "SteamAPI_SteamFriends_v017",
            "SteamAPI_SteamFriends",
            "SteamFriends",
        ])

        if not self._user_ptr:
            cprint.warning("SteamAPI: ISteamUser pointer NULL")
        if not self._matchmaking_ptr:
            cprint.warning("SteamAPI: ISteamMatchmaking pointer NULL")
        if not self._friends_ptr:
            # Dump export Friends/Persona dalla DLL
            self._dump_dll_exports(["Friend", "Persona"])

            # Prova via SteamInternal_FindOrCreateUserInterface
            try:
                fn_user = self._dll.SteamAPI_GetHSteamUser
                fn_user.restype = ctypes.c_int32
                fn_user.argtypes = []
                h_user = fn_user()

                fn_find = self._dll.SteamInternal_FindOrCreateUserInterface
                fn_find.restype = ctypes.c_void_p
                fn_find.argtypes = [ctypes.c_int32, ctypes.c_char_p]

                for ver in [b"SteamFriends017", b"SteamFriends016", b"SteamFriends015"]:
                    ptr = fn_find(h_user, ver)
                    if ptr:
                        self._friends_ptr = ptr
                        cprint.ok(f"SteamAPI: ISteamFriends ottenuto via FindOrCreate ({ver})")
                        break
            except (AttributeError, OSError) as e:
                cprint.warning(f"SteamAPI: FindOrCreateUserInterface fallito: {e}")

        if not self._friends_ptr:
            cprint.warning("SteamAPI: ISteamFriends non disponibile")

        self._setup_functions()
        self._ready = True
        cprint.ok(f"SteamAPI: inizializzato (App ID {app_id})")
        return True

    def shutdown(self) -> None:
        """Chiudi Steam API."""
        if self._dll:
            try:
                fn = self._dll.SteamAPI_Shutdown
                fn.restype = None
                fn.argtypes = []
                fn()
            except (AttributeError, OSError):
                pass
        self._ready = False
        self._pipe = 0
        self._pending_calls.clear()
        self._listeners.clear()

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def dll(self) -> ctypes.CDLL | None:
        """Accesso alla DLL caricata (per SteamP2P)."""
        return self._dll

    # ------------------------------------------------------------------
    # ISteamUser
    # ------------------------------------------------------------------

    def get_steam_id(self) -> int:
        """Ritorna lo Steam ID locale (uint64)."""
        if not self._ready or not self._user_ptr:
            return 0
        try:
            return self._fn_get_steam_id(self._user_ptr)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # ISteamFriends
    # ------------------------------------------------------------------

    def get_friend_count(self) -> int:
        """Ritorna il numero di amici Steam (flag=0x04, k_EFriendFlagImmediate)."""
        if not self._ready or not self._friends_ptr:
            return 0
        try:
            return self._fn_get_friend_count(self._friends_ptr, 0x04)
        except Exception as e:
            cprint.error(f"SteamAPI.get_friend_count: {e}")
            return 0

    def get_friend_by_index(self, idx: int) -> int:
        """Ritorna lo Steam ID dell'amico all'indice dato."""
        if not self._ready or not self._friends_ptr:
            return 0
        try:
            return self._fn_get_friend_by_index(self._friends_ptr, idx, 0x04)
        except Exception as e:
            cprint.error(f"SteamAPI.get_friend_by_index: {e}")
            return 0

    def get_persona_name(self) -> str:
        """Ritorna il nome del giocatore locale."""
        if not self._ready or not self._friends_ptr:
            cprint.warning(f"SteamAPI.get_persona_name: not ready ({self._ready}) or no friends_ptr ({self._friends_ptr})")
            return ""
        try:
            result = self._fn_get_persona_name(self._friends_ptr)
            if result:
                return result.decode("utf-8", errors="replace")
        except Exception as e:
            cprint.error(f"SteamAPI.get_persona_name: {e}")
        return ""

    def get_friend_persona_name(self, steam_id: int) -> str:
        """Ritorna il nome visualizzato di un utente Steam."""
        if not self._ready or not self._friends_ptr:
            cprint.warning("SteamAPI.get_friend_persona_name: not ready or no friends_ptr")
            return ""
        try:
            result = self._fn_get_friend_persona_name(
                self._friends_ptr, ctypes.c_uint64(steam_id))
            if result:
                return result.decode("utf-8", errors="replace")
        except Exception as e:
            cprint.error(f"SteamAPI.get_friend_persona_name({steam_id}): {e}")
        return ""

    def get_friend_persona_state(self, steam_id: int) -> int:
        """Ritorna lo stato di un utente (0=offline, 1=online, ..., 6=looking_to_trade)."""
        if not self._ready or not self._friends_ptr:
            return 0
        try:
            return self._fn_get_friend_persona_state(
                self._friends_ptr, ctypes.c_uint64(steam_id))
        except Exception as e:
            cprint.error(f"SteamAPI.get_friend_persona_state: {e}")
            return 0

    def set_rich_presence(self, key: str, value: str) -> bool:
        """Imposta una chiave Rich Presence. 'connect' abilita il tasto 'Unisciti'."""
        if not self._ready or not self._friends_ptr:
            return False
        try:
            return self._fn_set_rich_presence(
                self._friends_ptr,
                key.encode("utf-8"),
                value.encode("utf-8"))
        except Exception as e:
            cprint.error(f"SteamAPI.set_rich_presence: {e}")
            return False

    def clear_rich_presence(self) -> None:
        """Rimuovi tutte le chiavi Rich Presence."""
        if not self._ready or not self._friends_ptr:
            return
        try:
            self._fn_clear_rich_presence(self._friends_ptr)
        except Exception as e:
            cprint.error(f"SteamAPI.clear_rich_presence: {e}")

    def activate_invite_overlay(self, lobby_id: int) -> None:
        """Apre l'overlay Steam per invitare amici alla lobby."""
        if not self._ready or not self._friends_ptr:
            return
        try:
            self._fn_activate_invite_overlay(
                self._friends_ptr, ctypes.c_uint64(lobby_id))
        except Exception as e:
            cprint.error(f"SteamAPI.activate_invite_overlay: {e}")

    def invite_user_to_lobby(self, lobby_id: int, steam_id: int) -> bool:
        """Invita un utente specifico alla lobby."""
        if not self._ready or not self._matchmaking_ptr:
            return False
        try:
            return self._fn_invite_user_to_lobby(
                self._matchmaking_ptr,
                ctypes.c_uint64(lobby_id),
                ctypes.c_uint64(steam_id))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # ISteamMatchmaking
    # ------------------------------------------------------------------

    def create_lobby(self, lobby_type: int = LOBBY_TYPE_FRIENDS_ONLY,
                     max_members: int = 4,
                     callback: Callable | None = None) -> None:
        """Crea una lobby Steam.

        Il callback riceve (lobby_id) quando la lobby e' pronta,
        oppure (0) in caso di errore.
        """
        if not self._ready or not self._matchmaking_ptr:
            if callback:
                callback(0)
            return

        try:
            api_call = self._fn_create_lobby(
                self._matchmaking_ptr,
                ctypes.c_int(lobby_type),
                ctypes.c_int(max_members))

            if api_call and api_call != 0:
                if callback:
                    self._pending_calls[api_call] = (_CB_LOBBY_CREATED, callback)
                cprint.info(f"SteamAPI: CreateLobby chiamato (call={api_call})")
            else:
                cprint.error("SteamAPI: CreateLobby ritornato 0")
                if callback:
                    callback(0)
        except Exception as e:
            cprint.error(f"SteamAPI: CreateLobby errore: {e}")
            if callback:
                callback(0)

    def join_lobby(self, lobby_id: int,
                   callback: Callable | None = None) -> None:
        """Entra in una lobby Steam.

        Il callback riceve (lobby_id) quando il join e' completato,
        oppure (0) in caso di errore.
        """
        if not self._ready or not self._matchmaking_ptr:
            if callback:
                callback(0)
            return

        try:
            api_call = self._fn_join_lobby(
                self._matchmaking_ptr,
                ctypes.c_uint64(lobby_id))

            if api_call and api_call != 0:
                if callback:
                    self._pending_calls[api_call] = (_CB_LOBBY_ENTER, callback)
                cprint.info(f"SteamAPI: JoinLobby chiamato (call={api_call})")
            else:
                cprint.error("SteamAPI: JoinLobby ritornato 0")
                if callback:
                    callback(0)
        except Exception as e:
            cprint.error(f"SteamAPI: JoinLobby errore: {e}")
            if callback:
                callback(0)

    def leave_lobby(self, lobby_id: int) -> None:
        """Esci da una lobby."""
        if not self._ready or not self._matchmaking_ptr:
            return
        try:
            self._fn_leave_lobby(self._matchmaking_ptr,
                                 ctypes.c_uint64(lobby_id))
        except Exception as e:
            cprint.warning(f"SteamAPI: LeaveLobby errore: {e}")

    def set_lobby_data(self, lobby_id: int, key: str, value: str) -> bool:
        """Imposta un dato nella lobby (visibile a tutti i membri)."""
        if not self._ready or not self._matchmaking_ptr:
            return False
        try:
            return self._fn_set_lobby_data(
                self._matchmaking_ptr,
                ctypes.c_uint64(lobby_id),
                key.encode("utf-8"),
                value.encode("utf-8"))
        except Exception:
            return False

    def get_lobby_data(self, lobby_id: int, key: str) -> str:
        """Leggi un dato dalla lobby."""
        if not self._ready or not self._matchmaking_ptr:
            return ""
        try:
            result = self._fn_get_lobby_data(
                self._matchmaking_ptr,
                ctypes.c_uint64(lobby_id),
                key.encode("utf-8"))
            if result:
                return result.decode("utf-8")
        except Exception:
            pass
        return ""

    def get_lobby_members(self, lobby_id: int) -> list[int]:
        """Ritorna la lista di Steam ID dei membri della lobby."""
        if not self._ready or not self._matchmaking_ptr:
            return []
        try:
            count = self._fn_get_num_lobby_members(
                self._matchmaking_ptr,
                ctypes.c_uint64(lobby_id))
            members = []
            for i in range(count):
                sid = self._fn_get_lobby_member_by_index(
                    self._matchmaking_ptr,
                    ctypes.c_uint64(lobby_id),
                    ctypes.c_int(i))
                if sid:
                    members.append(sid)
            return members
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Callback system (Manual Dispatch)
    # ------------------------------------------------------------------

    def on(self, callback_id: int, fn: Callable) -> None:
        """Registra un listener per un callback ID specifico.

        Callback IDs comuni:
            504: LobbyEnter_t
            506: LobbyChatUpdate_t
            513: LobbyCreated_t
            1202: P2PSessionRequest_t
        """
        self._listeners.setdefault(callback_id, []).append(fn)

    def on_lobby_changed(self, fn: Callable) -> None:
        """Registra callback per cambiamenti nella lobby (join/leave)."""
        self.on(_CB_LOBBY_CHAT_UPDATE, fn)

    def on_p2p_request(self, fn: Callable) -> None:
        """Registra callback per richieste P2P in arrivo."""
        self.on(_CB_P2P_SESSION_REQUEST, fn)

    def run_callbacks(self) -> None:
        """Processa tutti i callback Steam pendenti.

        Chiamare ogni frame (o almeno 20 volte al secondo).
        Usa la Manual Dispatch API per evitare vtable C++.
        """
        if not self._ready or not self._pipe:
            return

        # 1. Run frame
        try:
            self._fn_run_frame(ctypes.c_int32(self._pipe))
        except Exception as e:
            cprint.error(f"SteamAPI: RunFrame errore: {e}")
            return

        # 2. Process broadcast callbacks
        msg = _CallbackMsg()
        while True:
            try:
                has_cb = self._fn_get_next_callback(
                    ctypes.c_int32(self._pipe),
                    ctypes.byref(msg))
            except Exception:
                break

            if not has_cb:
                break

            try:
                self._dispatch_callback(msg)
            except Exception as e:
                cprint.warning(f"SteamAPI: callback dispatch error: {e}")
            finally:
                try:
                    self._fn_free_callback(ctypes.c_int32(self._pipe))
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal: Steam init
    # ------------------------------------------------------------------

    def _steam_init(self) -> bool:
        """Chiama SteamAPI_InitFlat (SDK 1.57+) o SteamAPI_Init (legacy)."""
        dll = self._dll

        # 1. SteamAPI_InitFlat (SDK 1.57+)
        #    ESteamAPIInitResult SteamAPI_InitFlat(SteamErrMsg *pOutErrMsg)
        #    SteamErrMsg = char[1024], ritorna 0 = OK
        try:
            fn = dll.SteamAPI_InitFlat
            fn.restype = ctypes.c_int
            fn.argtypes = [ctypes.c_char_p]
            err_buf = ctypes.create_string_buffer(1024)
            result = fn(err_buf)
            if result == 0:
                return True
            err_msg = err_buf.value.decode("utf-8", errors="replace")
            cprint.error(f"SteamAPI: InitFlat fallito ({result}): {err_msg}")
            return False
        except (AttributeError, OSError):
            pass

        # 2. SteamAPI_Init (legacy, SDK < 1.57)
        try:
            fn = dll.SteamAPI_Init
            fn.restype = ctypes.c_bool
            fn.argtypes = []
            if fn():
                return True
            cprint.error("SteamAPI: SteamAPI_Init() fallito. "
                         "Steam aperto e loggato?")
            return False
        except (AttributeError, OSError):
            pass

        cprint.error("SteamAPI: nessuna funzione Init trovata nella DLL")
        return False

    # ------------------------------------------------------------------
    # Internal: callback dispatch
    # ------------------------------------------------------------------

    def _dispatch_callback(self, msg: _CallbackMsg) -> None:
        """Dispatcha un singolo callback."""
        cb_id = msg.m_iCallback

        # SteamAPICallCompleted_t (ID 703) = un CallResult e' pronto
        if cb_id == _CB_API_CALL_COMPLETED:
            if msg.m_cubParam >= ctypes.sizeof(_APICallCompleted):
                info = _APICallCompleted.from_address(msg.m_pubParam)
                self._handle_call_result(info.m_hAsyncCall, info.m_iCallback)
            return

        # Broadcast a listeners registrati
        listeners = self._listeners.get(cb_id, [])
        if not listeners:
            return

        if cb_id == _CB_LOBBY_CHAT_UPDATE and msg.m_cubParam >= ctypes.sizeof(_LobbyChatUpdate):
            data = _LobbyChatUpdate.from_address(msg.m_pubParam)
            for fn in listeners:
                try:
                    fn(data.m_ulSteamIDLobby,
                       data.m_ulSteamIDUserChanged,
                       data.m_ulSteamIDMakingChange,
                       data.m_rgfChatMemberStateChange)
                except Exception as e:
                    cprint.warning(f"SteamAPI: lobby_changed listener error: {e}")

        elif cb_id == _CB_P2P_SESSION_REQUEST and msg.m_cubParam >= ctypes.sizeof(_P2PSessionRequest):
            data = _P2PSessionRequest.from_address(msg.m_pubParam)
            for fn in listeners:
                try:
                    fn(data.m_steamIDRemote)
                except Exception as e:
                    cprint.warning(f"SteamAPI: p2p_request listener error: {e}")

    def _handle_call_result(self, api_call: int, actual_cb_id: int) -> None:
        """Leggi il risultato di un CallResult completato via ManualDispatch."""
        pending = self._pending_calls.pop(api_call, None)
        if pending is None:
            return  # Non era un nostro CallResult

        expected_id, callback = pending
        failed = ctypes.c_bool(False)

        if expected_id == _CB_LOBBY_CREATED:
            result = _LobbyCreated()
            try:
                ok = self._fn_get_call_result(
                    ctypes.c_int32(self._pipe),
                    ctypes.c_uint64(api_call),
                    ctypes.byref(result),
                    ctypes.c_int(ctypes.sizeof(result)),
                    ctypes.c_int(expected_id),
                    ctypes.byref(failed))
                if ok and not failed.value and result.m_eResult == 1:
                    callback(result.m_ulSteamIDLobby)
                else:
                    cprint.warning(f"SteamAPI: CreateLobby result="
                                   f"{result.m_eResult}, failed={failed.value}")
                    callback(0)
            except Exception as e:
                cprint.error(f"SteamAPI: GetCallResult error: {e}")
                callback(0)

        elif expected_id == _CB_LOBBY_ENTER:
            result = _LobbyEnter()
            try:
                ok = self._fn_get_call_result(
                    ctypes.c_int32(self._pipe),
                    ctypes.c_uint64(api_call),
                    ctypes.byref(result),
                    ctypes.c_int(ctypes.sizeof(result)),
                    ctypes.c_int(expected_id),
                    ctypes.byref(failed))
                if ok and not failed.value:
                    callback(result.m_ulSteamIDLobby)
                else:
                    callback(0)
            except Exception as e:
                cprint.error(f"SteamAPI: GetCallResult error: {e}")
                callback(0)

        else:
            # CallResult non gestito
            cprint.warning(f"SteamAPI: CallResult non gestito (id={expected_id})")

    # ------------------------------------------------------------------
    # Internal: setup ctypes function signatures
    # ------------------------------------------------------------------

    def _setup_functions(self) -> None:
        """Configura le firme ctypes per tutte le funzioni usate."""
        dll = self._dll
        VP = ctypes.c_void_p
        U64 = ctypes.c_uint64
        I32 = ctypes.c_int32
        INT = ctypes.c_int
        BOOL = ctypes.c_bool

        # ── Manual Dispatch ──
        self._fn_run_frame = dll.SteamAPI_ManualDispatch_RunFrame
        self._fn_run_frame.restype = None
        self._fn_run_frame.argtypes = [I32]

        self._fn_get_next_callback = dll.SteamAPI_ManualDispatch_GetNextCallback
        self._fn_get_next_callback.restype = BOOL
        self._fn_get_next_callback.argtypes = [I32, ctypes.POINTER(_CallbackMsg)]

        self._fn_free_callback = dll.SteamAPI_ManualDispatch_FreeLastCallback
        self._fn_free_callback.restype = None
        self._fn_free_callback.argtypes = [I32]

        self._fn_get_call_result = dll.SteamAPI_ManualDispatch_GetAPICallResult
        self._fn_get_call_result.restype = BOOL
        self._fn_get_call_result.argtypes = [I32, U64, VP, INT, INT,
                                             ctypes.POINTER(ctypes.c_bool)]

        # ── ISteamUser ──
        if self._user_ptr:
            self._fn_get_steam_id = dll.SteamAPI_ISteamUser_GetSteamID
            self._fn_get_steam_id.restype = U64
            self._fn_get_steam_id.argtypes = [VP]

        # ── ISteamMatchmaking ──
        if self._matchmaking_ptr:
            self._fn_create_lobby = dll.SteamAPI_ISteamMatchmaking_CreateLobby
            self._fn_create_lobby.restype = U64  # SteamAPICall_t
            self._fn_create_lobby.argtypes = [VP, INT, INT]

            self._fn_join_lobby = dll.SteamAPI_ISteamMatchmaking_JoinLobby
            self._fn_join_lobby.restype = U64  # SteamAPICall_t
            self._fn_join_lobby.argtypes = [VP, U64]

            self._fn_leave_lobby = dll.SteamAPI_ISteamMatchmaking_LeaveLobby
            self._fn_leave_lobby.restype = None
            self._fn_leave_lobby.argtypes = [VP, U64]

            self._fn_set_lobby_data = dll.SteamAPI_ISteamMatchmaking_SetLobbyData
            self._fn_set_lobby_data.restype = BOOL
            self._fn_set_lobby_data.argtypes = [VP, U64, ctypes.c_char_p,
                                                 ctypes.c_char_p]

            self._fn_get_lobby_data = dll.SteamAPI_ISteamMatchmaking_GetLobbyData
            self._fn_get_lobby_data.restype = ctypes.c_char_p
            self._fn_get_lobby_data.argtypes = [VP, U64, ctypes.c_char_p]

            self._fn_get_num_lobby_members = dll.SteamAPI_ISteamMatchmaking_GetNumLobbyMembers
            self._fn_get_num_lobby_members.restype = INT
            self._fn_get_num_lobby_members.argtypes = [VP, U64]

            self._fn_get_lobby_member_by_index = dll.SteamAPI_ISteamMatchmaking_GetLobbyMemberByIndex
            self._fn_get_lobby_member_by_index.restype = U64
            self._fn_get_lobby_member_by_index.argtypes = [VP, U64, INT]

            self._fn_invite_user_to_lobby = dll.SteamAPI_ISteamMatchmaking_InviteUserToLobby
            self._fn_invite_user_to_lobby.restype = BOOL
            self._fn_invite_user_to_lobby.argtypes = [VP, U64, U64]

        # ── ISteamFriends ──
        # Le funzioni flat API non richiedono il puntatore all'interfaccia
        # quando l'accessor non e' disponibile nella DLL.
        if self._friends_ptr:
            # Modalita' con puntatore
            self._fn_get_friend_count = dll.SteamAPI_ISteamFriends_GetFriendCount
            self._fn_get_friend_count.restype = INT
            self._fn_get_friend_count.argtypes = [VP, INT]

            self._fn_get_friend_by_index = dll.SteamAPI_ISteamFriends_GetFriendByIndex
            self._fn_get_friend_by_index.restype = U64
            self._fn_get_friend_by_index.argtypes = [VP, INT, INT]

            self._fn_get_persona_name = dll.SteamAPI_ISteamFriends_GetPersonaName
            self._fn_get_persona_name.restype = ctypes.c_char_p
            self._fn_get_persona_name.argtypes = [VP]

            self._fn_get_friend_persona_name = dll.SteamAPI_ISteamFriends_GetFriendPersonaName
            self._fn_get_friend_persona_name.restype = ctypes.c_char_p
            self._fn_get_friend_persona_name.argtypes = [VP, U64]

            self._fn_get_friend_persona_state = dll.SteamAPI_ISteamFriends_GetFriendPersonaState
            self._fn_get_friend_persona_state.restype = INT
            self._fn_get_friend_persona_state.argtypes = [VP, U64]

            self._fn_set_rich_presence = dll.SteamAPI_ISteamFriends_SetRichPresence
            self._fn_set_rich_presence.restype = BOOL
            self._fn_set_rich_presence.argtypes = [VP, ctypes.c_char_p, ctypes.c_char_p]

            self._fn_clear_rich_presence = dll.SteamAPI_ISteamFriends_ClearRichPresence
            self._fn_clear_rich_presence.restype = None
            self._fn_clear_rich_presence.argtypes = [VP]


# ── Module-level helpers ──

def _setup_dll_path() -> None:
    """Aggiunge la directory dello script al PATH per trovare la DLL."""
    script_dir = (os.path.dirname(os.path.abspath(sys.argv[0]))
                  if sys.argv[0] else os.getcwd())
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(script_dir)
        except OSError:
            pass
    if script_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = script_dir + os.pathsep + os.environ.get("PATH", "")


def _ensure_appid_file(app_id: int) -> None:
    """Crea steam_appid.txt se non esiste (serve a Steam per il dev)."""
    script_dir = (os.path.dirname(os.path.abspath(sys.argv[0]))
                  if sys.argv[0] else os.getcwd())
    path = os.path.join(script_dir, "steam_appid.txt")
    if not os.path.exists(path):
        try:
            with open(path, "w") as f:
                f.write(str(app_id))
        except OSError:
            pass
