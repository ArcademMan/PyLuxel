"""pyluxel.audio.manager -- Gestione centralizzata audio: SFX con cache, musica streaming, audio spaziale 2D."""

from __future__ import annotations

import math
import random

import numpy as np
import pygame

from pyluxel.core import paths
from pyluxel.core.pak import asset_open, asset_exists
from pyluxel.debug import cprint


class SoundManager:
    """Carica, cacha e riproduce effetti sonori e musica.

    Segue il pattern di TextureManager (load/cache/release) con in piu'
    volume master/sfx/music, mute e audio spaziale 2D.
    """

    def __init__(self):
        self._sfx_path: str = ""
        self._music_path: str = ""
        self._cache: dict[str, pygame.mixer.Sound] = {}
        self._master_volume: float = 1.0
        self._sfx_volume: float = 1.0
        self._music_volume: float = 1.0
        self._muted: bool = False
        self._pre_mute_master: float = 1.0
        self._current_music: str | None = None

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def init(self, sfx_path: str = "assets/sfx",
             music_path: str = "assets/music") -> None:
        """Configura le directory base per SFX e musica.

        Chiamare dopo ``pygame.init()`` (o dopo ``App.__init__``).
        """
        self._sfx_path = sfx_path
        self._music_path = music_path

    # ------------------------------------------------------------------
    # SFX -- load / play / play_at
    # ------------------------------------------------------------------

    def load(self, name: str, filename: str) -> pygame.mixer.Sound:
        """Carica un effetto sonoro da file e lo cacha.

        Parameters
        ----------
        name : str
            Chiave univoca per riferirsi al suono (es. ``"jump"``).
        filename : str
            Nome del file nella directory ``sfx_path`` (es. ``"jump.wav"``).
        """
        if name in self._cache:
            return self._cache[name]

        path = paths.join(self._sfx_path, filename)
        try:
            sound = pygame.mixer.Sound(file=asset_open(path))
            self._cache[name] = sound
            cprint.ok("SoundManager: loaded", name, f"({path})")
            return sound
        except Exception as exc:
            cprint.error("SoundManager: failed to load", name, "-", exc)
            raise

    def play(self, name: str, volume: float = 1.0,
             pitch_var: float = 0.0,
             volume_var: float = 0.0) -> pygame.mixer.Channel | None:
        """Riproduce un SFX precedentemente caricato.

        Parameters
        ----------
        name : str
            Chiave del suono (passata a ``load``).
        volume : float
            Volume locale 0.0 - 1.0 (moltiplicato per master * sfx).
        pitch_var : float
            Variazione pitch casuale (0.1 = ±10%). 0 = nessuna variazione.
        volume_var : float
            Variazione volume casuale (0.05 = ±5%). 0 = nessuna variazione.

        Returns
        -------
        Channel | None
            Il canale su cui e' in riproduzione, o ``None`` se non disponibile.
        """
        sound = self._cache.get(name)
        if sound is None:
            cprint.warning("SoundManager: sound not loaded:", name)
            return None

        vol = volume
        if volume_var > 0:
            vol *= 1.0 + random.uniform(-volume_var, volume_var)

        effective = max(0.0, min(1.0, vol * self._sfx_volume * self._master_volume))

        if pitch_var > 0:
            sound = self._resample(sound, pitch_var)

        sound.set_volume(effective)
        channel = sound.play()
        return channel

    def play_at(self, name: str, x: float, y: float,
                listener_x: float, listener_y: float,
                max_distance: float = 500.0,
                volume: float = 1.0,
                pitch_var: float = 0.0,
                volume_var: float = 0.0) -> pygame.mixer.Channel | None:
        """Riproduce un SFX con attenuazione e pan spaziale 2D.

        Parameters
        ----------
        name : str
            Chiave del suono.
        x, y : float
            Posizione della sorgente sonora (design space).
        listener_x, listener_y : float
            Posizione dell'ascoltatore (tipicamente camera o player).
        max_distance : float
            Distanza oltre la quale il suono non e' udibile.
        volume : float
            Volume base 0.0 - 1.0.
        pitch_var : float
            Variazione pitch casuale (0.1 = ±10%). 0 = nessuna variazione.
        volume_var : float
            Variazione volume casuale (0.05 = ±5%). 0 = nessuna variazione.

        Returns
        -------
        Channel | None
            Il canale su cui e' in riproduzione, o ``None``.
        """
        sound = self._cache.get(name)
        if sound is None:
            cprint.warning("SoundManager: sound not loaded:", name)
            return None

        dx = x - listener_x
        dy = y - listener_y
        distance = math.hypot(dx, dy)

        if distance >= max_distance:
            return None

        vol = volume
        if volume_var > 0:
            vol *= 1.0 + random.uniform(-volume_var, volume_var)

        # Attenuazione lineare
        attenuation = 1.0 - distance / max_distance
        effective = vol * attenuation * self._sfx_volume * self._master_volume

        if effective <= 0.0:
            return None

        # Pan stereo: -1.0 (sinistra) .. +1.0 (destra)
        pan = max(-1.0, min(1.0, dx / max_distance))
        left = max(0.0, min(1.0, effective * (1.0 - pan)))
        right = max(0.0, min(1.0, effective * (1.0 + pan)))

        if pitch_var > 0:
            sound = self._resample(sound, pitch_var)

        sound.set_volume(1.0)  # volume gestito dal canale
        channel = sound.play()
        if channel is not None:
            channel.set_volume(left, right)
        return channel

    def stop_all_sfx(self) -> None:
        """Ferma tutti i canali SFX in riproduzione."""
        pygame.mixer.stop()

    # ------------------------------------------------------------------
    # Music
    # ------------------------------------------------------------------

    def play_music(self, name: str, *, loop: bool = True,
                   fade_in: float = 0.0) -> None:
        """Avvia una traccia musicale (streaming, una alla volta).

        Parameters
        ----------
        name : str
            Nome del file nella directory ``music_path`` (senza path, es. ``"theme"``).
            Cerca automaticamente estensioni ``.ogg``, ``.mp3``, ``.wav``.
        loop : bool
            Ripeti all'infinito (default True).
        fade_in : float
            Secondi di fade in (0 = immediato).
        """
        path = self._resolve_music(name)
        if path is None:
            cprint.error("SoundManager: music not found:", name)
            return

        try:
            pygame.mixer.music.load(asset_open(path))
            pygame.mixer.music.set_volume(self._music_volume * self._master_volume)
            loops = -1 if loop else 0
            if fade_in > 0:
                pygame.mixer.music.play(loops, fade_ms=int(fade_in * 1000))
            else:
                pygame.mixer.music.play(loops)
            self._current_music = name
            cprint.ok("SoundManager: playing music", name)
        except Exception as exc:
            cprint.error("SoundManager: failed to play music", name, "-", exc)

    def stop_music(self, fade_out: float = 0.0) -> None:
        """Ferma la musica.

        Parameters
        ----------
        fade_out : float
            Secondi di fade out (0 = immediato).
        """
        if fade_out > 0:
            pygame.mixer.music.fadeout(int(fade_out * 1000))
        else:
            pygame.mixer.music.stop()
        self._current_music = None

    def pause_music(self) -> None:
        """Mette in pausa la musica."""
        pygame.mixer.music.pause()

    def resume_music(self) -> None:
        """Riprende la musica dopo una pausa."""
        pygame.mixer.music.unpause()

    # ------------------------------------------------------------------
    # Volume
    # ------------------------------------------------------------------

    def set_master_volume(self, vol: float) -> None:
        """Imposta il volume master (0.0 - 1.0). Scala tutto."""
        self._master_volume = max(0.0, min(1.0, vol))
        self._apply_music_volume()

    def set_sfx_volume(self, vol: float) -> None:
        """Imposta il volume base degli SFX (0.0 - 1.0)."""
        self._sfx_volume = max(0.0, min(1.0, vol))

    def set_music_volume(self, vol: float) -> None:
        """Imposta il volume della musica (0.0 - 1.0)."""
        self._music_volume = max(0.0, min(1.0, vol))
        self._apply_music_volume()

    def mute(self) -> None:
        """Silenzia tutto (conserva il volume precedente)."""
        if not self._muted:
            self._pre_mute_master = self._master_volume
            self._muted = True
            self._master_volume = 0.0
            self._apply_music_volume()

    def is_muted(self) -> bool:
        """True se l'audio e' silenziato."""
        return self._muted

    def get_master_volume(self) -> float:
        """Ritorna il volume master corrente."""
        return self._master_volume

    def get_sfx_volume(self) -> float:
        """Ritorna il volume SFX corrente."""
        return self._sfx_volume

    def get_music_volume(self) -> float:
        """Ritorna il volume musica corrente."""
        return self._music_volume

    def is_music_playing(self) -> bool:
        """True se la musica e' in riproduzione."""
        return pygame.mixer.music.get_busy()

    def get_current_music(self) -> str | None:
        """Ritorna il nome della traccia musicale corrente, o None."""
        return self._current_music

    def is_sound_loaded(self, name: str) -> bool:
        """True se un suono e' caricato in cache."""
        return name in self._cache

    def get_loaded_sounds(self) -> list[str]:
        """Ritorna la lista dei nomi dei suoni caricati."""
        return list(self._cache.keys())

    def unmute(self) -> None:
        """Ripristina il volume precedente al mute."""
        if self._muted:
            self._muted = False
            self._master_volume = self._pre_mute_master
            self._apply_music_volume()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def release(self, name: str) -> None:
        """Rilascia un singolo SFX dalla cache."""
        if name in self._cache:
            self._cache[name].stop()
            del self._cache[name]

    def release_all(self) -> None:
        """Ferma tutto e rilascia tutte le risorse audio."""
        pygame.mixer.music.stop()
        pygame.mixer.stop()
        self._cache.clear()
        self._current_music = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _resample(sound: pygame.mixer.Sound,
                  pitch_var: float) -> pygame.mixer.Sound:
        """Crea una copia del suono con pitch randomizzato via resampling numpy."""
        factor = 1.0 + random.uniform(-pitch_var, pitch_var)
        factor = max(0.5, min(2.0, factor))  # clamp di sicurezza

        samples = pygame.sndarray.array(sound)
        n = len(samples)
        new_n = int(n / factor)
        if new_n < 2 or new_n == n:
            return sound

        old_idx = np.arange(n, dtype=np.float32)
        new_idx = np.linspace(0, n - 1, new_n, dtype=np.float32)

        if samples.ndim == 1:
            resampled = np.interp(new_idx, old_idx, samples).astype(samples.dtype)
        else:
            # Stereo: resample ogni canale
            channels = []
            for ch in range(samples.shape[1]):
                channels.append(
                    np.interp(new_idx, old_idx, samples[:, ch]).astype(samples.dtype)
                )
            resampled = np.column_stack(channels)

        return pygame.sndarray.make_sound(resampled)

    def _apply_music_volume(self) -> None:
        """Applica il volume effettivo alla musica in riproduzione."""
        effective = self._music_volume * self._master_volume
        pygame.mixer.music.set_volume(max(0.0, min(1.0, effective)))

    def _resolve_music(self, name: str) -> str | None:
        """Trova il file musicale cercando estensioni comuni."""
        # Se il nome ha gia' un'estensione, prova direttamente
        base = paths.join(self._music_path, name)
        if paths.extension(name):
            return base if asset_exists(base) else None

        for ext in (".ogg", ".mp3", ".wav", ".flac"):
            path = base + ext
            if asset_exists(path):
                return path
        return None
