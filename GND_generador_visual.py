#!/usr/bin/env python3
"""
Generador Visual de Mapas GND para Ragnarok Online (rAthena)
Creador: Fernando Garcia Valenzuela - DunKelNox (rAthena)
vercion: 2.5
==============================================================

Convierte archivos GAT en archivos GND con texturas de BrowEdit.
Soporta versiones GND 1.7, 1.8 y 1.9 con configuración de agua.

Dependencias:
    pip install numpy Pillow

Uso:
    python gnd_generador_visual.py
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
# IMPLEMENTACIÓN PROPIA DE RUIDO
# ============================================================

def snoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=0, repeaty=0, base=0):
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
# FORMATO GAT
# ============================================================

class GATFile:
    MAGIC = b"GRAT"
    VERSION_MAJOR = 1
    VERSION_MINOR = 2

    def __init__(self, width=0, height=0):
        self.width = width
        self.height = height
        self.cells = []

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

    def get_cell_heights(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            cell = self.cells[y * self.width + x]
            return (cell[0], cell[1], cell[2], cell[3])
        return (0.0, 0.0, 0.0, 0.0)


# ============================================================
# FORMATO GND
# ============================================================

@dataclass
class GNDSurface:
    u_bottom_left: float = 0.0
    u_bottom_right: float = 1.0
    u_top_left: float = 0.0
    u_top_right: float = 1.0
    v_bottom_left: float = 1.0
    v_bottom_right: float = 1.0
    v_top_left: float = 0.0
    v_top_right: float = 0.0
    texture_id: int = -1
    lightmap_id: int = 0
    color: Tuple[int, int, int, int] = (255, 255, 255, 255)

    def pack(self) -> bytes:
        data = struct.pack('<8f',
            self.u_bottom_left, self.u_bottom_right,
            self.u_top_left, self.u_top_right,
            self.v_bottom_left, self.v_bottom_right,
            self.v_top_left, self.v_top_right)
        data += struct.pack('<i', self.texture_id)
        data += struct.pack('<i', self.lightmap_id)
        data += struct.pack('<4B', self.color[0], self.color[1], self.color[2], self.color[3])
        return data


@dataclass
class GNDCube:
    h_bottom_left: float = 0.0
    h_bottom_right: float = 0.0
    h_top_left: float = 0.0
    h_top_right: float = 0.0
    surface_top: int = -1
    surface_north: int = -1
    surface_east: int = -1

    def pack(self) -> bytes:
        return struct.pack('<4f3i',
            self.h_bottom_left, self.h_bottom_right,
            self.h_top_left, self.h_top_right,
            self.surface_top, self.surface_north, self.surface_east)


@dataclass
class GNDLightmapSlice:
    shadowmap: List[int] = field(default_factory=lambda: [255]*64)
    lightmap: List[Tuple[int, int, int]] = field(default_factory=lambda: [(128, 128, 128)]*64)

    def pack(self) -> bytes:
        data = b''
        for i in range(64):
            data += struct.pack('B', self.shadowmap[i])
        for i in range(64):
            r, g, b = self.lightmap[i]
            data += struct.pack('3B', r, g, b)
        return data


@dataclass
class GNDWaterConfig:
    level: float = 0.0
    type: int = 0
    wave_height: float = 1.0
    wave_speed: float = 2.0
    wave_pitch: float = 50.0
    texture_cycling: int = 0

    def pack(self) -> bytes:
        return struct.pack('<f i f f f i',
            self.level, self.type, self.wave_height,
            self.wave_speed, self.wave_pitch, self.texture_cycling)


class GNDFile:
    MAGIC = b"GRGN"
    TEXTURE_PATH_LENGTH = 80
    DEFAULT_SCALE = 10.0

    DEFAULT_TEXTURES = {
        'grass': '\\texture\\grass000.bmp',
        'dirt': '\\texture\\dirt000.bmp',
        'cliff': '\\texture\\cliff000.bmp',
        'water': '\\texture\\water000.bmp',
        'rock': '\\texture\\rock000.bmp',
        'wood': '\\texture\\wood000.bmp',
        'sand': '\\texture\\sand000.bmp',
        'snow': '\\texture\\snow000.bmp',
        'lava': '\\texture\\lava000.bmp',
        'swamp': '\\texture\\swamp000.bmp',
        'black': '\\texture\\backside.bmp',
    }

    WATER_TEXTURES = [
        '\\texture\\water000.bmp', '\\texture\\water001.bmp', '\\texture\\water002.bmp',
        '\\texture\\water003.bmp', '\\texture\\water004.bmp', '\\texture\\water005.bmp',
        '\\texture\\water006.bmp', '\\texture\\water007.bmp', '\\texture\\water008.bmp',
        '\\texture\\water009.bmp', '\\texture\\water010.bmp', '\\texture\\water011.bmp',
        '\\texture\\water012.bmp', '\\texture\\water013.bmp', '\\texture\\water014.bmp',
        '\\texture\\water015.bmp', '\\texture\\water016.bmp', '\\texture\\water017.bmp',
        '\\texture\\water018.bmp', '\\texture\\water019.bmp', '\\texture\\water020.bmp',
        '\\texture\\water021.bmp', '\\texture\\water022.bmp', '\\texture\\water023.bmp',
        '\\texture\\water024.bmp', '\\texture\\water025.bmp', '\\texture\\water026.bmp',
        '\\texture\\water027.bmp', '\\texture\\water028.bmp', '\\texture\\water029.bmp',
        '\\texture\\water030.bmp', '\\texture\\water031.bmp',
    ]

    def __init__(self, width=0, height=0, version=(1, 7)):
        self.width = width
        self.height = height
        self.scale = self.DEFAULT_SCALE
        self.version_major = version[0]
        self.version_minor = version[1]
        self.texture_paths: List[str] = []
        self.lightmap_slices: List[GNDLightmapSlice] = []
        self.surfaces: List[GNDSurface] = []
        self.cubes: List[GNDCube] = []
        self.water_config: GNDWaterConfig = GNDWaterConfig()
        self.water_textures: List[str] = []
        self.water_texture_count: int = 0

    def add_texture(self, path: str) -> int:
        if path in self.texture_paths:
            return self.texture_paths.index(path)
        self.texture_paths.append(path)
        return len(self.texture_paths) - 1

    def add_surface(self, surface: GNDSurface) -> int:
        self.surfaces.append(surface)
        return len(self.surfaces) - 1

    def add_lightmap_slice(self, slice_data: GNDLightmapSlice) -> int:
        self.lightmap_slices.append(slice_data)
        return len(self.lightmap_slices) - 1

    def set_cube(self, x: int, y: int, cube: GNDCube):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = y * self.width + x
            self.cubes[idx] = cube

    def get_cube(self, x: int, y: int) -> Optional[GNDCube]:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cubes[y * self.width + x]
        return None

    def is_version_18_or_higher(self) -> bool:
        return self.version_major > 1 or (self.version_major == 1 and self.version_minor >= 8)

    def is_version_19_or_higher(self) -> bool:
        return self.version_major > 1 or (self.version_major == 1 and self.version_minor >= 9)

    def save(self, filepath):
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('B', self.version_major))
            f.write(struct.pack('B', self.version_minor))
            f.write(struct.pack('<i', self.width))
            f.write(struct.pack('<i', self.height))
            f.write(struct.pack('<f', self.scale))

            f.write(struct.pack('<i', len(self.texture_paths)))
            f.write(struct.pack('<i', self.TEXTURE_PATH_LENGTH))
            for path in self.texture_paths:
                encoded = path.encode('cp949', errors='ignore')[:self.TEXTURE_PATH_LENGTH-1]
                padded = encoded + b'\x00' * (self.TEXTURE_PATH_LENGTH - len(encoded))
                f.write(padded)

            f.write(struct.pack('<i', len(self.lightmap_slices)))
            f.write(struct.pack('<i', 1))
            f.write(struct.pack('<i', 8))
            f.write(struct.pack('<i', 8))
            for slice_data in self.lightmap_slices:
                f.write(slice_data.pack())

            f.write(struct.pack('<i', len(self.surfaces)))
            for surface in self.surfaces:
                f.write(surface.pack())

            for cube in self.cubes:
                f.write(cube.pack())

            if self.is_version_18_or_higher():
                f.write(self.water_config.pack())

            if self.is_version_19_or_higher():
                f.write(struct.pack('<i', self.water_texture_count))
                for i in range(self.water_texture_count):
                    tex_path = self.water_textures[i] if i < len(self.water_textures) else ''
                    encoded = tex_path.encode('cp949', errors='ignore')[:self.TEXTURE_PATH_LENGTH-1]
                    padded = encoded + b'\x00' * (self.TEXTURE_PATH_LENGTH - len(encoded))
                    f.write(padded)

        return filepath


# ============================================================
# GENERADOR GND
# ============================================================

class GNDGenerator:
    def __init__(self, gat: GATFile, terrain_type: str = "pradera", 
                 gnd_version: Tuple[int, int] = (1, 7)):
        self.gat = gat
        self.terrain_type = terrain_type
        self.gnd_version = gnd_version
        self.gnd_width = (gat.width + 1) // 2
        self.gnd_height = (gat.height + 1) // 2

    def _get_texture_for_flag(self, flag: int, is_wall: bool = False) -> str:
        textures = GNDFile.DEFAULT_TEXTURES
        if is_wall:
            return textures['cliff']

        if flag == 0:
            if self.terrain_type in ["pradera", "selva", "swamp"]:
                return textures['grass']
            elif self.terrain_type == "desierto":
                return textures['sand']
            elif self.terrain_type == "paramo":
                return textures['snow']
            elif self.terrain_type == "cerros":
                return textures['dirt']
            elif self.terrain_type == "isla":
                return textures['sand']
            elif self.terrain_type == "volcano":
                return textures['dirt']
            return textures['grass']
        elif flag == 1:
            return textures['rock']
        elif flag == 2:
            return textures['water']
        elif flag == 3:
            if self.terrain_type == "volcano":
                return textures['lava']
            elif self.terrain_type == "paramo":
                return textures['snow']
            return textures['swamp']
        elif flag == 4:
            return textures['wood']
        elif flag == 5:
            return textures['rock']
        return textures['grass']

    def _get_dominant_flag_in_cube(self, cx: int, cy: int) -> int:
        flags = {}
        gat_x = cx * 2
        gat_y = cy * 2

        for dy in range(2):
            for dx in range(2):
                x = gat_x + dx
                y = gat_y + dy
                if x < self.gat.width and y < self.gat.height:
                    flag = self.gat.get_flag_at(x, y)
                    flags[flag] = flags.get(flag, 0) + 1

        if not flags:
            return 0

        priority = {2: 100, 3: 90, 1: 80, 5: 70, 4: 60, 0: 0}
        best_flag = 0
        best_score = -1
        for flag, count in flags.items():
            score = priority.get(flag, 0) * 10 + count
            if score > best_score:
                best_score = score
                best_flag = flag
        return best_flag

    def _get_cube_heights(self, cx: int, cy: int) -> Tuple[float, float, float, float]:
        gat_x = cx * 2
        gat_y = cy * 2
        h_bl = self.gat.get_height_at(gat_x, gat_y)
        h_br = self.gat.get_height_at(gat_x + 1, gat_y) if gat_x + 1 < self.gat.width else h_bl
        h_tl = self.gat.get_height_at(gat_x, gat_y + 1) if gat_y + 1 < self.gat.height else h_bl
        h_tr = self.gat.get_height_at(gat_x + 1, gat_y + 1) if gat_x + 1 < self.gat.width and gat_y + 1 < self.gat.height else h_bl
        return (h_bl, h_br, h_tl, h_tr)

    def _needs_wall(self, cx: int, cy: int, direction: str) -> bool:
        cube_flag = self._get_dominant_flag_in_cube(cx, cy)

        if direction == 'north':
            neighbor_cy = cy - 1
            if neighbor_cy < 0:
                return True
            neighbor_flag = self._get_dominant_flag_in_cube(cx, neighbor_cy)
        else:
            neighbor_cx = cx + 1
            if neighbor_cx >= self.gnd_width:
                return True
            neighbor_flag = self._get_dominant_flag_in_cube(neighbor_cx, cy)

        h_current = self._get_cube_heights(cx, cy)
        h_avg_current = sum(h_current) / 4.0

        if direction == 'north':
            h_neighbor = self._get_cube_heights(cx, neighbor_cy)
        else:
            h_neighbor = self._get_cube_heights(neighbor_cx, cy)
        h_avg_neighbor = sum(h_neighbor) / 4.0

        height_diff = abs(h_avg_current - h_avg_neighbor)
        type_change = (cube_flag in [0, 1, 4, 5] and neighbor_flag in [2, 3]) or \
                      (cube_flag in [2, 3] and neighbor_flag in [0, 1, 4, 5])
        return height_diff > 2.0 or type_change

    def _calculate_water_level(self) -> float:
        water_heights = []
        for y in range(self.gat.height):
            for x in range(self.gat.width):
                if self.gat.get_flag_at(x, y) in [2, 3]:
                    water_heights.append(self.gat.get_height_at(x, y))
        return sum(water_heights) / len(water_heights) if water_heights else 2.0

    def _calculate_water_type(self) -> int:
        water_types = {
            "pradera": 0, "selva": 0, "cerros": 0, "desierto": 0,
            "isla": 0, "paramo": 3, "volcano": 4, "swamp": 5
        }
        return water_types.get(self.terrain_type, 0)

    def generate(self) -> GNDFile:
        gnd = GNDFile(self.gnd_width, self.gnd_height, self.gnd_version)

        default_lightmap = GNDLightmapSlice()
        default_lightmap.shadowmap = [255] * 64
        default_lightmap.lightmap = [(128, 128, 128)] * 64
        lightmap_id = gnd.add_lightmap_slice(default_lightmap)

        texture_ids = {}
        for flag in range(6):
            tex_path = self._get_texture_for_flag(flag, is_wall=False)
            texture_ids[flag] = gnd.add_texture(tex_path)

        wall_texture_id = gnd.add_texture(GNDFile.DEFAULT_TEXTURES['cliff'])

        if gnd.is_version_18_or_higher():
            water_level = self._calculate_water_level()
            water_type = self._calculate_water_type()
            gnd.water_config = GNDWaterConfig(
                level=water_level,
                type=water_type,
                wave_height=1.0 if water_type == 0 else 0.2,
                wave_speed=2.0 if water_type == 0 else 0.5,
                wave_pitch=50.0,
                texture_cycling=0
            )

        if gnd.is_version_19_or_higher():
            if self.terrain_type == "volcano":
                gnd.water_textures = ['\\texture\\lava000.bmp', '\\texture\\lava001.bmp', '\\texture\\lava002.bmp']
            elif self.terrain_type == "paramo":
                gnd.water_textures = ['\\texture\\ice000.bmp', '\\texture\\ice001.bmp']
            elif self.terrain_type == "swamp":
                gnd.water_textures = ['\\texture\\swamp000.bmp', '\\texture\\swamp001.bmp']
            else:
                gnd.water_textures = GNDFile.WATER_TEXTURES[:4]
            gnd.water_texture_count = len(gnd.water_textures)

        surface_map = {}
        for flag in range(6):
            surf = GNDSurface()
            surf.texture_id = texture_ids[flag]
            surf.lightmap_id = lightmap_id
            if flag == 0:
                surf.color = (200, 255, 200, 255)
            elif flag == 2:
                surf.color = (255, 200, 150, 255)
            elif flag == 1:
                surf.color = (180, 180, 180, 255)
            else:
                surf.color = (255, 255, 255, 255)
            surface_map[flag] = gnd.add_surface(surf)

        wall_surface = GNDSurface()
        wall_surface.texture_id = wall_texture_id
        wall_surface.lightmap_id = lightmap_id
        wall_surface.color = (200, 200, 200, 255)
        wall_surface_id = gnd.add_surface(wall_surface)

        empty_surface = GNDSurface()
        empty_surface.texture_id = -1
        empty_surface_id = gnd.add_surface(empty_surface)

        gnd.cubes = [GNDCube() for _ in range(gnd.width * gnd.height)]

        for cy in range(gnd.height):
            for cx in range(gnd.width):
                cube = GNDCube()
                h_bl, h_br, h_tl, h_tr = self._get_cube_heights(cx, cy)
                cube.h_bottom_left = h_bl
                cube.h_bottom_right = h_br
                cube.h_top_left = h_tl
                cube.h_top_right = h_tr

                flag = self._get_dominant_flag_in_cube(cx, cy)

                if flag in [2, 3]:
                    water_level = min(h_bl, h_br, h_tl, h_tr)
                    if water_level < 0.1:
                        water_level = 2.0
                    cube.h_bottom_left = water_level
                    cube.h_bottom_right = water_level
                    cube.h_top_left = water_level
                    cube.h_top_right = water_level

                cube.surface_top = surface_map.get(flag, surface_map[0])

                if self._needs_wall(cx, cy, 'north'):
                    cube.surface_north = wall_surface_id
                else:
                    cube.surface_north = -1

                if self._needs_wall(cx, cy, 'east'):
                    cube.surface_east = wall_surface_id
                else:
                    cube.surface_east = -1

                if cx == gnd.width - 1:
                    cube.surface_east = empty_surface_id
                if cy == 0:
                    cube.surface_north = empty_surface_id

                gnd.set_cube(cx, cy, cube)

        return gnd


# ============================================================
# VISUALIZADOR 2D
# ============================================================

class GNDVisualizer:
    TEXTURE_COLORS = {
        'grass': (76, 175, 80), 'dirt': (121, 85, 72), 'cliff': (97, 97, 97),
        'water': (33, 150, 243), 'rock': (117, 117, 117), 'wood': (161, 136, 127),
        'sand': (255, 235, 59), 'snow': (255, 255, 255), 'lava': (244, 67, 54),
        'swamp': (104, 159, 56), 'black': (33, 33, 33),
    }

    @classmethod
    def render_preview(cls, gnd: GNDFile, gat: GATFile, cell_size: int = 8) -> Image.Image:
        width = gat.width * cell_size
        height = gat.height * cell_size
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for y in range(gat.height):
            for x in range(gat.width):
                flag = gat.get_flag_at(x, y)
                info = GAT_FLAG_INFO.get(flag, GAT_FLAG_INFO[0])
                hex_color = info['color'].lstrip('#')
                rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
                px = x * cell_size
                py = (gat.height - 1 - y) * cell_size
                draw.rectangle([px, py, px + cell_size - 1, py + cell_size - 1],
                              fill=rgb, outline=(20, 20, 20))
        return img


# ============================================================
# INTERFAZ GRÁFICA - CORREGIDA (ANCHO AJUSTADO)
# ============================================================

class GNDGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapas GND - Ragnarok Online (rAthena)")
        self.root.geometry("1400x900")
        self.root.configure(bg="#1e1e1e")

        self.current_gat = None
        self.current_gnd = None
        self.preview_image = None
        self.photo_image = None
        self.cell_size = 8
        self.preview_mode = "GAT"
        self.scroll_canvas = None

        self._build_ui()

    def _build_ui(self):
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(0, weight=1)

        # ==================== PANEL IZQUIERDO ====================
        left_container = tk.Frame(main_frame, bg="#2d2d2d", width=350)
        left_container.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_container.grid_propagate(False)
        left_container.rowconfigure(0, weight=0)
        left_container.rowconfigure(1, weight=1)
        left_container.columnconfigure(0, weight=1)

        # --- BOTONES DE ACCIÓN (SIEMPRE VISIBLES) ---
        action_frame = tk.Frame(left_container, bg="#2d2d2d", height=100)
        action_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        action_frame.grid_propagate(False)

        tk.Button(action_frame, text="▶ GENERAR GND", command=self._generate_gnd,
                 bg="#2196F3", fg="white", font=("Consolas", 11, "bold"),
                 activebackground="#1976D2", cursor="hand2",
                 height=1).pack(fill=tk.X, padx=2, pady=(0, 2))

        save_btn_frame = tk.Frame(action_frame, bg="#2d2d2d")
        save_btn_frame.pack(fill=tk.X, padx=2, pady=2)

        tk.Button(save_btn_frame, text="💾 Guardar GND", command=self._save_gnd,
                 bg="#2196F3", fg="white", font=("Consolas", 9),
                 activebackground="#1976D2", cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(save_btn_frame, text="🖼️ Guardar Preview", command=self._save_preview,
                 bg="#9C27B0", fg="white", font=("Consolas", 9),
                 activebackground="#7B1FA2", cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))

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

        # Frame interno con ANCHO CORREGIDO
        self.scroll_frame = tk.Frame(self.scroll_canvas, bg="#2d2d2d")
        # Ancho inicial: 350 (panel) - 10 (padx) - 20 (scrollbar) = 320
        self._scroll_frame_id = self.scroll_canvas.create_window(
            (0, 0), window=self.scroll_frame, anchor="nw", width=320
        )

        def configure_scroll_region(event):
            self.scroll_canvas.configure(scrollregion=self.scroll_canvas.bbox("all"))
            # Ajustar ancho al canvas real menos el ancho de la scrollbar (~20px)
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

        title = tk.Label(left_panel, text="🗺️ GND Generator", 
                        font=("Consolas", 16, "bold"), fg="#2196F3", bg="#2d2d2d")
        title.pack(pady=(10, 5))

        subtitle = tk.Label(left_panel, text="Para rAthena - Desde GAT", 
                           font=("Consolas", 10), fg="#888888", bg="#2d2d2d")
        subtitle.pack(pady=(0, 10))

        # --- Cargar GAT ---
        load_frame = tk.LabelFrame(left_panel, text="1. Cargar GAT", 
                                  font=("Consolas", 10, "bold"),
                                  fg="#ffffff", bg="#2d2d2d", bd=2)
        load_frame.pack(fill=tk.X, padx=5, pady=5)

        self.gat_path_var = tk.StringVar(value="")
        self.gat_entry = tk.Entry(load_frame, textvariable=self.gat_path_var, 
                                  font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                                  insertbackground="#ffffff", relief=tk.SUNKEN, bd=2)
        self.gat_entry.pack(fill=tk.X, padx=5, pady=(5, 2))
        self.gat_entry.insert(0, "Selecciona un archivo GAT...")
        self.gat_entry.config(fg="#888888")

        btn_frame = tk.Frame(load_frame, bg="#2d2d2d")
        btn_frame.pack(fill=tk.X, padx=5, pady=(2, 5))

        tk.Button(btn_frame, text="📂 Cargar GAT", command=self._load_gat,
                 bg="#4CAF50", fg="white", font=("Consolas", 9),
                 activebackground="#45a049", cursor="hand2").pack(side=tk.LEFT, padx=(0, 5))

        tk.Button(btn_frame, text="🎲 Generar GAT", command=self._generate_gat,
                 bg="#FF9800", fg="white", font=("Consolas", 9),
                 activebackground="#F57C00", cursor="hand2").pack(side=tk.LEFT)

        # --- Selector de preview ---
        preview_frame = tk.Frame(load_frame, bg="#2d2d2d")
        preview_frame.pack(fill=tk.X, padx=5, pady=(2, 5))
        
        tk.Label(preview_frame, text="Preview:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(side=tk.LEFT)
        
        self.preview_mode_var = tk.StringVar(value="GAT")
        preview_mode_combo = ttk.Combobox(preview_frame, textvariable=self.preview_mode_var,
                                          values=["GAT", "GND"],
                                          state="readonly", font=("Consolas", 9), width=6)
        preview_mode_combo.pack(side=tk.LEFT, padx=5)
        preview_mode_combo.bind("<<ComboboxSelected>>", self._on_preview_mode_change)

        # --- Configuración ---
        config_frame = tk.LabelFrame(left_panel, text="2. Configuración GND", 
                                    font=("Consolas", 10, "bold"),
                                    fg="#ffffff", bg="#2d2d2d", bd=2)
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(config_frame, text="Versión GND:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9, "bold")).pack(anchor=tk.W, padx=5, pady=(5, 0))

        version_frame = tk.Frame(config_frame, bg="#2d2d2d")
        version_frame.pack(fill=tk.X, padx=5, pady=2)

        self.version_var = tk.StringVar(value="1.7")
        version_combo = ttk.Combobox(version_frame, textvariable=self.version_var,
                                       values=["1.7", "1.8", "1.9"],
                                       state="readonly", font=("Consolas", 9), width=8)
        version_combo.pack(side=tk.LEFT, padx=(0, 5))
        version_combo.bind("<<ComboboxSelected>>", self._on_version_change)

        self.version_desc_label = tk.Label(version_frame, 
            text="Compatible con todos los clientes",
            fg="#4CAF50", bg="#2d2d2d", font=("Consolas", 8))
        self.version_desc_label.pack(side=tk.LEFT)

        tk.Label(config_frame, text="Bioma/Terreno:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(8, 0))
        self.terrain_var = tk.StringVar(value="pradera")
        terrain_combo = ttk.Combobox(config_frame, textvariable=self.terrain_var, 
                                       values=["pradera", "selva", "cerros", "desierto", 
                                               "isla", "paramo", "volcano", "swamp"],
                                       state="readonly", font=("Consolas", 9))
        terrain_combo.pack(fill=tk.X, padx=5, pady=2)

        tk.Label(config_frame, text="Escala del terreno:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.scale_var = tk.StringVar(value="10.0")
        tk.Entry(config_frame, textvariable=self.scale_var, width=10, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").pack(anchor=tk.W, padx=5, pady=2)

        # --- Agua ---
        self.water_frame = tk.LabelFrame(left_panel, text="💧 Configuración de Agua (v1.8+)", 
                                        font=("Consolas", 10, "bold"),
                                        fg="#2196F3", bg="#2d2d2d", bd=2)
        self.water_frame.pack(fill=tk.X, padx=5, pady=5)

        row = 0
        tk.Label(self.water_frame, text="Nivel:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.water_level_var = tk.StringVar(value="auto")
        tk.Entry(self.water_frame, textvariable=self.water_level_var, width=8, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
        tk.Label(self.water_frame, text="(auto)", fg="#888888", bg="#2d2d2d", 
                font=("Consolas", 8)).grid(row=row, column=2, sticky=tk.W, padx=2)
        row += 1

        tk.Label(self.water_frame, text="Tipo:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.water_type_var = tk.StringVar(value="auto")
        water_type_combo = ttk.Combobox(self.water_frame, textvariable=self.water_type_var,
                                          values=["auto", "0: Agua", "3: Hielo", "4: Lava", "5: Pantano"],
                                          state="readonly", font=("Consolas", 9), width=10)
        water_type_combo.grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
        row += 1

        tk.Label(self.water_frame, text="Onda Altura:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.wave_height_var = tk.StringVar(value="1.0")
        tk.Entry(self.water_frame, textvariable=self.wave_height_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
        row += 1

        tk.Label(self.water_frame, text="Onda Veloc.:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.wave_speed_var = tk.StringVar(value="2.0")
        tk.Entry(self.water_frame, textvariable=self.wave_speed_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)
        row += 1

        tk.Label(self.water_frame, text="Onda Pitch:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=row, column=0, sticky=tk.W, padx=5, pady=2)
        self.wave_pitch_var = tk.StringVar(value="50.0")
        tk.Entry(self.water_frame, textvariable=self.wave_pitch_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").grid(row=row, column=1, padx=5, pady=2, sticky=tk.W)

        # --- Texturas de Agua ---
        self.water_tex_frame = tk.LabelFrame(left_panel, text="🌊 Texturas de Agua (v1.9+)", 
                                            font=("Consolas", 10, "bold"),
                                            fg="#9C27B0", bg="#2d2d2d", bd=2)
        self.water_tex_frame.pack(fill=tk.X, padx=5, pady=5)

        self.water_tex_count_var = tk.StringVar(value="4")
        tk.Label(self.water_tex_frame, text="Cantidad:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(5, 0))
        tk.Entry(self.water_tex_frame, textvariable=self.water_tex_count_var, width=6, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
                insertbackground="#ffffff").pack(anchor=tk.W, padx=5, pady=2)

        self.water_tex_list = scrolledtext.ScrolledText(self.water_tex_frame, height=3, width=30,
                                                        font=("Consolas", 8),
                                                        bg="#1e1e1e", fg="#cccccc",
                                                        insertbackground="#ffffff")
        self.water_tex_list.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        self.water_tex_list.insert(tk.END, "\\texture\\water000.bmp\n")
        self.water_tex_list.insert(tk.END, "\\texture\\water001.bmp\n")
        self.water_tex_list.insert(tk.END, "\\texture\\water002.bmp\n")
        self.water_tex_list.insert(tk.END, "\\texture\\water003.bmp")

        # --- Información ---
        info_frame = tk.LabelFrame(left_panel, text="Información", 
                                  font=("Consolas", 10, "bold"),
                                  fg="#ffffff", bg="#2d2d2d", bd=2)
        info_frame.pack(fill=tk.X, padx=5, pady=5)

        self.info_label = tk.Label(info_frame, text="Carga un GAT para comenzar", 
                                  fg="#888888", bg="#2d2d2d", 
                                  font=("Consolas", 8), justify=tk.LEFT)
        self.info_label.pack(anchor=tk.W, padx=5, pady=5)

        # --- Texturas ---
        tex_frame = tk.LabelFrame(left_panel, text="Texturas Asignadas", 
                                 font=("Consolas", 10, "bold"),
                                 fg="#ffffff", bg="#2d2d2d", bd=2)
        tex_frame.pack(fill=tk.X, padx=5, pady=5)

        self.tex_text = scrolledtext.ScrolledText(tex_frame, height=5, width=30,
                                                  font=("Consolas", 8),
                                                  bg="#1e1e1e", fg="#cccccc",
                                                  insertbackground="#ffffff")
        self.tex_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # ==================== PANEL DERECHO ====================
        right_panel = tk.Frame(main_frame, bg="#1e1e1e")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)

        canvas_container = tk.Frame(right_panel, bg="#1e1e1e")
        canvas_container.grid(row=0, column=0, sticky="nsew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_container, bg="#0d0d0d", highlightthickness=0)
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

        self._on_version_change(None)

    # ============================================================
    # MÉTODOS DE CONTROL
    # ============================================================

    def _on_version_change(self, event):
        version = self.version_var.get()

        if version == "1.7":
            self.version_desc_label.configure(text="Compatible con todos los clientes", fg="#4CAF50")
            self._set_water_frame_state(tk.DISABLED)
            self._set_water_tex_frame_state(tk.DISABLED)
        elif version == "1.8":
            self.version_desc_label.configure(text="Agrega configuración de agua", fg="#2196F3")
            self._set_water_frame_state(tk.NORMAL)
            self._set_water_tex_frame_state(tk.DISABLED)
        elif version == "1.9":
            self.version_desc_label.configure(text="Agrega texturas de agua animadas", fg="#9C27B0")
            self._set_water_frame_state(tk.NORMAL)
            self._set_water_tex_frame_state(tk.NORMAL)

    def _set_water_frame_state(self, state):
        for child in self.water_frame.winfo_children():
            if isinstance(child, (tk.Entry, ttk.Combobox)):
                child.configure(state=state)

    def _set_water_tex_frame_state(self, state):
        for child in self.water_tex_frame.winfo_children():
            if isinstance(child, (tk.Entry, scrolledtext.ScrolledText)):
                child.configure(state=state)

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
                self.gat_entry.config(fg="#ffffff")
                self._update_info()
                self.preview_mode = "GAT"
                self.preview_mode_var.set("GAT")
                self._render_preview()
                self.status_bar.configure(text=f"GAT cargado: {self.current_gat.width}x{self.current_gat.height}")
                self.root.update()
                self.root.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el GAT:\n{e}")

    def _generate_gat(self):
        width, height = 100, 100
        gat = GATFile(width, height)

        seed = random.randint(0, 10000)
        for y in range(height):
            for x in range(width):
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
        self.gat_entry.config(fg="#FF9800")
        self._update_info()
        self.preview_mode = "GAT"
        self.preview_mode_var.set("GAT")
        self._render_preview()
        self.status_bar.configure(text=f"GAT generado: {width}x{height}")
        self.root.update()
        self.root.update_idletasks()

    def _generate_gnd(self):
        if not self.current_gat:
            messagebox.showwarning("Advertencia", "Primero carga o genera un GAT.")
            return

        try:
            terrain_type = self.terrain_var.get()
            version = self._parse_version()

            generator = GNDGenerator(self.current_gat, terrain_type, version)

            self.status_bar.configure(text=f"Generando GND v{version[0]}.{version[1]}...")
            self.root.update()

            self.current_gnd = generator.generate()

            try:
                scale = float(self.scale_var.get())
                self.current_gnd.scale = scale
            except ValueError:
                pass

            if self.current_gnd.is_version_18_or_higher():
                try:
                    level_str = self.water_level_var.get()
                    if level_str.lower() != "auto":
                        self.current_gnd.water_config.level = float(level_str)
                except ValueError:
                    pass

                try:
                    type_str = self.water_type_var.get()
                    if type_str != "auto":
                        self.current_gnd.water_config.type = int(type_str.split(':')[0])
                except (ValueError, IndexError):
                    pass

                try:
                    self.current_gnd.water_config.wave_height = float(self.wave_height_var.get())
                    self.current_gnd.water_config.wave_speed = float(self.wave_speed_var.get())
                    self.current_gnd.water_config.wave_pitch = float(self.wave_pitch_var.get())
                except ValueError:
                    pass

            if self.current_gnd.is_version_19_or_higher():
                try:
                    custom_textures = self.water_tex_list.get(1.0, tk.END).strip().split('\n')
                    custom_textures = [t.strip() for t in custom_textures if t.strip()]
                    if custom_textures:
                        self.current_gnd.water_textures = custom_textures
                        self.current_gnd.water_texture_count = len(custom_textures)
                except Exception:
                    pass

            self._update_texture_list()

            version_str = f"{self.current_gnd.version_major}.{self.current_gnd.version_minor}"
            water_info = ""
            if self.current_gnd.is_version_18_or_higher():
                wc = self.current_gnd.water_config
                water_info = f" | Agua: nivel={wc.level:.1f}, tipo={wc.type}"

            self.preview_mode = "GND"
            self.preview_mode_var.set("GND")
            self._render_preview()

            self.status_bar.configure(
                text=f"GND v{version_str} generado: {self.current_gnd.width}x{self.current_gnd.height} cubos, "
                     f"{len(self.current_gnd.texture_paths)} texturas{water_info}"
            )
            messagebox.showinfo("Éxito", f"Archivo GND v{version_str} generado correctamente.\n\nAhora puedes guardarlo o ver el preview en modo GND.")

        except Exception as e:
            messagebox.showerror("Error", f"Error generando GND:\n{e}")
            import traceback
            traceback.print_exc()

    def _on_preview_mode_change(self, event):
        self.preview_mode = self.preview_mode_var.get()
        self._render_preview()

    def _render_preview(self):
        if not self.current_gat:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Carga o genera un GAT primero", 
                                   fill="#888888", font=("Consolas", 16))
            return

        if self.preview_mode == "GND" and self.current_gnd:
            self.preview_image = self._render_gnd_preview()
            if self.preview_image:
                self.status_bar.configure(text=f"Preview GND: {self.current_gnd.width}x{self.current_gnd.height} cubos")
        else:
            self.preview_image = GNDVisualizer.render_preview(
                self.current_gnd if self.current_gnd else GNDFile(),
                self.current_gat,
                cell_size=self.cell_size
            )
            self.status_bar.configure(text=f"Preview GAT: {self.current_gat.width}x{self.current_gat.height} celdas")

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
            
            self.root.update()

    def _render_gnd_preview(self) -> Image.Image:
        if not self.current_gnd or not self.current_gat:
            return None

        texture_colors = {
            'grass': (76, 175, 80), 'dirt': (121, 85, 72), 'cliff': (97, 97, 97),
            'water': (33, 150, 243), 'rock': (117, 117, 117), 'wood': (161, 136, 127),
            'sand': (255, 235, 59), 'snow': (255, 255, 255), 'lava': (244, 67, 54),
            'swamp': (104, 159, 56), 'black': (33, 33, 33),
        }

        texture_colors_map = {}
        for idx, tex_path in enumerate(self.current_gnd.texture_paths):
            tex_name = tex_path.split('\\')[-1].replace('.bmp', '').lower()
            color = (128, 128, 128)
            for key, col in texture_colors.items():
                if key in tex_name:
                    color = col
                    break
            texture_colors_map[idx] = color

        cell_size = self.cell_size
        width = self.current_gat.width * cell_size
        height = self.current_gat.height * cell_size

        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for y in range(self.current_gat.height):
            for x in range(self.current_gat.width):
                cx = x // 2
                cy = y // 2
                
                if cx < self.current_gnd.width and cy < self.current_gnd.height:
                    cube = self.current_gnd.get_cube(cx, cy)
                    if cube:
                        surf_idx = cube.surface_top
                        if surf_idx >= 0 and surf_idx < len(self.current_gnd.surfaces):
                            tex_id = self.current_gnd.surfaces[surf_idx].texture_id
                            if tex_id >= 0 and tex_id in texture_colors_map:
                                color = texture_colors_map[tex_id]
                            else:
                                color = (128, 128, 128)
                        else:
                            color = (64, 64, 64)
                    else:
                        color = (64, 64, 64)
                else:
                    color = (0, 0, 0)

                px = x * cell_size
                py = (self.current_gat.height - 1 - y) * cell_size

                draw.rectangle([px, py, px + cell_size - 1, py + cell_size - 1],
                              fill=color, outline=(20, 20, 20))

        return img

    def _save_gnd(self):
        if not self.current_gnd:
            messagebox.showwarning("Advertencia", "No hay GND para guardar. Genera uno primero.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".gnd",
            filetypes=[("Archivos GND", "*.gnd"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.current_gnd.save(filepath)
                version = f"{self.current_gnd.version_major}.{self.current_gnd.version_minor}"
                self.status_bar.configure(text=f"GND v{version} guardado: {filepath}")
                messagebox.showinfo("Éxito", f"Archivo GND v{version} guardado:\n{filepath}")
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
GND Grid: {self.current_gat.width//2}x{self.current_gat.height//2} cubos"""

        self.info_label.configure(text=text)

    def _update_texture_list(self):
        if not self.current_gnd:
            return

        self.tex_text.delete(1.0, tk.END)
        self.tex_text.insert(tk.END, f"=== Texturas Difusas ({len(self.current_gnd.texture_paths)}) ===\n")
        for i, tex in enumerate(self.current_gnd.texture_paths):
            self.tex_text.insert(tk.END, f"[{i}] {tex}\n")

        if self.current_gnd.is_version_18_or_higher():
            wc = self.current_gnd.water_config
            self.tex_text.insert(tk.END, f"\n=== Configuración de Agua ===\n")
            self.tex_text.insert(tk.END, f"Nivel: {wc.level:.2f}\n")
            self.tex_text.insert(tk.END, f"Tipo: {wc.type}\n")
            self.tex_text.insert(tk.END, f"Onda Altura: {wc.wave_height:.2f}\n")
            self.tex_text.insert(tk.END, f"Onda Velocidad: {wc.wave_speed:.2f}\n")
            self.tex_text.insert(tk.END, f"Onda Pitch: {wc.wave_pitch:.2f}\n")

        if self.current_gnd.is_version_19_or_higher():
            self.tex_text.insert(tk.END, f"\n=== Texturas de Agua ({self.current_gnd.water_texture_count}) ===\n")
            for i, tex in enumerate(self.current_gnd.water_textures):
                self.tex_text.insert(tk.END, f"[{i}] {tex}\n")

        self.tex_text.insert(tk.END, f"\n=== Resumen ===\n")
        self.tex_text.insert(tk.END, f"Surfaces: {len(self.current_gnd.surfaces)}\n")
        self.tex_text.insert(tk.END, f"Cubes: {len(self.current_gnd.cubes)}\n")
        self.tex_text.insert(tk.END, f"Lightmaps: {len(self.current_gnd.lightmap_slices)}\n")
        self.tex_text.insert(tk.END, f"Versión: {self.current_gnd.version_major}.{self.current_gnd.version_minor}\n")


def main():
    root = tk.Tk()
    app = GNDGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()