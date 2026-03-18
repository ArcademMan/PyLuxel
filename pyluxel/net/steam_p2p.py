"""pyluxel.net.steam_p2p -- ctypes wrapper per ISteamNetworkingMessages.

Usa ISteamNetworkingMessages v002 (API moderna) con relay SDR di Valve.
Sostituisce la vecchia ISteamNetworking (deprecata).

Interfaccia invariata: send/receive/accept_session/close_session.

Richiede che Steam sia gia' inizializzato (via SteamAPI).
"""

import ctypes

from pyluxel.debug import cprint

# ── Send flags (ISteamNetworkingMessages) ──
_SEND_UNRELIABLE = 0
_SEND_RELIABLE = 8

# ── SteamNetworkingIdentity ──
# Layout: [m_eType: i32] [m_cbSize: i32] [union: 128 bytes] = 136 bytes
_IDENTITY_SIZE = 136

# ── SteamNetworkingMessage_t offsets (64-bit) ──
# [0]  void* m_pData
# [8]  int   m_cbSize
# [12] u32   m_conn
# [16] SteamNetworkingIdentity m_identityPeer (136 bytes)
_MSG_OFF_DATA = 0
_MSG_OFF_SIZE = 8
_MSG_OFF_IDENTITY = 16


class SteamP2P:
    """Wrapper ctypes per Steam P2P networking (ISteamNetworkingMessages)."""

    def __init__(self, dll: ctypes.CDLL | None = None):
        self._dll = dll
        self._msg = None   # ISteamNetworkingMessages*
        self._ready = False

        # Cache SteamNetworkingIdentity per steam_id (evita rebuild ogni send)
        self._identity_cache: dict[int, ctypes.Array] = {}

        # Riferimento forte al callback ctypes (impedisce GC)
        self._session_request_cb = None

    def init(self) -> bool:
        """Inizializza. Steam deve essere gia' avviato (SteamAPI_Init)."""
        if self._dll is None:
            cprint.error("SteamP2P: DLL non fornita")
            return False

        self._msg = self._get_messages_ptr()
        if not self._msg:
            cprint.error("SteamP2P: ISteamNetworkingMessages pointer NULL "
                         "(Steam non inizializzato?)")
            return False

        self._setup_functions()
        self._init_relay()
        self._register_session_callback()
        self._ready = True
        cprint.ok("SteamP2P: NetworkingMessages pronto (SDR relay)")
        return True

    # ------------------------------------------------------------------
    # Public API (interfaccia invariata rispetto alla vecchia ISteamNetworking)
    # ------------------------------------------------------------------

    @property
    def is_ready(self) -> bool:
        return self._ready

    def send(self, steam_id: int, data: bytes,
             reliable: bool = True, channel: int = 0) -> bool:
        """Invia un messaggio P2P a uno Steam ID."""
        if not self._ready:
            return False
        identity = self._get_identity(steam_id)
        flags = _SEND_RELIABLE if reliable else _SEND_UNRELIABLE
        buf = ctypes.create_string_buffer(data, len(data))
        result = self._fn_send(
            self._msg,
            ctypes.cast(identity, ctypes.c_void_p),
            buf, ctypes.c_uint32(len(data)),
            ctypes.c_int(flags), ctypes.c_int(channel))
        return result == 1  # k_EResultOK

    def receive(self, channel: int = 0,
                max_count: int = 64) -> list[tuple[int, bytes]]:
        """Leggi tutti i messaggi in coda su un canale.

        Returns:
            Lista di (steam_id_mittente, dati).
        """
        if not self._ready:
            return []

        messages = []
        msg_ptrs = (ctypes.c_void_p * max_count)()

        try:
            count = self._fn_receive(
                self._msg,
                ctypes.c_int(channel),
                msg_ptrs,
                ctypes.c_int(max_count))

            for i in range(count):
                ptr = msg_ptrs[i]
                if not ptr:
                    continue
                try:
                    # m_pData (void*) at offset 0
                    data_ptr = ctypes.c_void_p.from_address(
                        ptr + _MSG_OFF_DATA).value
                    # m_cbSize (int32) at offset 8
                    data_size = ctypes.c_int32.from_address(
                        ptr + _MSG_OFF_SIZE).value
                    # m_identityPeer at offset 16 -> GetSteamID64
                    sender_id = self._fn_get_identity_steamid(
                        ctypes.c_void_p(ptr + _MSG_OFF_IDENTITY))

                    if data_ptr and data_size > 0:
                        buf = (ctypes.c_uint8 * data_size).from_address(
                            data_ptr)
                        messages.append((sender_id, bytes(buf)))
                finally:
                    self._fn_release(ctypes.c_void_p(ptr))

        except Exception as e:
            cprint.error(f"SteamP2P: receive error: {e}")

        return messages

    def accept_session(self, steam_id: int) -> bool:
        """Accetta una sessione con uno Steam ID."""
        if not self._ready:
            return False
        identity = self._get_identity(steam_id)
        result = self._fn_accept(
            self._msg, ctypes.cast(identity, ctypes.c_void_p))
        cprint.ok(f"SteamP2P: AcceptSession({steam_id}) -> {result}")
        return result

    def close_session(self, steam_id: int) -> bool:
        """Chiudi la sessione con uno Steam ID."""
        if not self._ready:
            return False
        identity = self._get_identity(steam_id)
        result = self._fn_close(
            self._msg, ctypes.cast(identity, ctypes.c_void_p))
        self._identity_cache.pop(steam_id, None)
        return result

    # ------------------------------------------------------------------
    # Internal: SteamNetworkingIdentity helpers
    # ------------------------------------------------------------------

    def _get_identity(self, steam_id: int) -> ctypes.Array:
        """Ottieni/crea una SteamNetworkingIdentity per uno steam_id (cached)."""
        identity = self._identity_cache.get(steam_id)
        if identity is None:
            identity = (ctypes.c_uint8 * _IDENTITY_SIZE)()
            self._fn_identity_clear(
                ctypes.cast(identity, ctypes.c_void_p))
            self._fn_identity_set_steamid(
                ctypes.cast(identity, ctypes.c_void_p),
                ctypes.c_uint64(steam_id))
            self._identity_cache[steam_id] = identity
        return identity

    # ------------------------------------------------------------------
    # Internal: interface accessors
    # ------------------------------------------------------------------

    def _get_messages_ptr(self):
        """Ottieni il puntatore ISteamNetworkingMessages*."""
        try:
            fn = self._dll.SteamAPI_SteamNetworkingMessages_SteamAPI_v002
            fn.restype = ctypes.c_void_p
            fn.argtypes = []
            ptr = fn()
            if ptr:
                return ptr
        except (AttributeError, OSError):
            pass
        cprint.error("SteamP2P: accessor ISteamNetworkingMessages non trovato")
        return None

    def _get_utils_ptr(self):
        """Ottieni ISteamNetworkingUtils* (cached)."""
        if hasattr(self, "_utils_ptr"):
            return self._utils_ptr
        try:
            fn = self._dll.SteamAPI_SteamNetworkingUtils_SteamAPI_v004
            fn.restype = ctypes.c_void_p
            fn.argtypes = []
            self._utils_ptr = fn()
        except (AttributeError, OSError):
            self._utils_ptr = None
        return self._utils_ptr

    def _init_relay(self):
        """Inizializza la rete relay SDR di Valve (riduce latenza iniziale)."""
        utils_ptr = self._get_utils_ptr()
        if not utils_ptr:
            return
        try:
            fn_init = self._dll.SteamAPI_ISteamNetworkingUtils_InitRelayNetworkAccess
            fn_init.restype = None
            fn_init.argtypes = [ctypes.c_void_p]
            fn_init(utils_ptr)
            cprint.info("SteamP2P: relay network access inizializzato")
        except (AttributeError, OSError) as e:
            cprint.warning(f"SteamP2P: InitRelayNetworkAccess fallito: {e}")

    def _register_session_callback(self):
        """Registra global callback per auto-accettare sessioni in arrivo.

        Con ISteamNetworkingMessages, quando un peer invia un messaggio
        senza una sessione attiva, Steam genera un
        SteamNetworkingMessagesSessionRequest_t. Senza un handler,
        Steam fallisce con assertion 'Invalid pipe handle'.
        """
        utils_ptr = self._get_utils_ptr()
        if not utils_ptr:
            cprint.warning("SteamP2P: impossibile registrare session callback "
                           "(NetworkingUtils non disponibile)")
            return

        # Callback signature: void fn(SteamNetworkingMessagesSessionRequest_t*)
        # La struct contiene solo una SteamNetworkingIdentity (136 bytes)
        CALLBACK_TYPE = ctypes.CFUNCTYPE(None, ctypes.c_void_p)

        msg_ptr = self._msg
        fn_accept = self._fn_accept
        fn_get_sid = self._fn_get_identity_steamid

        def _on_session_request(info_ptr):
            # info_ptr punta a SteamNetworkingMessagesSessionRequest_t
            # che inizia con m_identityRemote (SteamNetworkingIdentity)
            steam_id = fn_get_sid(info_ptr)
            cprint.info(f"SteamP2P: auto-accept session from {steam_id}")
            fn_accept(msg_ptr, info_ptr)

        # Salva riferimento forte (impedisce GC del callback ctypes)
        self._session_request_cb = CALLBACK_TYPE(_on_session_request)

        try:
            fn_set = self._dll.SteamAPI_ISteamNetworkingUtils_SetGlobalCallback_MessagesSessionRequest
            fn_set.restype = ctypes.c_bool
            fn_set.argtypes = [ctypes.c_void_p, CALLBACK_TYPE]
            ok = fn_set(utils_ptr, self._session_request_cb)
            if ok:
                cprint.ok("SteamP2P: session request callback registrato")
            else:
                cprint.warning("SteamP2P: SetGlobalCallback_MessagesSessionRequest "
                               "ritornato False")
        except (AttributeError, OSError) as e:
            cprint.warning(f"SteamP2P: session callback fallito: {e}")

    def _setup_functions(self):
        """Configura le firme ctypes per ISteamNetworkingMessages."""
        dll = self._dll
        VP = ctypes.c_void_p
        U32 = ctypes.c_uint32
        U64 = ctypes.c_uint64
        I32 = ctypes.c_int
        BOOL = ctypes.c_bool

        # ── ISteamNetworkingMessages ──

        # SendMessageToUser(self, identity*, data, size, flags, channel) -> EResult
        self._fn_send = dll.SteamAPI_ISteamNetworkingMessages_SendMessageToUser
        self._fn_send.restype = I32
        self._fn_send.argtypes = [VP, VP, VP, U32, I32, I32]

        # ReceiveMessagesOnChannel(self, channel, ppOut, max) -> count
        self._fn_receive = dll.SteamAPI_ISteamNetworkingMessages_ReceiveMessagesOnChannel
        self._fn_receive.restype = I32
        self._fn_receive.argtypes = [VP, I32, ctypes.POINTER(VP), I32]

        # AcceptSessionWithUser(self, identity*) -> bool
        self._fn_accept = dll.SteamAPI_ISteamNetworkingMessages_AcceptSessionWithUser
        self._fn_accept.restype = BOOL
        self._fn_accept.argtypes = [VP, VP]

        # CloseSessionWithUser(self, identity*) -> bool
        self._fn_close = dll.SteamAPI_ISteamNetworkingMessages_CloseSessionWithUser
        self._fn_close.restype = BOOL
        self._fn_close.argtypes = [VP, VP]

        # ── SteamNetworkingMessage_t ──

        # Release(msg*) -> void
        self._fn_release = dll.SteamAPI_SteamNetworkingMessage_t_Release
        self._fn_release.restype = None
        self._fn_release.argtypes = [VP]

        # ── SteamNetworkingIdentity helpers ──

        self._fn_identity_clear = dll.SteamAPI_SteamNetworkingIdentity_Clear
        self._fn_identity_clear.restype = None
        self._fn_identity_clear.argtypes = [VP]

        self._fn_identity_set_steamid = dll.SteamAPI_SteamNetworkingIdentity_SetSteamID64
        self._fn_identity_set_steamid.restype = None
        self._fn_identity_set_steamid.argtypes = [VP, U64]

        self._fn_get_identity_steamid = dll.SteamAPI_SteamNetworkingIdentity_GetSteamID64
        self._fn_get_identity_steamid.restype = U64
        self._fn_get_identity_steamid.argtypes = [VP]
