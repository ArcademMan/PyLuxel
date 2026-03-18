"""Loader per mappe JSON/TMX — formato proprio + compatibilita' con export Tiled."""

from __future__ import annotations
import json
import xml.etree.ElementTree as ET
from typing import Any, TYPE_CHECKING

from pyluxel.core import paths
from pyluxel.core.pak import asset_open, asset_exists
from pyluxel.debug import cprint

if TYPE_CHECKING:
    from pyluxel.core.texture_manager import TextureManager

from pyluxel.tilemap.tileset import Tileset
from pyluxel.tilemap.tile_layer import TileLayer
from pyluxel.tilemap.tile_map import TileMap, MapObject


def load_map(path: str, texture_manager: TextureManager | None = None) -> TileMap:
    """Carica una mappa da file JSON o TMX.

    Supporta:
    - Formato Tiled JSON (.tmj, .json) con tileset embedded o esterni (.tsx)
    - Formato Tiled XML (.tmx) con tileset esterni (.tsx)
    - Formato proprio semplificato
    - Mappe solo-oggetti (senza tileset, texture_manager=None)

    Args:
        path: percorso al file della mappa (.json, .tmj, .tmx)
        texture_manager: TextureManager per caricare i tileset (None per mappe solo-oggetti)

    Returns:
        TileMap con layers, tilesets e oggetti caricati
    """
    ext = paths.extension(path).lower()
    if not ext:
        for try_ext in (".tmx", ".json", ".tmj"):
            candidate = path + try_ext
            if asset_exists(candidate):
                return load_map(candidate, texture_manager)
        raise FileNotFoundError(
            f"load_map: file not found: {path} "
            f"(tried .tmx, .json, .tmj)"
        )
    if ext == ".tmx":
        return _load_tmx(path, texture_manager)
    return _load_json(path, texture_manager)


def _load_json(path: str, texture_manager: TextureManager | None) -> TileMap:
    """Carica una mappa da file JSON (Tiled o formato proprio)."""
    try:
        raw = asset_open(path).read()
        data = json.loads(raw)
    except FileNotFoundError:
        raise FileNotFoundError(f"load_map: file not found: {path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"load_map: invalid JSON in {path}: {e}")

    _required = ("width", "height", "tilewidth", "tileheight")
    missing = [k for k in _required if k not in data]
    if missing:
        raise KeyError(f"load_map: missing required fields {missing} in {path}")

    map_w = data["width"]
    map_h = data["height"]
    tile_w = data["tilewidth"]
    tile_h = data["tileheight"]

    tilemap = TileMap(map_w, map_h, tile_w, tile_h)

    # --- Carica tileset (solo se texture_manager disponibile) ---
    if texture_manager is not None:
        for ts_data in data.get("tilesets", []):
            source = ts_data.get("source")
            first_gid = ts_data.get("firstgid", 1)

            if source:
                # Tileset esterno (TSX) — risolvi path relativo alla mappa
                tsx_path = paths.resolve_relative(path, source)
                tileset = _load_tsx(tsx_path, texture_manager, first_gid)
            else:
                # Tileset embedded nel JSON
                image_path = ts_data.get("image", "")
                image_name = paths.filename(image_path)
                ts_tile_w = ts_data.get("tilewidth", tile_w)
                ts_tile_h = ts_data.get("tileheight", tile_h)

                # Parsa tile properties dal JSON embedded
                tile_properties = _parse_json_tile_properties(
                    ts_data.get("tiles", []), first_gid
                )

                texture = texture_manager.load(image_name)
                tileset = Tileset(texture, ts_tile_w, ts_tile_h,
                                  first_gid=first_gid,
                                  tile_properties=tile_properties)

            tilemap.tilesets.append(tileset)

    # --- Carica layers ---
    for layer_data in data.get("layers", []):
        layer_type = layer_data.get("type", "tilelayer")

        if layer_type == "tilelayer":
            layer = _parse_tile_layer(layer_data, map_w, map_h, tile_w, tile_h)
            tilemap.layers.append(layer)

        elif layer_type == "objectgroup":
            layer_name = layer_data.get("name", "")
            for obj_data in layer_data.get("objects", []):
                obj = _parse_object(obj_data)
                obj.properties["_layer"] = layer_name
                tilemap.objects.append(obj)

    return tilemap


def _load_tmx(path: str, texture_manager: TextureManager | None) -> TileMap:
    """Carica una mappa da file TMX (Tiled XML)."""
    try:
        tree = ET.parse(asset_open(path))
    except FileNotFoundError:
        raise FileNotFoundError(f"load_map: file not found: {path}")
    except ET.ParseError as e:
        raise ValueError(f"load_map: invalid XML in {path}: {e}")

    root = tree.getroot()
    map_w = int(root.get("width", 0))
    map_h = int(root.get("height", 0))
    tile_w = int(root.get("tilewidth", 0))
    tile_h = int(root.get("tileheight", 0))

    if not all((map_w, map_h, tile_w, tile_h)):
        raise KeyError(f"load_map: missing map dimensions in {path}")

    tilemap = TileMap(map_w, map_h, tile_w, tile_h)

    # --- Carica tileset ---
    if texture_manager is not None:
        for ts_elem in root.findall("tileset"):
            first_gid = int(ts_elem.get("firstgid", 1))
            source = ts_elem.get("source")

            if source:
                tsx_path = paths.resolve_relative(path, source)
                tileset = _load_tsx(tsx_path, texture_manager, first_gid)
            else:
                # Tileset inline nel TMX (raro ma possibile)
                image_elem = ts_elem.find("image")
                image_name = paths.filename(image_elem.get("source", ""))
                ts_tile_w = int(ts_elem.get("tilewidth", tile_w))
                ts_tile_h = int(ts_elem.get("tileheight", tile_h))

                tile_properties = _parse_xml_tile_properties(ts_elem, first_gid)

                texture = texture_manager.load(image_name)
                tileset = Tileset(texture, ts_tile_w, ts_tile_h,
                                  first_gid=first_gid,
                                  tile_properties=tile_properties)

            tilemap.tilesets.append(tileset)

    # --- Carica layers ---
    for layer_elem in root.findall("layer"):
        layer = _parse_tmx_tile_layer(layer_elem, map_w, map_h, tile_w, tile_h)
        tilemap.layers.append(layer)

    for objgroup_elem in root.findall("objectgroup"):
        layer_name = objgroup_elem.get("name", "")
        for obj_elem in objgroup_elem.findall("object"):
            obj = _parse_tmx_object(obj_elem)
            obj.properties["_layer"] = layer_name
            tilemap.objects.append(obj)

    return tilemap


def _load_tsx(tsx_path: str, texture_manager: TextureManager,
              first_gid: int) -> Tileset:
    """Carica un tileset da file TSX (Tiled XML esterno).

    Args:
        tsx_path: percorso assoluto al file .tsx
        texture_manager: TextureManager per caricare la texture
        first_gid: primo global tile ID assegnato a questo tileset

    Returns:
        Tileset con texture e tile properties caricate
    """
    try:
        tree = ET.parse(asset_open(tsx_path))
    except FileNotFoundError:
        raise FileNotFoundError(f"_load_tsx: file not found: {tsx_path}")
    except ET.ParseError as e:
        raise ValueError(f"_load_tsx: invalid XML in {tsx_path}: {e}")

    root = tree.getroot()
    tile_w = int(root.get("tilewidth", 32))
    tile_h = int(root.get("tileheight", 32))

    # Immagine del tileset
    image_elem = root.find("image")
    if image_elem is None:
        raise ValueError(f"_load_tsx: no <image> element in {tsx_path}")
    image_name = paths.filename(image_elem.get("source", ""))

    # Tile properties
    tile_properties = _parse_xml_tile_properties(root, first_gid)

    texture = texture_manager.load(image_name)
    return Tileset(texture, tile_w, tile_h,
                   first_gid=first_gid,
                   tile_properties=tile_properties)


def _parse_xml_tile_properties(tileset_elem: ET.Element,
                                first_gid: int) -> dict[int, dict[str, Any]]:
    """Parsa le tile properties da un elemento XML <tileset>.

    Ogni <tile id="N"> ha properties locali (0-based).
    Le converte in GID globali (id + first_gid).
    """
    tile_properties: dict[int, dict[str, Any]] = {}

    for tile_elem in tileset_elem.findall("tile"):
        local_id = int(tile_elem.get("id", 0))
        gid = local_id + first_gid

        props_elem = tile_elem.find("properties")
        if props_elem is None:
            continue

        props: dict[str, Any] = {}
        for prop in props_elem.findall("property"):
            name = prop.get("name", "")
            if not name:
                continue
            value = prop.get("value", "")
            prop_type = prop.get("type", "string")
            props[name] = _convert_property_value(value, prop_type)

        if props:
            tile_properties[gid] = props

    return tile_properties


def _parse_json_tile_properties(tiles: list[dict],
                                 first_gid: int) -> dict[int, dict[str, Any]]:
    """Parsa le tile properties dal formato JSON embedded di Tiled.

    tiles e' la lista "tiles" dentro un tileset JSON, ogni entry ha
    "id" (locale) e "properties" (lista di {name, type, value}).
    """
    tile_properties: dict[int, dict[str, Any]] = {}

    for tile_data in tiles:
        local_id = tile_data.get("id", 0)
        gid = local_id + first_gid

        props: dict[str, Any] = {}
        for prop in tile_data.get("properties", []):
            name = prop.get("name", "")
            if not name:
                continue
            value = prop.get("value", "")
            prop_type = prop.get("type", "string")
            props[name] = _convert_property_value(value, prop_type)

        if props:
            tile_properties[gid] = props

    return tile_properties


def _convert_property_value(value: str | bool | int | float,
                             prop_type: str) -> Any:
    """Converte un valore di property al tipo corretto."""
    if prop_type == "bool":
        if isinstance(value, bool):
            return value
        return str(value).lower() == "true"
    elif prop_type == "int":
        return int(value)
    elif prop_type == "float":
        return float(value)
    return value  # string o tipo sconosciuto


# ---------- TMX layer/object parsing ----------

def _parse_tmx_tile_layer(elem: ET.Element, map_w: int, map_h: int,
                           tile_w: int, tile_h: int) -> TileLayer:
    """Parsa un <layer> TMX con <data encoding="csv">."""
    name = elem.get("name", "unnamed")
    visible = elem.get("visible", "1") != "0"
    opacity = float(elem.get("opacity", "1.0"))

    data_elem = elem.find("data")
    if data_elem is None or data_elem.text is None:
        raw = [0] * (map_w * map_h)
    else:
        encoding = data_elem.get("encoding", "")
        if encoding == "csv":
            raw = [int(x.strip()) for x in data_elem.text.strip().split(",") if x.strip()]
        else:
            raise ValueError(f"Unsupported layer encoding: '{encoding}' (only 'csv' supported)")

    expected = map_w * map_h
    if len(raw) < expected:
        cprint.warning(
            f"Tile layer '{name}' has {len(raw)} tiles,"
            f" expected {expected} ({map_w}x{map_h}). Padding with 0."
        )
        raw = list(raw) + [0] * (expected - len(raw))

    grid = []
    for row_idx in range(map_h):
        start = row_idx * map_w
        grid.append(list(raw[start:start + map_w]))

    layer = TileLayer(name, map_w, map_h, tile_w, tile_h, data=grid)
    layer.visible = visible
    layer.opacity = opacity
    return layer


def _parse_tmx_object(elem: ET.Element) -> MapObject:
    """Parsa un <object> da un TMX objectgroup."""
    # Properties
    properties: dict[str, Any] = {}
    props_elem = elem.find("properties")
    if props_elem is not None:
        for prop in props_elem.findall("property"):
            name = prop.get("name", "")
            if not name:
                continue
            value = prop.get("value", "")
            prop_type = prop.get("type", "string")
            properties[name] = _convert_property_value(value, prop_type)

    # Polygon
    polygon = None
    poly_elem = elem.find("polygon")
    if poly_elem is not None:
        points_str = poly_elem.get("points", "")
        polygon = []
        for point in points_str.split():
            parts = point.split(",")
            if len(parts) == 2:
                polygon.append((float(parts[0]), float(parts[1])))

    # Ellipse
    is_ellipse = elem.find("ellipse") is not None

    return MapObject(
        name=elem.get("name", ""),
        type=elem.get("type", "") or elem.get("class", ""),
        x=float(elem.get("x", 0)),
        y=float(elem.get("y", 0)),
        width=float(elem.get("width", 0)),
        height=float(elem.get("height", 0)),
        properties=properties,
        polygon=polygon,
        id=int(elem.get("id", 0)),
        rotation=float(elem.get("rotation", 0)),
        ellipse=is_ellipse,
    )


# ---------- JSON layer/object parsing (originale) ----------

def _parse_tile_layer(data: dict, map_w: int, map_h: int,
                      tile_w: int, tile_h: int) -> TileLayer:
    """Parsa un tile layer dal JSON."""
    name = data.get("name", "unnamed")
    visible = data.get("visible", True)
    opacity = data.get("opacity", 1.0)

    # I dati possono essere flat (Tiled) o gia' 2D (formato nostro)
    raw = data.get("data", [])

    if raw and isinstance(raw[0], list):
        # Gia' 2D
        grid = raw
    else:
        # Flat array → 2D
        expected = map_w * map_h
        if len(raw) < expected:
            cprint.warning(
                f"Tile layer '{name}' has {len(raw)} tiles,"
                f" expected {expected} ({map_w}x{map_h}). Padding with 0."
            )
            raw = list(raw) + [0] * (expected - len(raw))
        grid = []
        for row_idx in range(map_h):
            start = row_idx * map_w
            grid.append(list(raw[start:start + map_w]))

    layer = TileLayer(name, map_w, map_h, tile_w, tile_h, data=grid)
    layer.visible = visible
    layer.opacity = opacity
    return layer


def _parse_object(data: dict) -> MapObject:
    """Parsa un oggetto dal JSON."""
    poly_data = data.get("polygon")
    polygon = [(p["x"], p["y"]) for p in poly_data] if poly_data else None

    return MapObject(
        name=data.get("name", ""),
        type=data.get("type", "") or data.get("class", ""),
        x=data.get("x", 0.0),
        y=data.get("y", 0.0),
        width=data.get("width", 0.0),
        height=data.get("height", 0.0),
        id=data.get("id", 0),
        properties={
            p["name"]: p["value"]
            for p in data.get("properties", [])
            if "name" in p and "value" in p
        },
        polygon=polygon,
        rotation=data.get("rotation", 0.0),
        ellipse=data.get("ellipse", False),
    )
