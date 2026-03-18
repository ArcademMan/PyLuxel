"""pyluxel.net.node -- NetNode, base class per oggetti sincronizzati."""


class NetNode:
    """Classe base per oggetti sincronizzati in rete.

    Formalizza il contratto implicito richiesto da NetworkManager.register():
    ogni oggetto registrato deve avere ``_net_owner`` e ``_net_dirty``.
    """

    def __init__(self, owner: int):
        self._net_owner = owner
        self._net_dirty: set[str] = set()
        self._net_type_name: str = ""
