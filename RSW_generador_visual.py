#!/usr/bin/env python3
"""
Generador Visual de Mapas RSW para Ragnarok Online (rAthena)
Creador: Fernando Garcia Valenzuela - DunKelNox (rAthena)
=============================================================

Genera archivos RSW (Resource World) a partir de GAT/GND.
Define objetos 3D, luces, sonidos, efectos y configuración del mundo.
Sigue el mismo patrón que gat_generator_visual.py y gnd_generator_visual.py.

Dependencias:
    pip install numpy Pillow

Uso:
    python rsw_generator_visual.py
"""

import struct
import random
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageTk
except ImportError:
    print("Instalando dependencias necesarias...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'numpy', 'Pillow'])
    import numpy as np
    from PIL import Image, ImageDraw, ImageTk


# ============================================================
# IMPLEMENTACIÓN PROPIA DE RUIDO (no requiere compilador)
# ============================================================

def snoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=0, repeaty=0, base=0):
    """
    Implementación propia de ruido Perlin.
    No requiere la librería 'noise' que necesita compilador.
    """
    import random
    
    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)
    
    def lerp(a, b, t):
        return a + t * (b - a)
    
    def hash_2d(px, py, seed):
        rng = random.Random((px * 374761393 + py * 668265263 + seed * 1274126177) % 2**31)
        return rng.uniform(-1, 1)
    
    if repeatx > 0:
        x = x % repeatx
    if repeaty > 0:
        y = y % repeaty
    
    if octaves == 0:
        return 0.0
    
    value = 0.0
    amplitude = 1.0
    frequency = 1.0
    max_value = 0.0
    
    for octave in range(octaves):
        fx = x * frequency
        fy = y * frequency
        
        x0 = int(np.floor(fx))
        y0 = int(np.floor(fy))
        
        sx = fx - x0
        sy = fy - y0
        
        sx = fade(sx)
        sy = fade(sy)
        
        seed = base + octave * 1000
        n00 = hash_2d(x0, y0, seed)
        n10 = hash_2d(x0 + 1, y0, seed)
        n01 = hash_2d(x0, y0 + 1, seed)
        n11 = hash_2d(x0 + 1, y0 + 1, seed)
        
        nx0 = lerp(n00, n10, sx)
        nx1 = lerp(n01, n11, sx)
        ny = lerp(nx0, nx1, sy)
        
        value += amplitude * ny
        max_value += amplitude
        
        amplitude *= persistence
        frequency *= lacunarity
    
    if max_value > 0:
        value = value / max_value
    
    return value


# ============================================================
# CONSTANTES Y UTILIDADES
# ============================================================

GAT_FLAG_INFO = {
    0: {"name": "WALKABLE", "char": ".", "color": "#4CAF50", "desc": "Caminable"},
    1: {"name": "BLOCKED", "char": "#", "color": "#424242", "desc": "Bloqueado"},
    2: {"name": "WATER", "char": "~", "color": "#2196F3", "desc": "Agua"},
    3: {"name": "BLOCKED_WATER", "char": "=", "color": "#9C27B0", "desc": "Hielo/Lava/Barro"},
    4: {"name": "SPECIAL", "char": "!", "color": "#FF9800", "desc": "Especial (script)"},
    5: {"name": "BLOCKED_SPECIAL", "char": "@", "color": "#F44336", "desc": "Especial bloqueado"},
}


# ============================================================
# FORMATO GAT (para lectura)
# ============================================================

class GATFile:
    """Lee archivos GAT generados por gat_generator_visual.py"""

    MAGIC = b"GRAT"
    VERSION_MAJOR = 1
    VERSION_MINOR = 2

    def __init__(self, width=0, height=0):
        self.width = width
        self.height = height
        self.cells = []  # (h1, h2, h3, h4, flag)

    @classmethod
    def load(cls, filepath):
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {filepath}")

        with open(filepath, 'rb') as f:
            magic = f.read(4)
            if magic != cls.MAGIC:
                raise ValueError(f"Magic number inválido: {magic}")

            version_major = struct.unpack('B', f.read(1))[0]
            version_minor = struct.unpack('B', f.read(1))[0]
            width = struct.unpack('<i', f.read(4))[0]
            height = struct.unpack('<i', f.read(4))[0]

            gat = cls(width, height)
            for _ in range(width * height):
                h1 = struct.unpack('<f', f.read(4))[0]
                h2 = struct.unpack('<f', f.read(4))[0]
                h3 = struct.unpack('<f', f.read(4))[0]
                h4 = struct.unpack('<f', f.read(4))[0]
                flag = struct.unpack('<i', f.read(4))[0]
                gat.cells.append((h1, h2, h3, h4, flag))

        return gat

    def get_flag_at(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y * self.width + x][4]
        return 0

    def get_height_at(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y * self.width + x][0]
        return 0.0

    def get_avg_height_at(self, x, y):
        """Altura promedio de una celda GAT"""
        if 0 <= x < self.width and 0 <= y < self.height:
            cell = self.cells[y * self.width + x]
            return sum(cell[:4]) / 4.0
        return 0.0


# ============================================================
# FORMATO RSW - Especificación completa
# ============================================================

@dataclass
class RSWModel:
    """Objeto 3D (modelo RSM) colocado en el mundo"""
    name: str = ""           # 40 bytes null-terminated
    anim_type: int = 0       # 0=none, 1=loop
    anim_speed: float = 1.0
    block_type: int = 0      # 0=none, 1=water, 2=ice, 3=clay

    # Transform
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    rot_x: float = 0.0
    rot_y: float = 0.0
    rot_z: float = 0.0

    scale_x: float = 1.0
    scale_y: float = 1.0
    scale_z: float = 1.0

    # v2.2+
    rsm_res_name: str = ""   # 40 bytes

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Nombre del modelo (40 bytes)
        name_bytes = self.name.encode('cp949', errors='ignore')[:39]
        data += name_bytes + b'\x00' * (40 - len(name_bytes))

        # Tipo de animación
        data += struct.pack('<i', self.anim_type)
        data += struct.pack('<f', self.anim_speed)
        data += struct.pack('<i', self.block_type)

        # Posición
        data += struct.pack('<3f', self.pos_x, self.pos_y, self.pos_z)

        # Rotación
        data += struct.pack('<3f', self.rot_x, self.rot_y, self.rot_z)

        # Escala
        data += struct.pack('<3f', self.scale_x, self.scale_y, self.scale_z)

        # v2.2+: nombre de recurso RSM
        if version >= (2, 2):
            rsm_bytes = self.rsm_res_name.encode('cp949', errors='ignore')[:39]
            data += rsm_bytes + b'\x00' * (40 - len(rsm_bytes))

        return data


@dataclass
class RSWLight:
    """Luz puntual en el mundo"""
    name: str = ""           # 40 bytes null-terminated

    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    # Color RGB (0-1)
    red: float = 1.0
    green: float = 1.0
    blue: float = 1.0

    # Atenuación
    range: float = 1.0       # v2.1+

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Nombre (40 bytes)
        name_bytes = self.name.encode('cp949', errors='ignore')[:39]
        data += name_bytes + b'\x00' * (40 - len(name_bytes))

        # Posición
        data += struct.pack('<3f', self.pos_x, self.pos_y, self.pos_z)

        # Color
        data += struct.pack('<3f', self.red, self.green, self.blue)

        # Rango (v2.1+)
        if version >= (2, 1):
            data += struct.pack('<f', self.range)

        return data


@dataclass
class RSWSound:
    """Fuente de sonido 3D"""
    name: str = ""           # 40 bytes null-terminated
    sound_file: str = ""     # 40 bytes null-terminated
    wave_name: str = ""      # 40 bytes null-terminated (v2.1+)

    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    vol: float = 1.0         # 0-1
    width: int = 0           # área de efecto
    height: int = 0
    range: float = 1.0       # distancia máxima
    cycle: float = 4.0       # segundos entre repeticiones

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Nombre (40 bytes)
        name_bytes = self.name.encode('cp949', errors='ignore')[:39]
        data += name_bytes + b'\x00' * (40 - len(name_bytes))

        # Archivo de sonido (40 bytes)
        snd_bytes = self.sound_file.encode('cp949', errors='ignore')[:39]
        data += snd_bytes + b'\x00' * (40 - len(snd_bytes))

        # Posición
        data += struct.pack('<3f', self.pos_x, self.pos_y, self.pos_z)

        # Volumen
        data += struct.pack('<f', self.vol)

        # Ancho/Alto del área
        data += struct.pack('<i', self.width)
        data += struct.pack('<i', self.height)

        # Rango y ciclo
        data += struct.pack('<f', self.range)
        data += struct.pack('<f', self.cycle)

        # v2.1+: nombre de wave adicional
        if version >= (2, 1):
            wave_bytes = self.wave_name.encode('cp949', errors='ignore')[:39]
            data += wave_bytes + b'\x00' * (40 - len(wave_bytes))

        return data


@dataclass
class RSWSprite:
    """Sprite 2D (efecto) en el mundo"""
    name: str = ""           # 40 bytes

    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    # v2.2+
    sprite_name: str = ""    # 40 bytes
    spr_res_name: str = ""   # 40 bytes

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Nombre (40 bytes)
        name_bytes = self.name.encode('cp949', errors='ignore')[:39]
        data += name_bytes + b'\x00' * (40 - len(name_bytes))

        # Posición
        data += struct.pack('<3f', self.pos_x, self.pos_y, self.pos_z)

        # v2.2+: nombres de sprite
        if version >= (2, 2):
            spr_bytes = self.sprite_name.encode('cp949', errors='ignore')[:39]
            data += spr_bytes + b'\x00' * (40 - len(spr_bytes))

            res_bytes = self.spr_res_name.encode('cp949', errors='ignore')[:39]
            data += res_bytes + b'\x00' * (40 - len(res_bytes))

        return data


@dataclass
class RSWEffect:
    """Efecto de partículas"""
    name: str = ""           # 40 bytes
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0

    type: int = 0
    emit_speed: float = 1.0
    param1: float = 0.0
    param2: float = 0.0
    param3: float = 0.0
    param4: float = 0.0

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Nombre (40 bytes)
        name_bytes = self.name.encode('cp949', errors='ignore')[:39]
        data += name_bytes + b'\x00' * (40 - len(name_bytes))

        # Posición
        data += struct.pack('<3f', self.pos_x, self.pos_y, self.pos_z)

        # Tipo
        data += struct.pack('<i', self.type)

        # Velocidad de emisión
        data += struct.pack('<f', self.emit_speed)

        # Parámetros
        data += struct.pack('<4f', self.param1, self.param2, self.param3, self.param4)

        return data


@dataclass
class RSWQuadTreeNode:
    """Nodo del QuadTree para culling"""
    half_size: float = 0.0
    center_x: float = 0.0
    center_z: float = 0.0
    bottom: float = 0.0
    top: float = 0.0
    children: List['RSWQuadTreeNode'] = field(default_factory=list)

    def pack(self, version: Tuple[int, int]) -> bytes:
        data = b''

        # Mitad del tamaño (0 = nodo hoja/vacío)
        data += struct.pack('<f', self.half_size)

        if self.half_size > 0:
            # Centro
            data += struct.pack('<f', self.center_x)
            data += struct.pack('<f', self.center_z)

            # Altura mínima/máxima
            data += struct.pack('<f', self.bottom)
            data += struct.pack('<f', self.top)

            # 4 hijos (recursivo)
            for child in self.children:
                data += child.pack(version)

        return data


class RSWFile:
    """
    Archivo RSW (Resource World) - Recursos del mundo 3D

    Versiones soportadas:
    - 2.0: Formato base (INI block, objetos, luces, sonidos)
    - 2.1: Agrega rango de luces, nombre de wave en sonidos
    - 2.2: Agrega nombres de recurso RSM, sprites, efectos

    Estructura del archivo:
    - Header: "GRSW" + version + INI block
    - Objetos 3D: lista de modelos RSM
    - Luces: lista de luces puntuales
    - Sonidos: lista de fuentes de sonido
    - Sprites: lista de sprites 2D (v2.2+)
    - Efectos: lista de efectos de partículas (v2.2+)
    - QuadTree: estructura de culling
    - Water: nivel de agua, color, etc.
    - Ambient: luz ambiental y direccional
    - Bounding Box: límites del mundo
    """

    MAGIC = b"GRSW"

    # Modelos disponibles por bioma
    BIOME_MODELS = {
        'pradera': [
            '\\model\\tree01.rsm',
            '\\model\\tree02.rsm',
            '\\model\\grass01.rsm',
            '\\model\\flower01.rsm',
            '\\model\\rock01.rsm',
        ],
        'selva': [
            '\\model\\jungle_tree01.rsm',
            '\\model\\jungle_tree02.rsm',
            '\\model\\vine01.rsm',
            '\\model\\bush01.rsm',
            '\\model\\rock_mossy01.rsm',
        ],
        'cerros': [
            '\\model\\pine01.rsm',
            '\\model\\pine02.rsm',
            '\\model\\rock02.rsm',
            '\\model\\rock03.rsm',
            '\\model\\stump01.rsm',
        ],
        'desierto': [
            '\\model\\cactus01.rsm',
            '\\model\\cactus02.rsm',
            '\\model\\palm01.rsm',
            '\\model\\rock_desert01.rsm',
            '\\model\\skull01.rsm',
        ],
        'isla': [
            '\\model\\palm01.rsm',
            '\\model\\palm02.rsm',
            '\\model\\rock_beach01.rsm',
            '\\model\\shell01.rsm',
            '\\model\\crab01.rsm',
        ],
        'paramo': [
            '\\model\\snow_tree01.rsm',
            '\\model\\snow_rock01.rsm',
            '\\model\\ice01.rsm',
            '\\model\\snowman01.rsm',
            '\\model\\frozen_tree01.rsm',
        ],
        'volcano': [
            '\\model\\lava_rock01.rsm',
            '\\model\\lava_rock02.rsm',
            '\\model\\dead_tree01.rsm',
            '\\model\\smoke01.rsm',
            '\\model\\volcano_rock01.rsm',
        ],
        'swamp': [
            '\\model\\swamp_tree01.rsm',
            '\\model\\swamp_tree02.rsm',
            '\\model\\mushroom01.rsm',
            '\\model\\reed01.rsm',
            '\\model\\swamp_rock01.rsm',
        ],
    }

    # Sonidos por bioma
    BIOME_SOUNDS = {
        'pradera': [
            ('\\wav\\wind.wav', '\\wav\\birds.wav'),
            ('\\wav\\grass_rustle.wav', ''),
        ],
        'selva': [
            ('\\wav\\jungle_amb.wav', '\\wav\\monkey.wav'),
            ('\\wav\\water_drip.wav', ''),
        ],
        'cerros': [
            ('\\wav\\wind_mountain.wav', '\\wav\\eagle.wav'),
            ('\\wav\\rock_slide.wav', ''),
        ],
        'desierto': [
            ('\\wav\\desert_wind.wav', '\\wav\\sand_storm.wav'),
            ('\\wav\\cricket.wav', ''),
        ],
        'isla': [
            ('\\wav\\ocean.wav', '\\wav\\seagull.wav'),
            ('\\wav\\waves.wav', ''),
        ],
        'paramo': [
            ('\\wav\\blizzard.wav', '\\wav\\howling_wind.wav'),
            ('\\wav\\ice_crack.wav', ''),
        ],
        'volcano': [
            ('\\wav\\lava_bubble.wav', '\\wav\\volcano_rumble.wav'),
            ('\\wav\\fire_crack.wav', ''),
        ],
        'swamp': [
            ('\\wav\\swamp_amb.wav', '\\wav\\frog.wav'),
            ('\\wav\\mosquito.wav', ''),
        ],
    }

    def __init__(self, version: Tuple[int, int] = (2, 1)):
        self.version_major = version[0]
        self.version_minor = version[1]

        # INI Block
        self.ini_block: str = ""
        self.ini_length: int = 0

        # Recursos
        self.models: List[RSWModel] = []
        self.lights: List[RSWLight] = []
        self.sounds: List[RSWSound] = []
        self.sprites: List[RSWSprite] = []
        self.effects: List[RSWEffect] = []

        # QuadTree
        self.quadtree: Optional[RSWQuadTreeNode] = None

        # Agua
        self.water_level: float = 0.0
        self.water_type: int = 0
        self.wave_height: float = 1.0
        self.wave_speed: float = 2.0
        self.wave_pitch: float = 50.0
        self.water_texture_cycling: int = 0

        # Luz ambiental
        self.ambient_r: float = 1.0
        self.ambient_g: float = 1.0
        self.ambient_b: float = 1.0
        self.ambient_intensity: float = 0.5  # v2.2+

        # Luz direccional (sol)
        self.light_r: float = 1.0
        self.light_g: float = 1.0
        self.light_b: float = 1.0
        self.light_intensity: float = 1.0  # v2.2+
        self.light_dir_x: float = -0.5
        self.light_dir_y: float = -1.0
        self.light_dir_z: float = -0.5

        # Bounding box
        self.bb_min_x: float = -500.0
        self.bb_min_y: float = -500.0
        self.bb_min_z: float = -500.0
        self.bb_max_x: float = 500.0
        self.bb_max_y: float = 500.0
        self.bb_max_z: float = 500.0

        # v2.2+
        self.object_count: int = 0

    def get_version_tuple(self) -> Tuple[int, int]:
        return (self.version_major, self.version_minor)

    def is_version_21_or_higher(self) -> bool:
        return self.version_major > 2 or (self.version_major == 2 and self.version_minor >= 1)

    def is_version_22_or_higher(self) -> bool:
        return self.version_major > 2 or (self.version_major == 2 and self.version_minor >= 2)

    def save(self, filepath):
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'wb') as f:
            # === HEADER (10 bytes) ===
            f.write(self.MAGIC)
            f.write(struct.pack('B', self.version_major))
            f.write(struct.pack('B', self.version_minor))

            # === INI BLOCK ===
            ini_data = self.ini_block.encode('cp949', errors='ignore')
            self.ini_length = len(ini_data)
            f.write(struct.pack('<i', self.ini_length))
            f.write(ini_data)

            # === OBJETOS 3D ===
            f.write(struct.pack('<i', len(self.models)))
            for model in self.models:
                f.write(model.pack(self.get_version_tuple()))

            # === LUCES ===
            f.write(struct.pack('<i', len(self.lights)))
            for light in self.lights:
                f.write(light.pack(self.get_version_tuple()))

            # === SONIDOS ===
            f.write(struct.pack('<i', len(self.sounds)))
            for sound in self.sounds:
                f.write(sound.pack(self.get_version_tuple()))

            # === SPRITES (v2.2+) ===
            if self.is_version_22_or_higher():
                f.write(struct.pack('<i', len(self.sprites)))
                for sprite in self.sprites:
                    f.write(sprite.pack(self.get_version_tuple()))

            # === EFECTOS (v2.2+) ===
            if self.is_version_22_or_higher():
                f.write(struct.pack('<i', len(self.effects)))
                for effect in self.effects:
                    f.write(effect.pack(self.get_version_tuple()))

            # === QUADTREE ===
            if self.quadtree:
                f.write(self.quadtree.pack(self.get_version_tuple()))
            else:
                # QuadTree vacío
                f.write(struct.pack('<f', 0.0))

            # === AGUA ===
            f.write(struct.pack('<f', self.water_level))
            f.write(struct.pack('<i', self.water_type))
            f.write(struct.pack('<f', self.wave_height))
            f.write(struct.pack('<f', self.wave_speed))
            f.write(struct.pack('<f', self.wave_pitch))
            f.write(struct.pack('<i', self.water_texture_cycling))

            # === LUZ AMBIENTAL ===
            f.write(struct.pack('<f', self.ambient_r))
            f.write(struct.pack('<f', self.ambient_g))
            f.write(struct.pack('<f', self.ambient_b))

            # Intensidad ambiental (v2.2+)
            if self.is_version_22_or_higher():
                f.write(struct.pack('<f', self.ambient_intensity))

            # === LUZ DIRECCIONAL ===
            f.write(struct.pack('<f', self.light_r))
            f.write(struct.pack('<f', self.light_g))
            f.write(struct.pack('<f', self.light_b))

            # Intensidad direccional (v2.2+)
            if self.is_version_22_or_higher():
                f.write(struct.pack('<f', self.light_intensity))

            f.write(struct.pack('<f', self.light_dir_x))
            f.write(struct.pack('<f', self.light_dir_y))
            f.write(struct.pack('<f', self.light_dir_z))

            # === BOUNDING BOX ===
            f.write(struct.pack('<f', self.bb_min_x))
            f.write(struct.pack('<f', self.bb_min_y))
            f.write(struct.pack('<f', self.bb_min_z))
            f.write(struct.pack('<f', self.bb_max_x))
            f.write(struct.pack('<f', self.bb_max_y))
            f.write(struct.pack('<f', self.bb_max_z))

            # === OBJECT COUNT (v2.2+) ===
            if self.is_version_22_or_higher():
                self.object_count = (len(self.models) + len(self.lights) + 
                                    len(self.sounds) + len(self.sprites) + 
                                    len(self.effects))
                f.write(struct.pack('<i', self.object_count))

        return filepath


# ============================================================
# GENERADOR RSW DESDE GAT
# ============================================================

class RSWGenerator:
    """
    Genera archivos RSW a partir de archivos GAT.

    Coloca objetos 3D según el bioma, genera luces ambientales,
    configura agua y sonidos.
    """

    def __init__(self, gat: GATFile, terrain_type: str = "pradera",
                 gnd_width: int = 0, gnd_height: int = 0,
                 rsw_version: Tuple[int, int] = (2, 1)):
        self.gat = gat
        self.terrain_type = terrain_type
        self.rsw_version = rsw_version

        # Dimensiones del mundo (en unidades de mundo RO: 1 celda GAT = 5 unidades)
        self.world_width = gat.width * 5.0
        self.world_height = gat.height * 5.0

        # Centro del mundo
        self.center_x = self.world_width / 2.0
        self.center_z = self.world_height / 2.0

        # Altura promedio del terreno
        self.avg_terrain_height = 0.0

        # Modelos disponibles para este bioma
        self.available_models = RSWFile.BIOME_MODELS.get(terrain_type, 
                                                         RSWFile.BIOME_MODELS['pradera'])
        self.available_sounds = RSWFile.BIOME_SOUNDS.get(terrain_type,
                                                         RSWFile.BIOME_SOUNDS['pradera'])
        
        # Almacenes de objetos generados
        self.models = []
        self.lights = []
        self.sounds = []
        self.effects = []
        self.quadtree = None

    def _calculate_terrain_stats(self):
        """Calcula estadísticas del terreno para colocación de objetos"""
        heights = []
        water_heights = []

        for y in range(self.gat.height):
            for x in range(self.gat.width):
                h = self.gat.get_avg_height_at(x, y)
                flag = self.gat.get_flag_at(x, y)
                heights.append(h)

                if flag in [2, 3]:
                    water_heights.append(h)

        self.avg_terrain_height = sum(heights) / len(heights) if heights else 5.0

        if water_heights:
            self.water_level = sum(water_heights) / len(water_heights)
        else:
            self.water_level = self.avg_terrain_height - 2.0

    def _world_pos_from_gat(self, gat_x: int, gat_y: int, height_offset: float = 0.0) -> Tuple[float, float, float]:
        """Convierte coordenadas GAT a coordenadas de mundo RO"""
        # En RO: X crece hacia el este, Z crece hacia el sur (o norte dependiendo de la convención)
        # Y es la altura
        world_x = gat_x * 5.0
        world_z = gat_y * 5.0
        world_y = self.gat.get_avg_height_at(gat_x, gat_y) + height_offset

        return (world_x, world_y, world_z)

    def _is_valid_placement(self, gat_x: int, gat_y: int, require_walkable: bool = True) -> bool:
        """Verifica si una posición es válida para colocar un objeto"""
        if gat_x < 2 or gat_x >= self.gat.width - 2:
            return False
        if gat_y < 2 or gat_y >= self.gat.height - 2:
            return False

        flag = self.gat.get_flag_at(gat_x, gat_y)

        if require_walkable and flag not in [0, 4]:
            return False

        # No colocar en agua profunda
        if flag in [2, 3]:
            return False

        return True

    def _generate_ini_block(self) -> str:
        """Genera el bloque INI con referencias a GAT y GND"""
        map_name = f"generated_{self.terrain_type}"

        ini = f"""[Map]
Name={map_name}
Type={self.terrain_type}
Width={self.gat.width}
Height={self.gat.height}
WorldWidth={self.world_width:.1f}
WorldHeight={self.world_height:.1f}

[Files]
GAT=.\\{map_name}.gat
GND=.\\{map_name}.gnd
RSW=.\\{map_name}.rsw

[Water]
Level={self.water_level:.2f}
Type={self._get_water_type()}

[Lighting]
Ambient=0.5,0.5,0.5
Directional=1.0,1.0,1.0
Direction=-0.5,-1.0,-0.5

[Generator]
Tool=ROMapGenerator
Version=1.0
Terrain={self.terrain_type}
"""
        return ini

    def _get_water_type(self) -> int:
        """Determina el tipo de agua según el bioma"""
        water_types = {
            "pradera": 0,    # Agua normal
            "selva": 0,      # Agua normal
            "cerros": 0,     # Agua normal
            "desierto": 0,   # Agua normal (oasis)
            "isla": 0,       # Agua normal (océano)
            "paramo": 3,     # Hielo
            "volcano": 4,    # Lava
            "swamp": 5,      # Pantano/barro
        }
        return water_types.get(self.terrain_type, 0)

    def _place_vegetation(self, density: float = 0.15):
        """Coloca vegetación (árboles, arbustos) en áreas caminables"""
        random.seed(hash(self.terrain_type) % 10000)

        for y in range(3, self.gat.height - 3, 2):
            for x in range(3, self.gat.width - 3, 2):
                if random.random() > density:
                    continue

                if not self._is_valid_placement(x, y):
                    continue

                # Seleccionar modelo aleatorio
                model_path = random.choice(self.available_models)

                # Variación de posición dentro de la celda
                offset_x = random.uniform(-1.5, 1.5)
                offset_z = random.uniform(-1.5, 1.5)

                wx, wy, wz = self._world_pos_from_gat(x, y, 0.0)

                model = RSWModel()
                model.name = model_path
                model.rsm_res_name = model_path
                model.pos_x = wx + offset_x
                model.pos_y = wy
                model.pos_z = wz + offset_z

                # Rotación aleatoria
                model.rot_y = random.uniform(0, 360)

                # Escala variada
                scale = random.uniform(0.7, 1.3)
                model.scale_x = scale
                model.scale_y = scale
                model.scale_z = scale

                self.models.append(model)

    def _place_rocks_and_details(self, density: float = 0.08):
        """Coloca rocas y detalles del terreno"""
        random.seed(hash(self.terrain_type + "rocks") % 10000)

        rock_models = [m for m in self.available_models if 'rock' in m.lower()]
        if not rock_models:
            rock_models = self.available_models

        for y in range(2, self.gat.height - 2):
            for x in range(2, self.gat.width - 2):
                if random.random() > density:
                    continue

                flag = self.gat.get_flag_at(x, y)

                # Colocar rocas en pendientes (BLOCKED) y áreas caminables
                if flag not in [0, 1, 4, 5]:
                    continue

                model_path = random.choice(rock_models)
                wx, wy, wz = self._world_pos_from_gat(x, y, 0.0)

                model = RSWModel()
                model.name = model_path
                model.rsm_res_name = model_path
                model.pos_x = wx + random.uniform(-1.0, 1.0)
                model.pos_y = wy
                model.pos_z = wz + random.uniform(-1.0, 1.0)
                model.rot_y = random.uniform(0, 360)

                scale = random.uniform(0.3, 0.8)
                model.scale_x = scale
                model.scale_y = scale
                model.scale_z = scale

                self.models.append(model)

    def _place_water_objects(self):
        """Coloca objetos específicos cerca del agua"""
        random.seed(hash(self.terrain_type + "water") % 10000)

        water_models = []
        if self.terrain_type == "isla":
            water_models = ['\\model\\palm01.rsm', '\\model\\shell01.rsm']
        elif self.terrain_type == "swamp":
            water_models = ['\\model\\reed01.rsm', '\\model\\mushroom01.rsm']
        elif self.terrain_type == "paramo":
            water_models = ['\\model\\ice01.rsm']

        if not water_models:
            return

        for y in range(1, self.gat.height - 1):
            for x in range(1, self.gat.width - 1):
                flag = self.gat.get_flag_at(x, y)

                # Colocar cerca del agua (adyacentes a celdas de agua)
                if flag in [2, 3]:
                    continue

                has_water_neighbor = False
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.gat.width and 0 <= ny < self.gat.height:
                            if self.gat.get_flag_at(nx, ny) in [2, 3]:
                                has_water_neighbor = True
                                break

                if has_water_neighbor and random.random() < 0.3:
                    model_path = random.choice(water_models)
                    wx, wy, wz = self._world_pos_from_gat(x, y, 0.0)

                    model = RSWModel()
                    model.name = model_path
                    model.rsm_res_name = model_path
                    model.pos_x = wx
                    model.pos_y = wy
                    model.pos_z = wz
                    model.rot_y = random.uniform(0, 360)

                    self.models.append(model)

    def _generate_lights(self):
        """Genera luces ambientales y puntuales"""
        # Luz ambiental general
        ambient = RSWLight()
        ambient.name = "ambient_light"
        ambient.pos_x = self.center_x
        ambient.pos_y = 50.0
        ambient.pos_z = self.center_z
        ambient.red = 0.6
        ambient.green = 0.6
        ambient.blue = 0.7
        ambient.range = 1000.0
        self.lights.append(ambient)

        # Luces puntuales en áreas especiales
        random.seed(hash(self.terrain_type + "lights") % 10000)

        for y in range(5, self.gat.height - 5, 10):
            for x in range(5, self.gat.width - 5, 10):
                flag = self.gat.get_flag_at(x, y)

                if flag == 4:  # SPECIAL - luces de script/NPC
                    wx, wy, wz = self._world_pos_from_gat(x, y, 3.0)

                    light = RSWLight()
                    light.name = f"special_light_{x}_{y}"
                    light.pos_x = wx
                    light.pos_y = wy + 2.0
                    light.pos_z = wz
                    light.red = 1.0
                    light.green = 0.8
                    light.blue = 0.4
                    light.range = 15.0
                    self.lights.append(light)

    def _generate_sounds(self):
        """Genera fuentes de sonido ambientales"""
        random.seed(hash(self.terrain_type + "sounds") % 10000)

        # Sonidos de ambiente general
        for sound_pair in self.available_sounds[:1]:
            sound_file, wave_name = sound_pair

            sound = RSWSound()
            sound.name = "ambient_sound"
            sound.sound_file = sound_file
            sound.wave_name = wave_name
            sound.pos_x = self.center_x
            sound.pos_y = 10.0
            sound.pos_z = self.center_z
            sound.vol = 0.3
            sound.width = int(self.world_width)
            sound.height = int(self.world_height)
            sound.range = max(self.world_width, self.world_height)
            sound.cycle = 8.0
            self.sounds.append(sound)

        # Sonidos locales cerca del agua
        water_sounds = [s for s in self.available_sounds if 'water' in s[0].lower() or 'ocean' in s[0].lower()]
        if water_sounds and self.terrain_type in ["isla", "swamp", "pradera"]:
            for y in range(10, self.gat.height - 10, 20):
                for x in range(10, self.gat.width - 10, 20):
                    flag = self.gat.get_flag_at(x, y)
                    if flag in [2, 3]:
                        wx, wy, wz = self._world_pos_from_gat(x, y, 0.0)

                        sound = RSWSound()
                        sound.name = f"water_sound_{x}_{y}"
                        sound_file, wave_name = water_sounds[0]
                        sound.sound_file = sound_file
                        sound.wave_name = wave_name
                        sound.pos_x = wx
                        sound.pos_y = wy
                        sound.pos_z = wz
                        sound.vol = 0.5
                        sound.width = 30
                        sound.height = 30
                        sound.range = 40.0
                        sound.cycle = 4.0
                        self.sounds.append(sound)
                        break  # Solo un sonido de agua

    def _generate_effects(self):
        """Genera efectos de partículas según el bioma"""
        if not self.is_version_22_or_higher():
            return

        random.seed(hash(self.terrain_type + "effects") % 10000)

        # Efectos por bioma
        effect_types = {
            "volcano": 1,   # Humo/fuego
            "paramo": 2,    # Nieve
            "swamp": 3,     # Niebla
            "selva": 4,     # Hojas
            "desierto": 5,  # Arena
        }

        effect_type = effect_types.get(self.terrain_type, 0)
        if effect_type == 0:
            return

        # Colocar efectos en áreas relevantes
        for y in range(5, self.gat.height - 5, 15):
            for x in range(5, self.gat.width - 5, 15):
                if random.random() > 0.3:
                    continue

                wx, wy, wz = self._world_pos_from_gat(x, y, 2.0)

                effect = RSWEffect()
                effect.name = f"effect_{self.terrain_type}_{x}_{y}"
                effect.pos_x = wx
                effect.pos_y = wy
                effect.pos_z = wz
                effect.type = effect_type
                effect.emit_speed = random.uniform(0.5, 2.0)
                effect.param1 = random.uniform(0.0, 1.0)
                effect.param2 = random.uniform(0.0, 1.0)

                self.effects.append(effect)

    def _generate_quadtree(self):
        """Genera el QuadTree para culling"""
        root = RSWQuadTreeNode()

        # Calcular bounding box del terreno
        min_h = float('inf')
        max_h = float('-inf')

        for y in range(self.gat.height):
            for x in range(self.gat.width):
                h = self.gat.get_avg_height_at(x, y)
                min_h = min(min_h, h)
                max_h = max(max_h, h)

        # Tamaño del mundo
        half_size = max(self.world_width, self.world_height) / 2.0

        root.half_size = half_size
        root.center_x = self.center_x
        root.center_z = self.center_z
        root.bottom = min_h - 10.0
        root.top = max_h + 50.0

        # Crear 4 hijos (dividir en cuadrantes)
        child_size = half_size / 2.0

        for i in range(4):
            child = RSWQuadTreeNode()
            child.half_size = child_size

            # Posición del cuadrante
            if i == 0:  # NW
                child.center_x = self.center_x - child_size
                child.center_z = self.center_z - child_size
            elif i == 1:  # NE
                child.center_x = self.center_x + child_size
                child.center_z = self.center_z - child_size
            elif i == 2:  # SW
                child.center_x = self.center_x - child_size
                child.center_z = self.center_z + child_size
            else:  # SE
                child.center_x = self.center_x + child_size
                child.center_z = self.center_z + child_size

            child.bottom = min_h - 5.0
            child.top = max_h + 20.0

            # Nietos (simplificado - solo un nivel más)
            for j in range(4):
                grandchild = RSWQuadTreeNode()
                grandchild.half_size = child_size / 2.0
                grandchild.center_x = child.center_x + (random.choice([-1, 1]) * child_size / 2.0)
                grandchild.center_z = child.center_z + (random.choice([-1, 1]) * child_size / 2.0)
                grandchild.bottom = min_h
                grandchild.top = max_h + 10.0
                grandchild.half_size = 0.0  # Nodo hoja

                child.children.append(grandchild)

            root.children.append(child)

        self.quadtree = root

    def _setup_lighting(self):
        """Configura iluminación según el bioma"""
        lighting_configs = {
            "pradera": {
                'ambient': (0.7, 0.7, 0.6),
                'directional': (1.0, 0.95, 0.8),
                'dir': (-0.3, -1.0, -0.3),
            },
            "selva": {
                'ambient': (0.4, 0.5, 0.3),
                'directional': (0.8, 0.9, 0.6),
                'dir': (-0.2, -1.0, -0.2),
            },
            "cerros": {
                'ambient': (0.6, 0.6, 0.7),
                'directional': (0.9, 0.9, 1.0),
                'dir': (-0.5, -1.0, -0.2),
            },
            "desierto": {
                'ambient': (0.8, 0.7, 0.5),
                'directional': (1.0, 0.9, 0.7),
                'dir': (-0.4, -1.0, -0.4),
            },
            "isla": {
                'ambient': (0.6, 0.7, 0.8),
                'directional': (1.0, 1.0, 0.9),
                'dir': (-0.3, -1.0, -0.5),
            },
            "paramo": {
                'ambient': (0.7, 0.7, 0.8),
                'directional': (0.9, 0.9, 1.0),
                'dir': (-0.2, -1.0, -0.6),
            },
            "volcano": {
                'ambient': (0.5, 0.3, 0.2),
                'directional': (1.0, 0.6, 0.3),
                'dir': (-0.1, -1.0, -0.1),
            },
            "swamp": {
                'ambient': (0.3, 0.4, 0.3),
                'directional': (0.6, 0.7, 0.5),
                'dir': (-0.3, -1.0, -0.3),
            },
        }

        config = lighting_configs.get(self.terrain_type, lighting_configs['pradera'])

        self.ambient_r, self.ambient_g, self.ambient_b = config['ambient']
        self.light_r, self.light_g, self.light_b = config['directional']
        self.light_dir_x, self.light_dir_y, self.light_dir_z = config['dir']

    def is_version_22_or_higher(self) -> bool:
        return self.rsw_version[0] > 2 or (self.rsw_version[0] == 2 and self.rsw_version[1] >= 2)

    def generate(self) -> RSWFile:
        """Genera el archivo RSW completo"""
        rsw = RSWFile(self.rsw_version)

        # Calcular estadísticas del terreno
        self._calculate_terrain_stats()

        # Configurar iluminación
        self._setup_lighting()
        rsw.ambient_r = self.ambient_r
        rsw.ambient_g = self.ambient_g
        rsw.ambient_b = self.ambient_b
        rsw.light_r = self.light_r
        rsw.light_g = self.light_g
        rsw.light_b = self.light_b
        rsw.light_dir_x = self.light_dir_x
        rsw.light_dir_y = self.light_dir_y
        rsw.light_dir_z = self.light_dir_z

        # Configurar agua
        rsw.water_level = self.water_level
        rsw.water_type = self._get_water_type()

        water_configs = {
            "pradera": (0.5, 1.5, 40.0),
            "selva": (0.3, 1.0, 30.0),
            "cerros": (0.8, 2.0, 50.0),
            "desierto": (0.2, 0.5, 60.0),
            "isla": (1.0, 2.5, 45.0),
            "paramo": (0.1, 0.3, 20.0),
            "volcano": (0.2, 0.8, 35.0),
            "swamp": (0.1, 0.4, 25.0),
        }

        wave_h, wave_s, wave_p = water_configs.get(self.terrain_type, (1.0, 2.0, 50.0))
        rsw.wave_height = wave_h
        rsw.wave_speed = wave_s
        rsw.wave_pitch = wave_p

        # Bounding box
        rsw.bb_min_x = -10.0
        rsw.bb_min_y = self.water_level - 10.0
        rsw.bb_min_z = -10.0
        rsw.bb_max_x = self.world_width + 10.0
        rsw.bb_max_y = self.avg_terrain_height + 50.0
        rsw.bb_max_z = self.world_height + 10.0

        # INI Block
        rsw.ini_block = self._generate_ini_block()

        # Colocar objetos
        self._place_vegetation(density=0.12)
        self._place_rocks_and_details(density=0.06)
        self._place_water_objects()

        # Generar luces
        self._generate_lights()

        # Generar sonidos
        self._generate_sounds()

        # Generar efectos (v2.2+)
        self._generate_effects()

        # Generar QuadTree
        self._generate_quadtree()

        # Transferir objetos al RSW
        rsw.models = self.models
        rsw.lights = self.lights
        rsw.sounds = self.sounds
        rsw.effects = self.effects
        rsw.quadtree = self.quadtree

        return rsw


# ============================================================
# VISUALIZADOR 2D DEL RSW
# ============================================================

class RSWVisualizer:
    """Visualiza la distribución de objetos en el mapa"""

    @classmethod
    def render_preview(cls, rsw: RSWFile, gat: GATFile, cell_size: int = 6) -> Image.Image:
        width = gat.width * cell_size
        height = gat.height * cell_size

        img = Image.new('RGB', (width, height), (20, 20, 20))
        draw = ImageDraw.Draw(img)

        # Dibujar terreno base
        for y in range(gat.height):
            for x in range(gat.width):
                flag = gat.get_flag_at(x, y)
                info = GAT_FLAG_INFO.get(flag, GAT_FLAG_INFO[0])

                hex_color = info['color'].lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

                px = x * cell_size
                py = (gat.height - 1 - y) * cell_size

                draw.rectangle(
                    [px, py, px + cell_size - 1, py + cell_size - 1],
                    fill=rgb,
                    outline=(30, 30, 30)
                )

        # Dibujar objetos 3D
        for model in rsw.models:
            # Convertir posición de mundo a coordenadas GAT
            gat_x = int(model.pos_x / 5.0)
            gat_y = int(model.pos_z / 5.0)

            if 0 <= gat_x < gat.width and 0 <= gat_y < gat.height:
                px = gat_x * cell_size + cell_size // 2
                py = (gat.height - 1 - gat_y) * cell_size + cell_size // 2

                # Color según tipo de objeto
                if 'tree' in model.name.lower():
                    color = (34, 139, 34)
                elif 'rock' in model.name.lower():
                    color = (128, 128, 128)
                elif 'palm' in model.name.lower():
                    color = (50, 205, 50)
                else:
                    color = (255, 215, 0)

                radius = max(2, cell_size // 3)
                draw.ellipse(
                    [px - radius, py - radius, px + radius, py + radius],
                    fill=color,
                    outline=(255, 255, 255)
                )

        # Dibujar luces
        for light in rsw.lights:
            gat_x = int(light.pos_x / 5.0)
            gat_y = int(light.pos_z / 5.0)

            if 0 <= gat_x < gat.width and 0 <= gat_y < gat.height:
                px = gat_x * cell_size + cell_size // 2
                py = (gat.height - 1 - gat_y) * cell_size + cell_size // 2

                r = int(light.red * 255)
                g = int(light.green * 255)
                b = int(light.blue * 255)

                draw.ellipse(
                    [px - 2, py - 2, px + 2, py + 2],
                    fill=(r, g, b),
                    outline=(255, 255, 255)
                )

        # Dibujar sonidos
        for sound in rsw.sounds:
            gat_x = int(sound.pos_x / 5.0)
            gat_y = int(sound.pos_z / 5.0)

            if 0 <= gat_x < gat.width and 0 <= gat_y < gat.height:
                px = gat_x * cell_size + cell_size // 2
                py = (gat.height - 1 - gat_y) * cell_size + cell_size // 2

                draw.rectangle(
                    [px - 1, py - 1, px + 1, py + 1],
                    fill=(0, 191, 255),
                    outline=(255, 255, 255)
                )

        return img


# ============================================================
# INTERFAZ GRÁFICA - CON SCROLL EN PANEL IZQUIERDO
# ============================================================

class RSWGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapas RSW - Ragnarok Online (rAthena)")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")

        self.current_gat = None
        self.current_rsw = None
        self.preview_image = None
        self.cell_size = 6

        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # ==================== PANEL IZQUIERDO CON SCROLL ====================
        left_container = tk.Frame(main_frame, bg="#2d2d2d", width=380)
        left_container.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_container.grid_propagate(False)
        left_container.rowconfigure(0, weight=0)  # Botones fijos
        left_container.rowconfigure(1, weight=1)  # Scrollable
        left_container.columnconfigure(0, weight=1)

        # --- BOTONES DE ACCIÓN (SIEMPRE VISIBLES) ---
        action_frame = tk.Frame(left_container, bg="#2d2d2d", height=100)
        action_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        action_frame.grid_propagate(False)

        tk.Button(action_frame, text="▶ GENERAR RSW", command=self._generate_rsw,
                 bg="#9C27B0", fg="white", font=("Consolas", 11, "bold"),
                 activebackground="#7B1FA2", cursor="hand2",
                 height=1).pack(fill=tk.X, padx=2, pady=(0, 2))

        save_btn_frame = tk.Frame(action_frame, bg="#2d2d2d")
        save_btn_frame.pack(fill=tk.X, padx=2, pady=2)

        tk.Button(save_btn_frame, text="💾 Guardar RSW", command=self._save_rsw,
                 bg="#9C27B0", fg="white", font=("Consolas", 9),
                 activebackground="#7B1FA2", cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(save_btn_frame, text="🖼️ Guardar Preview", command=self._save_preview,
                 bg="#2196F3", fg="white", font=("Consolas", 9),
                 activebackground="#1976D2", cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

        # --- CONTENIDO SCROLLABLE ---
        scroll_container = tk.Frame(left_container, bg="#2d2d2d")
        scroll_container.grid(row=1, column=0, sticky="nsew")
        scroll_container.rowconfigure(0, weight=1)
        scroll_container.columnconfigure(0, weight=1)

        self.scroll_canvas = tk.Canvas(scroll_container, bg="#2d2d2d", highlightthickness=0)
        self.scroll_canvas.grid(row=0, column=0, sticky="nsew")

        scrollbar = tk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=self.scroll_canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)

        def on_mousewheel(event):
            self.scroll_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        self.scroll_canvas.bind("<Enter>", lambda e: self.scroll_canvas.bind_all("<MouseWheel>", on_mousewheel))
        self.scroll_canvas.bind("<Leave>", lambda e: self.scroll_canvas.unbind_all("<MouseWheel>"))

        # Frame interno con ancho ajustable
        self.scroll_frame = tk.Frame(self.scroll_canvas, bg="#2d2d2d")
        self._scroll_frame_id = self.scroll_canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw", width=350
        )

        def configure_scroll_region(event):
            self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            canvas_w = self.scroll_canvas.winfo_width()
            self.scroll_canvas.itemconfig(self._scroll_frame_id, width=max(1, canvas_w - 4))

        self.scroll_frame.bind("<Configure>", configure_scroll_region)
        self.scroll_canvas.bind(
            "<Configure>",
            lambda e: self.scroll_canvas.itemconfig(
                self._scroll_frame_id, width=max(1, e.width - 4)
            )
        )

        # ========== CONTENIDO DENTRO DEL SCROLL ==========
        left_panel = self.scroll_frame

        title = tk.Label(left_panel, text="🌍 RSW Generator", 
                        font=("Consolas", 16, "bold"), fg="#9C27B0", bg="#2d2d2d")
        title.pack(pady=(10, 5))

        subtitle = tk.Label(left_panel, text="Para rAthena - Desde GAT", 
                           font=("Consolas", 10), fg="#888888", bg="#2d2d2d")
        subtitle.pack(pady=(0, 10))

        # --- Sección: Cargar GAT ---
        load_frame = tk.LabelFrame(left_panel, text="1. Cargar GAT", 
                                  font=("Consolas", 10, "bold"),
                                  fg="#ffffff", bg="#2d2d2d", bd=2)
        load_frame.pack(fill=tk.X, padx=5, pady=5)

        self.gat_path_var = tk.StringVar(value="")
        gat_entry = tk.Entry(load_frame, textvariable=self.gat_path_var, 
                            font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                            insertbackground="#ffffff", state="readonly")
        gat_entry.pack(fill=tk.X, padx=5, pady=(5, 2))

        btn_frame = tk.Frame(load_frame, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, padx=5, pady=(2, 5))

        tk.Button(btn_frame, text="📂 Cargar GAT", command=self._load_gat,
                 bg="#4CAF50", fg="white", font=("Consolas", 9),
                 activebackground="#45a049", cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🎲 Generar GAT", command=self._generate_gat,
                 bg="#FF9800", fg="white", font=("Consolas", 9),
                 activebackground="#F57C00", cursor="hand2").pack(side=tk.LEFT)

        # --- Sección: Configuración ---
        config_frame = tk.LabelFrame(left_panel, text="2. Configuración RSW", 
                                    font=("Consolas", 10, "bold"),
                                    fg="#ffffff", bg="#2d2d2d", bd=2)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        # Versión RSW
        tk.Label(config_frame, text="Versión RSW:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 0))

        version_frame = tk.Frame(config_frame, bg="#2d2d2d")
        version_frame.pack(fill=tk.X, padx=5, pady=2)

        self.version_var = tk.StringVar(value="2.1")
        version_combo = ttk.Combobox(version_frame, textvariable=self.version_var,
                                       values=["2.0", "2.1", "2.2"],
                                       state="readonly", font=("Consolas", 9), width=8)
        version_combo.pack(side=tk.LEFT, padx=(0, 5))
        version_combo.bind("<<ComboboxSelected>>", self._on_version_change)

        self.version_desc_label = tk.Label(version_frame, 
            text="Compatible con clientes 2010+",
            fg="#4CAF50", bg="#2d2d2d", font=("Consolas", 8))
        self.version_desc_label.pack(side=tk.LEFT)

        # Tipo de terreno
        tk.Label(config_frame, text="Bioma/Terreno:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(8, 0))
        self.terrain_var = tk.StringVar(value="pradera")
        terrain_combo = ttk.Combobox(config_frame, textvariable=self.terrain_var, 
                                       values=["pradera", "selva", "cerros", "desierto", 
                                               "isla", "paramo", "volcano", "swamp"],
                                       state="readonly", font=("Consolas", 9))
        terrain_combo.pack(fill=tk.X, padx=5, pady=2)

        # Densidad de objetos
        tk.Label(config_frame, text="Densidad de objetos:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(5, 0))

        density_frame = tk.Frame(config_frame, bg="#2d2d2d")
        density_frame.pack(fill=tk.X, padx=5, pady=2)

        self.density_var = tk.DoubleVar(value=0.12)
        tk.Scale(density_frame, from_=0.0, to=0.5, resolution=0.01, 
                orient=tk.HORIZONTAL, variable=self.density_var,
                bg="#2d2d2d", fg="#cccccc", highlightthickness=0,
                troughcolor="#3d3d3d", activebackground="#4CAF50").pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.density_label = tk.Label(density_frame, text="0.12", 
                                     fg="#cccccc", bg="#2d2d2d", font=("Consolas", 9), width=4)
        self.density_label.pack(side=tk.LEFT, padx=(5, 0))

        self.density_var.trace('w', lambda *args: self.density_label.configure(
            text=f"{self.density_var.get():.2f}"))

        # --- Configuración de Agua ---
        water_frame = tk.LabelFrame(left_panel, text="💧 Configuración de Agua", 
                                   font=("Consolas", 10, "bold"),
                                   fg="#2196F3", bg="#2d2d2d", bd=2)
        water_frame.pack(fill=tk.X, padx=5, pady=5)

        # Nivel de agua
        tk.Label(water_frame, text="Nivel:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.water_level_var = tk.StringVar(value="auto")
        tk.Entry(water_frame, textvariable=self.water_level_var, width=10, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        tk.Label(water_frame, text="(auto)", fg="#888888", bg="#2d2d2d", 
                font=("Consolas", 8)).grid(row=0, column=2, sticky=tk.W, padx=2)

        # Tipo de agua
        tk.Label(water_frame, text="Tipo:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.water_type_var = tk.StringVar(value="auto")
        water_type_combo = ttk.Combobox(water_frame, textvariable=self.water_type_var,
                                          values=["auto", "0: Agua", "3: Hielo", "4: Lava", "5: Pantano"],
                                          state="readonly", font=("Consolas", 9), width=12)
        water_type_combo.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)

        # --- Configuración de Iluminación ---
        light_frame = tk.LabelFrame(left_panel, text="💡 Iluminación", 
                                   font=("Consolas", 10, "bold"),
                                   fg="#FF9800", bg="#2d2d2d", bd=2)
        light_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(light_frame, text="Ambiental R:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.amb_r_var = tk.StringVar(value="0.7")
        tk.Entry(light_frame, textvariable=self.amb_r_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=0, column=1, padx=5, pady=2)

        tk.Label(light_frame, text="G:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=0, column=2, sticky=tk.W, padx=2)
        self.amb_g_var = tk.StringVar(value="0.7")
        tk.Entry(light_frame, textvariable=self.amb_g_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=0, column=3, padx=5, pady=2)

        tk.Label(light_frame, text="B:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=0, column=4, sticky=tk.W, padx=2)
        self.amb_b_var = tk.StringVar(value="0.6")
        tk.Entry(light_frame, textvariable=self.amb_b_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=0, column=5, padx=5, pady=2)

        # --- Sección: Info ---
        info_frame = tk.LabelFrame(left_panel, text="Información", 
                                  font=("Consolas", 10, "bold"),
                                  fg="#ffffff", bg="#2d2d2d", bd=2)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.info_label = tk.Label(info_frame, text="Carga un GAT para comenzar", 
                                  fg="#888888", bg="#2d2d2d", 
                                  font=("Consolas", 8), justify=tk.LEFT)
        self.info_label.pack(anchor=tk.W, padx=5, pady=5)

        # --- Objetos generados ---
        obj_frame = tk.LabelFrame(left_panel, text="Objetos Generados", 
                                 font=("Consolas", 10, "bold"),
                                 fg="#ffffff", bg="#2d2d2d", bd=2)
        obj_frame.pack(fill=tk.X, padx=5, pady=5)

        self.obj_text = scrolledtext.ScrolledText(obj_frame, height=8, width=40,
                                                   font=("Consolas", 8),
                                                   bg="#1e1e1e", fg="#cccccc",
                                                   insertbackground="#ffffff")
        self.obj_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # ==================== PANEL DERECHO: PREVIEW ====================
        right_panel = tk.Frame(main_frame, bg="#1e1e1e")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)

        canvas_container = tk.Frame(right_panel, bg="#1e1e1e")
        canvas_container.grid(row=0, column=0, sticky="nsew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_container, bg="#0d0d0d", 
                               highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        h_scroll = tk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")

        v_scroll = tk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Barra de estado
        self.status_bar = tk.Label(self.root, text="Listo. Carga un archivo GAT para comenzar.", 
                                  bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                  bg="#2d2d2d", fg="#cccccc", font=("Consolas", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Inicializar estado
        self._on_version_change(None)

    def _on_version_change(self, event):
        version = self.version_var.get()

        if version == "2.0":
            self.version_desc_label.configure(text="Compatible con clientes antiguos", fg="#FF9800")
        elif version == "2.1":
            self.version_desc_label.configure(text="Compatible con clientes 2010+", fg="#4CAF50")
        elif version == "2.2":
            self.version_desc_label.configure(text="Agrega sprites y efectos", fg="#9C27B0")

    def _parse_version(self) -> Tuple[int, int]:
        version_str = self.version_var.get()
        parts = version_str.split('.')
        return (int(parts[0]), int(parts[1]))

    def _load_gat(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Archivos GAT", "*.gat"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.current_gat = GATFile.load(filepath)
                self.gat_path_var.set(filepath)
                self._update_info()
                self._render_preview()
                self.status_bar.configure(text=f"GAT cargado: {self.current_gat.width}x{self.current_gat.height}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el GAT:\n{e}")

    def _generate_gat(self):
        width, height = 100, 100
        gat = GATFile(width, height)

        seed = random.randint(0, 10000)
        for y in range(height):
            for x in range(width):
                # Usar nuestra propia implementación de snoise2
                value = snoise2(x/50.0, y/50.0, octaves=4, persistence=0.5, base=seed)
                h = (value + 1.0) / 2.0 * 20.0

                if value < -0.3:
                    flag = 2
                    h = 2.0
                elif value > 0.5:
                    flag = 1
                else:
                    flag = 0

                gat.cells.append((h, h, h, h, flag))

        self.current_gat = gat
        self.gat_path_var.set("[GAT Generado Internamente]")
        self._update_info()
        self._render_preview()
        self.status_bar.configure(text=f"GAT generado: {width}x{height}")

    def _generate_rsw(self):
        if not self.current_gat:
            messagebox.showwarning("Advertencia", "Primero carga o genera un GAT.")
            return

        try:
            terrain_type = self.terrain_var.get()
            version = self._parse_version()

            generator = RSWGenerator(self.current_gat, terrain_type, rsw_version=version)

            self.status_bar.configure(text=f"Generando RSW v{version[0]}.{version[1]}...")
            self.root.update()

            self.current_rsw = generator.generate()

            # Aplicar configuración de agua personalizada
            try:
                level_str = self.water_level_var.get()
                if level_str.lower() != "auto":
                    self.current_rsw.water_level = float(level_str)
            except ValueError:
                pass

            try:
                type_str = self.water_type_var.get()
                if type_str != "auto":
                    self.current_rsw.water_type = int(type_str.split(':')[0])
            except (ValueError, IndexError):
                pass

            # Aplicar iluminación personalizada
            try:
                self.current_rsw.ambient_r = float(self.amb_r_var.get())
                self.current_rsw.ambient_g = float(self.amb_g_var.get())
                self.current_rsw.ambient_b = float(self.amb_b_var.get())
            except ValueError:
                pass

            self._update_object_list()
            self._render_preview()

            version_str = f"{self.current_rsw.version_major}.{self.current_rsw.version_minor}"
            self.status_bar.configure(
                text=f"RSW v{version_str} generado: {len(self.current_rsw.models)} modelos, "
                     f"{len(self.current_rsw.lights)} luces, {len(self.current_rsw.sounds)} sonidos"
            )
            messagebox.showinfo("Éxito", f"Archivo RSW v{version_str} generado correctamente.\n\nAhora puedes guardarlo.")

        except Exception as e:
            messagebox.showerror("Error", f"Error generando RSW:\n{e}")
            import traceback
            traceback.print_exc()

    def _save_rsw(self):
        if not self.current_rsw:
            messagebox.showwarning("Advertencia", "No hay RSW para guardar. Genera uno primero.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".rsw",
            filetypes=[("Archivos RSW", "*.rsw"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.current_rsw.save(filepath)
                version = f"{self.current_rsw.version_major}.{self.current_rsw.version_minor}"
                self.status_bar.configure(text=f"RSW v{version} guardado: {filepath}")
                messagebox.showinfo("Éxito", f"Archivo RSW v{version} guardado:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _save_preview(self):
        if not self.preview_image:
            messagebox.showwarning("Advertencia", "No hay preview para guardar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("Imagen PNG", "*.png"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.preview_image.save(filepath)
                self.status_bar.configure(text=f"Preview guardado: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _update_info(self):
        if not self.current_gat:
            return

        flags = [cell[4] for cell in self.current_gat.cells]
        total = len(flags)

        text = f"""GAT: {self.current_gat.width}x{self.current_gat.height}
Celdas: {total}
WALKABLE: {flags.count(0)} ({flags.count(0)/total*100:.1f}%)
BLOCKED: {flags.count(1)} ({flags.count(1)/total*100:.1f}%)
WATER: {flags.count(2)} ({flags.count(2)/total*100:.1f}%)
BLOCKED_WATER: {flags.count(3)} ({flags.count(3)/total*100:.1f}%)
SPECIAL: {flags.count(4)} ({flags.count(4)/total*100:.1f}%)
BLOCKED_SPECIAL: {flags.count(5)} ({flags.count(5)/total*100:.1f}%)
Mundo: {self.current_gat.width*5:.0f}x{self.current_gat.height*5:.0f} unidades"""

        self.info_label.configure(text=text)

    def _update_object_list(self):
        if not self.current_rsw:
            return

        self.obj_text.delete(1.0, tk.END)

        self.obj_text.insert(tk.END, f"=== Modelos 3D ({len(self.current_rsw.models)}) ===\n")
        for i, model in enumerate(self.current_rsw.models[:20]):
            self.obj_text.insert(tk.END, f"[{i}] {model.name} @ ({model.pos_x:.1f}, {model.pos_y:.1f}, {model.pos_z:.1f})\n")
        if len(self.current_rsw.models) > 20:
            self.obj_text.insert(tk.END, f"... y {len(self.current_rsw.models)-20} más\n")

        self.obj_text.insert(tk.END, f"\n=== Luces ({len(self.current_rsw.lights)}) ===\n")
        for i, light in enumerate(self.current_rsw.lights[:10]):
            self.obj_text.insert(tk.END, f"[{i}] {light.name} @ ({light.pos_x:.1f}, {light.pos_y:.1f}, {light.pos_z:.1f})\n")

        self.obj_text.insert(tk.END, f"\n=== Sonidos ({len(self.current_rsw.sounds)}) ===\n")
        for i, sound in enumerate(self.current_rsw.sounds[:10]):
            self.obj_text.insert(tk.END, f"[{i}] {sound.sound_file}\n")

        if self.current_rsw.effects:
            self.obj_text.insert(tk.END, f"\n=== Efectos ({len(self.current_rsw.effects)}) ===\n")
            for i, effect in enumerate(self.current_rsw.effects[:10]):
                self.obj_text.insert(tk.END, f"[{i}] {effect.name} tipo={effect.type}\n")

        self.obj_text.insert(tk.END, f"\n=== Configuración ===\n")
        self.obj_text.insert(tk.END, f"Agua: nivel={self.current_rsw.water_level:.2f}, tipo={self.current_rsw.water_type}\n")
        self.obj_text.insert(tk.END, f"Ambiental: R={self.current_rsw.ambient_r:.2f} G={self.current_rsw.ambient_g:.2f} B={self.current_rsw.ambient_b:.2f}\n")
        self.obj_text.insert(tk.END, f"Direccional: R={self.current_rsw.light_r:.2f} G={self.current_rsw.light_g:.2f} B={self.current_rsw.light_b:.2f}\n")
        self.obj_text.insert(tk.END, f"Versión: {self.current_rsw.version_major}.{self.current_rsw.version_minor}\n")

    def _render_preview(self):
        if not self.current_gat:
            return

        if self.current_rsw:
            self.preview_image = RSWVisualizer.render_preview(
                self.current_rsw, self.current_gat, cell_size=self.cell_size
            )
        else:
            # Preview solo del GAT
            width = self.current_gat.width * self.cell_size
            height = self.current_gat.height * self.cell_size
            self.preview_image = Image.new('RGB', (width, height), (20, 20, 20))
            draw = ImageDraw.Draw(self.preview_image)

            for y in range(self.current_gat.height):
                for x in range(self.current_gat.width):
                    flag = self.current_gat.get_flag_at(x, y)
                    info = GAT_FLAG_INFO.get(flag, GAT_FLAG_INFO[0])

                    hex_color = info['color'].lstrip('#')
                    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

                    px = x * self.cell_size
                    py = (self.current_gat.height - 1 - y) * self.cell_size

                    draw.rectangle(
                        [px, py, px + self.cell_size - 1, py + self.cell_size - 1],
                        fill=rgb,
                        outline=(30, 30, 30)
                    )

        if self.preview_image:
            max_width = 1200
            max_height = 800
            img_width, img_height = self.preview_image.size
            
            scale = 1.0
            if img_width > max_width or img_height > max_height:
                scale_x = max_width / img_width
                scale_y = max_height / img_height
                scale = min(scale_x, scale_y, 1.0)
                
                if scale < 1.0:
                    new_width = int(img_width * scale)
                    new_height = int(img_height * scale)
                    self.preview_image = self.preview_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            self.photo_image = ImageTk.PhotoImage(self.preview_image)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo_image)
            self.canvas.configure(scrollregion=(0, 0, self.preview_image.width, self.preview_image.height))


def main():
    root = tk.Tk()
    app = RSWGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()