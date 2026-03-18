# Asset PAK System

Sistema per impacchettare gli asset di gioco in un singolo file `.pak` offuscato, proteggendo i file da modifiche casuali dei giocatori.

## Come funziona

- **Dev mode**: nessun `.pak` presente, gli asset vengono letti da disco normalmente
- **Build mode**: `data.pak` accanto all'eseguibile, gli asset vengono letti dal pak in memoria
- **Formato**: zip standard con XOR ciclico applicato all'intero file

Il sistema e' trasparente: il codice del gioco non cambia tra dev e build.

## Creare un .pak

Da terminale, nella root del progetto:

```bash
# Impacchetta tutta la cartella assets/
pyluxel pak assets/

# Output personalizzato
pyluxel pak assets/ -o game_data.pak

# Escludi directory (es. cache, temp)
pyluxel pak assets/ --exclude cache --exclude temp

# Chiave XOR personalizzata
pyluxel pak assets/ --key "LaMiaChiaveSegreta"
```

Funziona anche con `python -m pyluxel pak assets/`.

## Auto-detection

`App.__init__` cerca automaticamente `data.pak` nella stessa directory dell'eseguibile (`sys.argv[0]`). Se lo trova, lo carica. Non serve nessuna configurazione.

Per usare un pak con nome o posizione diversa, chiamare manualmente:

```python
from pyluxel import init_pak

init_pak("percorso/al/mio.pak")
# oppure con chiave personalizzata:
init_pak("percorso/al/mio.pak", key=b"LaMiaChiaveSegreta")
```

## API per il codice del gioco

Per la maggior parte dei casi non serve usare queste funzioni: i loader dell'engine (TextureManager, FontManager, SoundManager, load_map) le usano automaticamente.

Servono solo se il gioco legge file custom dalla cartella assets:

```python
from pyluxel import asset_open, asset_exists, has_pak

# Leggere un file (funziona sia da disco che da pak)
import json
data = json.loads(asset_open("assets/data/enemies.json").read())

# Verificare se un file esiste
if asset_exists("assets/data/config.json"):
    ...

# Verificare se il pak e' attivo
if has_pak():
    print("Asset caricati dal pak")
```

### Riferimento funzioni

| Funzione | Descrizione |
|----------|-------------|
| `asset_open(path) -> BinaryIO` | Apre un asset dal pak (se attivo) o da disco. Restituisce un file-like object binario. |
| `asset_exists(path) -> bool` | `True` se l'asset esiste (nel pak o su disco). |
| `init_pak(path, key=...)` | Carica un file `.pak`. Chiamato automaticamente da `App` se trova `data.pak`. |
| `has_pak() -> bool` | `True` se un pak e' attivo. |

## Integrazione con Nuitka

1. Creare il pak: `pyluxel pak assets/ --exclude cache`
2. Compilare includendo il pak:
   ```bash
   nuitka --onefile --include-data-files=data.pak=data.pak main.py
   ```
3. Distribuire `game.exe` + `data.pak` (oppure `data.pak` embeddato nel onefile)

## Note

- La SDF font cache (`assets/cache/sdf/`) non va nel pak: e' dati generati al primo avvio, non asset originali. Usare `--exclude cache`.
- I save file (`user_data_dir`) non sono coinvolti dal pak.
- Il pak usa path con forward slash. Path come `assets\sprites\player.png` vengono normalizzati automaticamente.
- La protezione e' offuscamento (XOR), non crittografia. Scoraggia l'utente medio, non ferma un reverse engineer determinato.
