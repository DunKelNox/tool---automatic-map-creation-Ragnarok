#!/usr/bin/env python3
"""
Generador Visual de Mapas GAT para Ragnarok Online (rAthena)
Creador: Fernando Garcia Valenzuela - DunKelNox (rAthena)
Vercion: 3.0
============================================================

Interfaz gráfica con cuadrícula ASCII para visualizar y editar mapas.
No requiere línea de comandos.

Dependencias:
    pip install numpy noise

Uso:
    python gat_generator_visual.py
"""

import struct
import random
import math
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
import threading
import time

try:
    import numpy as np
except ImportError:
    print("Instalando dependencias necesarias...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'numpy'])
    import numpy as np


# ============================================================
# CONSTANTES Y UTILIDADES
# ============================================================

FLAG_INFO = {
    0: {"name": "WALKABLE", "char": ".", "color": "#4CAF50", "desc": "Caminable"},
    1: {"name": "BLOCKED", "char": "#", "color": "#424242", "desc": "Bloqueado"},
    2: {"name": "WATER", "char": "~", "color": "#2196F3", "desc": "Agua"},
    3: {"name": "BLOCKED_WATER", "char": "=", "color": "#9C27B0", "desc": "Hielo/Lava/Barro"},
    4: {"name": "SPECIAL", "char": "!", "color": "#FF9800", "desc": "Especial (script)"},
    5: {"name": "BLOCKED_SPECIAL", "char": "@", "color": "#F44336", "desc": "Especial bloqueado"},
}

# ============================================================
# PARÁMETROS POR DEFECTO Y RANGOS PARA SLIDERS
# ============================================================

DEFAULT_PARAMS = {
    'pradera': {'water_level': 0.35, 'hill_threshold': 0.65},
    'selva': {'water_level': 0.20, 'dense_threshold': 0.55},
    'cerros': {'peak_threshold': 0.75, 'valley_level': 0.25},
    'desierto': {'water_level': 0.10, 'dune_threshold': 0.60, 'oasis_chance': 0.001},
    'isla': {'water_level': 0.35, 'beach_width': 0.08},
    'paramo': {'snow_level': 0.45, 'rock_threshold': 0.70, 'ice_chance': 0.03},
    'volcano': {'crater_radius': 0.18, 'lava_level': 0.12, 'slope_steepness': 0.65},
    'swamp': {'water_level': 0.25, 'mud_chance': 0.01, 'tree_chance': 0.08}
}

PARAM_RANGES = {
    'water_level': (0.0, 1.0, 0.01),
    'hill_threshold': (0.0, 1.0, 0.01),
    'dense_threshold': (0.0, 1.0, 0.01),
    'peak_threshold': (0.0, 1.0, 0.01),
    'valley_level': (0.0, 1.0, 0.01),
    'dune_threshold': (0.0, 1.0, 0.01),
    'oasis_chance': (0.0, 0.05, 0.0005),
    'beach_width': (0.0, 0.5, 0.01),
    'snow_level': (0.0, 1.0, 0.01),
    'rock_threshold': (0.0, 1.0, 0.01),
    'ice_chance': (0.0, 0.1, 0.001),
    'crater_radius': (0.0, 0.5, 0.01),
    'lava_level': (0.0, 0.5, 0.01),
    'slope_steepness': (0.0, 1.0, 0.01),
    'mud_chance': (0.0, 0.05, 0.0005),
    'tree_chance': (0.0, 0.2, 0.01)
}

ASCII_PREVIEW = {
    0: ".",  # WALKABLE - verde
    1: "#",  # BLOCKED - gris oscuro
    2: "~",  # WATER - azul
    3: "=",  # BLOCKED_WATER - morado
    4: "!",  # SPECIAL - naranja
    5: "@",  # BLOCKED_SPECIAL - rojo
}


class GATFile:
    """Representa un archivo GAT completo."""

    MAGIC = b"GRAT"
    VERSION_MAJOR = 1
    VERSION_MINOR = 2

    FLAG_NAMES = {k: v["name"] for k, v in FLAG_INFO.items()}

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

    def save(self, filepath):
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'wb') as f:
            f.write(self.MAGIC)
            f.write(struct.pack('B', self.VERSION_MAJOR))
            f.write(struct.pack('B', self.VERSION_MINOR))
            f.write(struct.pack('<i', self.width))
            f.write(struct.pack('<i', self.height))

            for h1, h2, h3, h4, flag in self.cells:
                f.write(struct.pack('<f', float(h1)))
                f.write(struct.pack('<f', float(h2)))
                f.write(struct.pack('<f', float(h3)))
                f.write(struct.pack('<f', float(h4)))
                f.write(struct.pack('<i', int(flag)))

        return filepath

    def export_to_csv(self, filepath, include_heights=True):
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            header = ['Y\\X'] + [str(x) for x in range(self.width)]
            writer.writerow(header)

            for y in range(self.height):
                row = [str(y)]
                for x in range(self.width):
                    idx = y * self.width + x
                    h1, h2, h3, h4, flag = self.cells[idx]
                    flag_name = self.FLAG_NAMES.get(flag, f"UNKNOWN_{flag}")

                    if include_heights:
                        cell_value = f"{flag_name};{h1:.4f};{h2:.4f};{h3:.4f};{h4:.4f}"
                    else:
                        cell_value = flag_name

                    row.append(cell_value)
                writer.writerow(row)

        return filepath

    @classmethod
    def import_from_csv(cls, filepath):
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"CSV no encontrado: {filepath}")

        name_to_flag = {v: k for k, v in cls.FLAG_NAMES.items()}

        with open(filepath, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            rows = list(reader)

        if len(rows) < 2:
            raise ValueError("CSV vacío o inválido")

        width = len(rows[0]) - 1
        height = len(rows) - 1

        gat = cls(width, height)

        for row in rows[1:]:
            if len(row) < 2:
                continue

            for x_idx in range(1, len(row)):
                cell_data = row[x_idx].strip()

                if not cell_data:
                    h1 = h2 = h3 = h4 = 0.0
                    flag = 0
                else:
                    parts = cell_data.split(';')
                    flag_name = parts[0].strip().upper()

                    if flag_name in name_to_flag:
                        flag = name_to_flag[flag_name]
                    else:
                        try:
                            flag = int(flag_name)
                        except ValueError:
                            flag = 0

                    if len(parts) >= 5:
                        h1 = float(parts[1])
                        h2 = float(parts[2])
                        h3 = float(parts[3])
                        h4 = float(parts[4])
                    else:
                        h1 = h2 = h3 = h4 = 0.0

                gat.cells.append((h1, h2, h3, h4, flag))

        return gat

    def get_statistics(self):
        if not self.cells:
            return {}

        flags = [cell[4] for cell in self.cells]
        heights = [cell[0] for cell in self.cells]

        return {
            'total_cells': len(self.cells),
            'walkable': flags.count(0),
            'blocked': flags.count(1),
            'water': flags.count(2),
            'blocked_water': flags.count(3),
            'special': flags.count(4),
            'blocked_special': flags.count(5),
            'min_height': min(heights),
            'max_height': max(heights),
            'avg_height': sum(heights) / len(heights)
        }

    def get_flag_at(self, x, y):
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y * self.width + x][4]
        return 0

    def set_flag_at(self, x, y, flag):
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = y * self.width + x
            h1, h2, h3, h4, _ = self.cells[idx]
            self.cells[idx] = (h1, h2, h3, h4, flag)


# ============================================================
# GENERADOR DE TERRENOS
# ============================================================

class GATGenerator:
    def __init__(self, width, height, seed=None):
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 100000)
    
    def _generate_heightmap(self, scale=50.0, octaves=6, persistence=0.5, lacunarity=2.0):
        """
        Genera el mapa de alturas normalizado correctamente.
        """
        # Crear un array para almacenar los valores
        heightmap = np.zeros((self.height, self.width), dtype=np.float32)
        
        # Llenar con valores de ruido
        for y in range(self.height):
            for x in range(self.width):
                value = snoise2(
                    x / scale, y / scale,
                    octaves=octaves, persistence=persistence,
                    lacunarity=lacunarity,
                    repeatx=self.width, repeaty=self.height,
                    base=self.seed
                )
                heightmap[y, x] = value
        
        # ¡NORMALIZACIÓN CORRECTA! Usar min y max reales
        min_val = heightmap.min()
        max_val = heightmap.max()
        range_val = max_val - min_val
        
        if range_val > 0:
            # Normalizar a [0, 1] usando el rango real
            heightmap = (heightmap - min_val) / range_val
        else:
            # Si todos los valores son iguales, llenar con 0.5
            heightmap.fill(0.5)
        
        return heightmap

    def _generate_slopemap(self, heightmap):
        slopemap = np.zeros((self.height, self.width), dtype=np.float32)
        vectors = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]

        for y in range(self.height):
            for x in range(self.width):
                slope = 0.0
                count = 0
                for dx, dy in vectors:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        slope += abs(float(heightmap[y,x]) - float(heightmap[ny,nx]))
                        count += 1
                slopemap[y, x] = slope / count if count > 0 else 0.0
        return slopemap

    def _get_cell_height(self, heightmap, x, y):
        base = float(heightmap[y, x]) * 20.0
        h1 = h2 = h3 = h4 = base

        if x + 1 < self.width:
            h2 = (base + float(heightmap[y, x+1]) * 20.0) / 2.0
            h4 = h2
        if y + 1 < self.height:
            h3 = (base + float(heightmap[y+1, x]) * 20.0) / 2.0
            h4 = h3
        if x + 1 < self.width and y + 1 < self.height:
            h4 = (base + float(heightmap[y, x+1])*20.0 + float(heightmap[y+1, x])*20.0 + 
                  float(heightmap[y+1, x+1])*20.0) / 4.0
        return h1, h2, h3, h4

    def _place_circular_patches(self, chance, radius_min, radius_max, seed_offset):
        patch_map = np.zeros((self.height, self.width), dtype=bool)
        if chance <= 0:
            return patch_map

        random.seed(self.seed + seed_offset)
        for y in range(self.height):
            for x in range(self.width):
                if random.random() < chance:
                    radius = random.randint(radius_min, radius_max)
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            if dx*dx + dy*dy <= radius*radius:
                                ny, nx = y + dy, x + dx
                                if 0 <= ny < self.height and 0 <= nx < self.width:
                                    patch_map[ny, nx] = True
        return patch_map


    def generate_pradera(self, water_level=0.35, hill_threshold=0.65):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=80.0, octaves=4, persistence=0.4, lacunarity=2.0)
        slopemap = self._generate_slopemap(heightmap)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                if h_val < water_level:
                    flag = 2  # Agua
                    h1 = h2 = h3 = h4 = water_level * 20.0
                elif h_val > hill_threshold:
                    flag = 1  # Colina
                    altura_extra = 1.5 + (h_val - hill_threshold) * 2.0
                    h1 *= altura_extra
                    h2 *= altura_extra
                    h3 *= altura_extra
                    h4 *= altura_extra
                else:
                    flag = 0  # Caminable
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_selva(self, water_level=0.2, dense_threshold=0.55):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=60.0, octaves=8, persistence=0.6, lacunarity=2.2)
        slopemap = self._generate_slopemap(heightmap)

        vegetation = np.zeros((self.height, self.width), dtype=np.float32)
        for y in range(self.height):
            for x in range(self.width):
                vegetation[y, x] = (snoise2(x/30.0+1000, y/30.0+1000, 
                    octaves=3, persistence=0.5, base=self.seed+1) + 1.0) / 2.0

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                veg_val = float(vegetation[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                if h_val < water_level:
                    flag = 2
                    h1 = h2 = h3 = h4 = water_level * 20.0
                elif s_val > 0.3:
                    flag = 1
                elif veg_val > dense_threshold and h_val > water_level + 0.1:
                    flag = 5
                elif veg_val > dense_threshold - 0.15:
                    flag = 4
                else:
                    flag = 0
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_cerros(self, peak_threshold=0.75, valley_level=0.25):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=40.0, octaves=6, persistence=0.7, lacunarity=2.5)
        slopemap = self._generate_slopemap(heightmap)
        heightmap = np.power(heightmap, 1.5)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                if h_val < valley_level:
                    if h_val < valley_level * 0.5:
                        flag = 2
                        h1 = h2 = h3 = h4 = valley_level * 0.5 * 30.0
                    else:
                        flag = 0
                elif s_val > 0.4 or h_val > peak_threshold:
                    flag = 1
                    h1 *= 1.5; h2 *= 1.5; h3 *= 1.5; h4 *= 1.5
                elif s_val > 0.2:
                    flag = 5
                else:
                    flag = 0
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_desierto(self, water_level=0.10, dune_threshold=0.60, oasis_chance=0.001):
        """
        Genera un desierto con dunas y oasis ocasionales.
        water_level: Nivel de agua (muy bajo para desierto)
        dune_threshold: Umbral para dunas (colinas de arena)
        oasis_chance: Probabilidad de oasis (reducida)
        """
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=30.0, octaves=4, persistence=0.5, lacunarity=2.0)
        slopemap = self._generate_slopemap(heightmap)
        
        # Aumentar el contraste para dunas más definidas
        heightmap = np.power(heightmap, 1.2)
        
        # Oasis ocasionales (manchas de agua muy raras)
        oasis_map = self._place_circular_patches(oasis_chance, 2, 5, 500)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                # Oasis (agua) - muy raros y pequeños
                if oasis_map[y, x]:
                    flag = 2
                    h1 = h2 = h3 = h4 = 1.0
                # Dunas (colinas de arena) - basado en altura y pendiente
                elif h_val > dune_threshold:
                    flag = 1  # Duna (bloqueado)
                    # Altura moderada para dunas
                    factor = 1.2 + (h_val - dune_threshold) * 1.5
                    h1 *= factor; h2 *= factor; h3 *= factor; h4 *= factor
                else:
                    flag = 0  # Arena caminable
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_isla(self, water_level=0.35, beach_width=0.08):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=70.0, octaves=5, persistence=0.5, lacunarity=2.0)
        slopemap = self._generate_slopemap(heightmap)

        center_x, center_y = self.width / 2.0, self.height / 2.0
        max_dist = math.sqrt(center_x**2 + center_y**2)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                dist = math.sqrt((x - center_x)**2 + (y - center_y)**2) / max_dist
                island_mask = max(0.0, 1.0 - (dist ** 2))
                h_val = h_val * island_mask
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)
                h1 *= island_mask; h2 *= island_mask; h3 *= island_mask; h4 *= island_mask

                if h_val < water_level:
                    flag = 2
                    h1 = h2 = h3 = h4 = water_level * 15.0
                elif h_val < water_level + beach_width:
                    flag = 0
                elif s_val > 0.3 and h_val > 0.6:
                    flag = 1
                else:
                    flag = 0
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_paramo(self, snow_level=0.45, rock_threshold=0.7, ice_chance=0.03):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=50.0, octaves=8, persistence=0.6, lacunarity=2.3)
        slopemap = self._generate_slopemap(heightmap)
        heightmap = np.power(heightmap, 1.3)

        ice_map = self._place_circular_patches(ice_chance, 2, 5, 999)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                if ice_map[y, x]:
                    flag = 3
                    h1 = h2 = h3 = h4 = 0.5
                elif h_val < 0.08:
                    flag = 2
                    h1 = h2 = h3 = h4 = 0.0
                elif h_val > snow_level:
                    if s_val > rock_threshold:
                        flag = 1
                        h1 *= 1.2; h2 *= 1.2; h3 *= 1.2; h4 *= 1.2
                    else:
                        flag = 0
                elif s_val > 0.4:
                    flag = 5
                else:
                    flag = 0
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_volcano(self, crater_radius=0.18, lava_level=0.12, slope_steepness=0.65):
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=30.0, octaves=6, persistence=0.6, lacunarity=2.5)
        slopemap = self._generate_slopemap(heightmap)

        center_x, center_y = self.width / 2.0, self.height / 2.0
        max_dist = math.sqrt(center_x**2 + center_y**2)

        volcano_profile = np.zeros((self.height, self.width), dtype=np.float32)
        for y in range(self.height):
            for x in range(self.width):
                dist = math.sqrt((x - center_x)**2 + (y - center_y)**2) / max_dist
                dist = max(0.0, min(1.0, dist))

                if dist < crater_radius:
                    volcano_profile[y, x] = lava_level + (dist / crater_radius) * 0.15
                else:
                    normalized_dist = (dist - crater_radius) / (1.0 - crater_radius)
                    volcano_profile[y, x] = 0.25 + (1.0 - normalized_dist ** 0.6) * 0.75

        blended_height = heightmap * 0.3 + volcano_profile * 0.7
        blended_height = np.clip(blended_height, 0.0, 1.0)

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(blended_height[y, x])
                s_val = float(slopemap[y, x])
                dist = math.sqrt((x - center_x)**2 + (y - center_y)**2) / max_dist
                dist = max(0.0, min(1.0, dist))

                height_scale = h_val * 25.0
                h1 = h2 = h3 = h4 = height_scale

                if dist < crater_radius * 0.7:
                    flag = 3
                    h1 = h2 = h3 = h4 = lava_level * 20.0
                elif dist < crater_radius:
                    flag = 1
                    h1 = h2 = h3 = h4 = (lava_level + 0.1) * 20.0
                elif s_val > slope_steepness:
                    flag = 1
                elif dist < crater_radius + 0.15:
                    flag = 4
                else:
                    flag = 0
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat

    def generate_swamp(self, water_level=0.25, mud_chance=0.01, tree_chance=0.08):
        """
        Pantano con tierra firme y pocas zonas de agua/barro.
        """
        gat = GATFile(self.width, self.height)
        heightmap = self._generate_heightmap(scale=80.0, octaves=4, persistence=0.4, lacunarity=2.0)
        slopemap = self._generate_slopemap(heightmap)
        
        # Terreno con más variación
        heightmap = heightmap * 0.6 + 0.2

        # Parches de barro (MUY reducidos)
        mud_patches = self._place_circular_patches(mud_chance, 2, 3, 200)
        water_patches = self._place_circular_patches(mud_chance * 0.5, 1, 2, 300)

        # Árboles dispersos
        tree_map = np.zeros((self.height, self.width), dtype=bool)
        random.seed(self.seed + 400)
        for y in range(self.height):
            for x in range(self.width):
                if (random.random() < tree_chance and 
                    not mud_patches[y, x] and 
                    not water_patches[y, x] and
                    heightmap[y, x] > water_level + 0.05):
                    tree_map[y, x] = True

        for y in range(self.height):
            for x in range(self.width):
                h_val = float(heightmap[y, x])
                s_val = float(slopemap[y, x])
                h1, h2, h3, h4 = self._get_cell_height(heightmap, x, y)

                # Árboles en tierra firme
                if tree_map[y, x]:
                    flag = 5  # Especial bloqueado
                    h1 *= 1.3; h2 *= 1.3; h3 *= 1.3; h4 *= 1.3
                # Barro profundo (muy raro)
                elif mud_patches[y, x]:
                    flag = 3  # Blocked water
                    h1 = h2 = h3 = h4 = 0.5
                # Agua superficial (rara)
                elif water_patches[y, x]:
                    flag = 2  # Water
                    h1 = h2 = h3 = h4 = 0.3
                # Zonas bajas (agua)
                elif h_val < water_level:
                    flag = 2  # Water
                    h1 = h2 = h3 = h4 = water_level * 4.0
                # Colinas pequeñas
                elif s_val > 0.15 and h_val > 0.6:
                    flag = 1  # Blocked
                    h1 *= 1.3; h2 *= 1.3; h3 *= 1.3; h4 *= 1.3
                # Zonas especiales (hierba alta, arbustos)
                elif h_val > water_level + 0.1 and h_val < 0.45:
                    flag = 4  # Special
                else:
                    flag = 0  # Caminable
                gat.cells.append((h1, h2, h3, h4, flag))
        return gat


# ============================================================
# INTERFAZ GRÁFICA - CON SCROLL EN PANEL IZQUIERDO
# ============================================================

class GATGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Generador de Mapas GAT - Ragnarok Online (rAthena)")
        self.root.geometry("1200x800")
        self.root.configure(bg="#1e1e1e")

        self.current_gat = None
        self.selected_flag = 0
        self.cell_size = 12  # Tamaño de cada celda en píxeles
        self.current_params = None          # Últimos valores usados (diccionario)
        self.params_window = None           # Referencia a la ventana flotante
        self.param_sliders = {}             # Referencias a los sliders

        self._build_ui()

    def _build_ui(self):
        # Frame principal dividido en izquierda (controles) y derecha (canvas)
        main_frame = tk.Frame(self.root, bg="#1e1e1e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        main_frame.columnconfigure(0, weight=0)  # Panel izquierdo fijo
        main_frame.columnconfigure(1, weight=1)  # Canvas expandible
        main_frame.rowconfigure(0, weight=1)

        # ==================== PANEL IZQUIERDO CON SCROLL ====================
        left_container = tk.Frame(main_frame, bg="#2d2d2d", width=300)
        left_container.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left_container.grid_propagate(False)
        left_container.rowconfigure(0, weight=0)  # Botones fijos
        left_container.rowconfigure(1, weight=1)  # Scrollable
        left_container.columnconfigure(0, weight=1)

        # --- BOTONES DE ACCIÓN (SIEMPRE VISIBLES) ---
        action_frame = tk.Frame(left_container, bg="#2d2d2d", height=80)
        action_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        action_frame.grid_propagate(False)

        tk.Button(action_frame, text="▶ GENERAR", command=self._generate_map,
                 bg="#4CAF50", fg="white", font=("Consolas", 11, "bold"),
                 activebackground="#45a049", cursor="hand2",
                 height=1).pack(fill=tk.X, padx=2, pady=(0, 2))

        save_btn_frame = tk.Frame(action_frame, bg="#2d2d2d")
        save_btn_frame.pack(fill=tk.X, padx=2, pady=2)

        tk.Button(save_btn_frame, text="💾 Guardar GAT", command=self._save_gat,
                 bg="#2196F3", fg="white", font=("Consolas", 9),
                 activebackground="#1976D2", cursor="hand2").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2))

        tk.Button(save_btn_frame, text="📂 Cargar GAT", command=self._load_gat,
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
            (0, 0), window=self.scroll_frame, anchor="nw", width=270
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

        # Título
        title = tk.Label(left_panel, text="🗺️ GAT Generator", 
                        font=("Consolas", 16, "bold"), fg="#4CAF50", bg="#2d2d2d")
        title.pack(pady=(15, 5))

        subtitle = tk.Label(left_panel, text="Para rAthena", 
                        font=("Consolas", 10), fg="#888888", bg="#2d2d2d")
        subtitle.pack(pady=(0, 15))

        # --- Sección: Generar ---
        gen_frame = tk.LabelFrame(left_panel, text="Generar Mapa", 
                                font=("Consolas", 10, "bold"),
                                fg="#ffffff", bg="#2d2d2d", bd=2)
        gen_frame.pack(fill=tk.X, padx=5, pady=5)

        # Botón para abrir ventana de ajustes
        tk.Button(gen_frame, text="⚙ Ajustes", command=self._open_params_window,
            bg="#FF9800", fg="white", font=("Consolas", 10, "bold"),
            activebackground="#F57C00", cursor="hand2").pack(fill=tk.X, padx=5, pady=5)

        # Tipo de terreno
        tk.Label(gen_frame, text="Tipo:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(5, 0))
        self.terrain_var = tk.StringVar(value="pradera")
        self.terrain_var.trace('w', self._on_terrain_changed)
        terrain_combo = ttk.Combobox(gen_frame, textvariable=self.terrain_var, 
                                    values=["pradera", "selva", "cerros", "desierto", 
                                            "isla", "paramo", "volcano", "swamp"],
                                    state="readonly", font=("Consolas", 9))
        terrain_combo.pack(fill=tk.X, padx=5, pady=2)

        # Dimensiones
        dim_frame = tk.Frame(gen_frame, bg="#2d2d2d")
        dim_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(dim_frame, text="Ancho:", fg="#cccccc", bg="#2d2d2d", 
                font=("Consolas", 9)).grid(row=0, column=0, sticky=tk.W)
        self.width_var = tk.StringVar(value="100")
        tk.Entry(dim_frame, textvariable=self.width_var, width=8, 
                font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff", 
                insertbackground="#ffffff").grid(row=0, column=1, padx=5)

        tk.Label(dim_frame, text="Alto:", fg="#cccccc", bg="#2d2d2d", 
            font=("Consolas", 9)).grid(row=1, column=0, sticky=tk.W, pady=(5,0))
        self.height_var = tk.StringVar(value="100")
        tk.Entry(dim_frame, textvariable=self.height_var, width=8, 
            font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
            insertbackground="#ffffff").grid(row=1, column=1, padx=5, pady=(5,0))

        # Semilla
        seed_frame = tk.Frame(gen_frame, bg="#2d2d2d")
        seed_frame.pack(fill=tk.X, padx=5, pady=5)
        tk.Label(seed_frame, text="Semilla:", fg="#cccccc", bg="#2d2d2d", 
            font=("Consolas", 9)).pack(side=tk.LEFT)
        self.seed_var = tk.StringVar(value="")
        tk.Entry(seed_frame, textvariable=self.seed_var, width=12, 
            font=("Consolas", 9), bg="#3d3d3d", fg="#ffffff",
            insertbackground="#ffffff").pack(side=tk.LEFT, padx=5)
        tk.Button(seed_frame, text="🎲", command=self._random_seed, 
             bg="#4CAF50", fg="white", font=("Consolas", 8), width=2).pack(side=tk.LEFT)

        # --- Sección: Herramientas de edición ---
        edit_frame = tk.LabelFrame(left_panel, text="Herramientas de Edición", 
                               font=("Consolas", 10, "bold"),
                               fg="#ffffff", bg="#2d2d2d", bd=2)
        edit_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(edit_frame, text="Pincel (click en el mapa):", 
            fg="#cccccc", bg="#2d2d2d", font=("Consolas", 9)).pack(anchor=tk.W, padx=5, pady=(5,0))

        # Botones de flags
        flags_frame = tk.Frame(edit_frame, bg="#2d2d2d")
        flags_frame.pack(fill=tk.X, padx=5, pady=5)

        self.flag_buttons = {}
        for flag_id, info in FLAG_INFO.items():
            btn = tk.Button(flags_frame, text=f"{info['char']} {info['name']}",
                        bg=info["color"], fg="white" if flag_id != 0 else "black",
                        font=("Consolas", 8), 
                        command=lambda fid=flag_id: self._select_flag(fid))
            btn.pack(fill=tk.X, pady=1)
            self.flag_buttons[flag_id] = btn

        # --- Sección: Exportar/Importar ---
        io_frame = tk.LabelFrame(left_panel, text="Exportar / Importar", 
                             font=("Consolas", 10, "bold"),
                             fg="#ffffff", bg="#2d2d2d", bd=2)
        io_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(io_frame, text="📄 Exportar CSV", command=self._export_csv,
             bg="#FF9800", fg="white", font=("Consolas", 9),
             activebackground="#F57C00", cursor="hand2").pack(fill=tk.X, padx=5, pady=(5,2))

        tk.Button(io_frame, text="📄 Importar CSV", command=self._import_csv,
             bg="#FF9800", fg="white", font=("Consolas", 9),
             activebackground="#F57C00", cursor="hand2").pack(fill=tk.X, padx=5, pady=(2,5))

        # --- Sección: Estadísticas ---
        self.stats_frame = tk.LabelFrame(left_panel, text="Estadísticas", 
                                     font=("Consolas", 10, "bold"),
                                     fg="#ffffff", bg="#2d2d2d", bd=2)
        self.stats_frame.pack(fill=tk.X, padx=5, pady=5)

        self.stats_label = tk.Label(self.stats_frame, text="Sin mapa cargado", 
                                 fg="#888888", bg="#2d2d2d", 
                                 font=("Consolas", 8), justify=tk.LEFT)
        self.stats_label.pack(anchor=tk.W, padx=5, pady=5)

        # --- Leyenda ASCII ---
        legend_frame = tk.LabelFrame(left_panel, text="Leyenda ASCII", 
                                 font=("Consolas", 10, "bold"),
                                 fg="#ffffff", bg="#2d2d2d", bd=2)
        legend_frame.pack(fill=tk.X, padx=5, pady=5)

        legend_text = ""
        for flag_id, info in FLAG_INFO.items():
            legend_text += f"{info['char']} = {info['name']}\n"

        legend_label = tk.Label(legend_frame, text=legend_text.strip(), 
                           fg="#cccccc", bg="#2d2d2d", 
                           font=("Consolas", 8), justify=tk.LEFT)
        legend_label.pack(anchor=tk.W, padx=5, pady=5)

        # ==================== PANEL DERECHO: CANVAS ====================
        right_panel = tk.Frame(main_frame, bg="#1e1e1e")
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.rowconfigure(0, weight=1)
        right_panel.columnconfigure(0, weight=1)

        # Canvas con scrollbars
        canvas_container = tk.Frame(right_panel, bg="#1e1e1e")
        canvas_container.grid(row=0, column=0, sticky="nsew")
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_container, bg="#0d0d0d", 
                           highlightthickness=0, cursor="crosshair")
        self.canvas.grid(row=0, column=0, sticky="nsew")

        h_scroll = tk.Scrollbar(canvas_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        h_scroll.grid(row=1, column=0, sticky="ew")

        v_scroll = tk.Scrollbar(canvas_container, orient=tk.VERTICAL, command=self.canvas.yview)
        v_scroll.grid(row=0, column=1, sticky="ns")

        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        # Eventos del canvas
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)

        # Barra de estado (CREAR ANTES DE _select_flag)
        self.status_bar = tk.Label(self.root, text="Listo. Genera un mapa para comenzar.", 
                              bd=1, relief=tk.SUNKEN, anchor=tk.W,
                              bg="#2d2d2d", fg="#cccccc", font=("Consolas", 9))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Ahora seleccionar el flag por defecto (después de crear status_bar)
        self._select_flag(0)  # Seleccionar WALKABLE por defecto

    def _random_seed(self):
        self.seed_var.set(str(random.randint(1, 999999)))

    def _select_flag(self, flag_id):
        self.selected_flag = flag_id
        for fid, btn in self.flag_buttons.items():
            if fid == flag_id:
                btn.configure(relief=tk.SUNKEN, bd=3)
            else:
                btn.configure(relief=tk.RAISED, bd=1)

        info = FLAG_INFO[flag_id]
        self.status_bar.configure(text=f"Pincel seleccionado: {info['name']} ({info['desc']})")

    def _open_params_window(self):
        if self.params_window is not None and self.params_window.winfo_exists():
            self.params_window.lift()
            return

        terrain = self.terrain_var.get()
        default_params = DEFAULT_PARAMS.get(terrain, {})
        
        # Si no hay parámetros guardados, usar los por defecto
        if self.current_params is None:
            self.current_params = default_params.copy()
        
        # Crear ventana
        self.params_window = tk.Toplevel(self.root)
        self.params_window.title("Ajustes del Terreno")
        self.params_window.geometry("350x400")
        self.params_window.transient(self.root)
        self.params_window.grab_set()
        self.params_window.configure(bg="#2d2d2d")
        
        # Etiqueta del terreno
        tk.Label(self.params_window, text=f"Terreno: {terrain.title()}", 
                font=("Consolas", 12, "bold"), fg="#4CAF50", bg="#2d2d2d").pack(pady=10)
        
        # Frame para los sliders
        container = tk.Frame(self.params_window, bg="#2d2d2d")
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Construir sliders
        self._build_sliders(container, terrain, self.current_params)
        
        # Botón restablecer
        tk.Button(self.params_window, text="↺ Restablecer valores por defecto",
                command=self._reset_params_in_window, bg="#555555", fg="white",
                font=("Consolas", 9), activebackground="#777777").pack(pady=10)
        
        # Al cerrar, guardar los valores actuales (se actualizan automáticamente)
        self.params_window.protocol("WM_DELETE_WINDOW", self._close_params_window)

    def _build_sliders(self, container, terrain, params):
        # Limpiar el contenedor por si se llama de nuevo
        for widget in container.winfo_children():
            widget.destroy()
        
        self.param_sliders = {}  # guardar referencias a los sliders y variables
        
        for param_name, default_value in params.items():
            min_val, max_val, step = PARAM_RANGES.get(param_name, (0.0, 1.0, 0.01))
            
            frame = tk.Frame(container, bg="#2d2d2d")
            frame.pack(fill=tk.X, pady=3)
            
            label = tk.Label(frame, text=param_name.replace('_', ' ').title() + ":", 
                            fg="#cccccc", bg="#2d2d2d", font=("Consolas", 8), width=15, anchor='w')
            label.pack(side=tk.LEFT)
            
            var = tk.DoubleVar(value=default_value)
            slider = tk.Scale(frame, from_=min_val, to=max_val, resolution=step,
                            orient=tk.HORIZONTAL, variable=var,
                            bg="#3d3d3d", fg="#ffffff", highlightthickness=0,
                            length=150, showvalue=False)
            slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            value_label = tk.Label(frame, text=f"{default_value:.{self._get_decimals(step)}f}", 
                                fg="#4CAF50", bg="#2d2d2d", font=("Consolas", 8), width=6)
            value_label.pack(side=tk.LEFT, padx=(0,5))
            
            # Actualizar la etiqueta y el self.current_params al mover el slider
            def update(param=param_name, lbl=value_label, stp=step, v=var):
                val = v.get()
                decimals = self._get_decimals(stp)
                lbl.config(text=f"{val:.{decimals}f}")
                # Actualizar el diccionario de parámetros actuales
                if self.current_params is not None:
                    self.current_params[param] = val
            
            slider.config(command=update)
            
            # Guardar referencias
            self.param_sliders[param_name] = (slider, var, value_label)

    def _get_decimals(self, step):
        if step >= 1:
            return 0
        return len(str(step).split('.')[-1])

    def _reset_params_in_window(self):
        terrain = self.terrain_var.get()
        default_params = DEFAULT_PARAMS.get(terrain, {})
        # Actualizar el diccionario actual
        if self.current_params is not None:
            self.current_params.update(default_params)
        else:
            self.current_params = default_params.copy()
        # Reconstruir sliders con los nuevos valores
        if self.params_window is not None and self.params_window.winfo_exists():
            container = self.params_window.winfo_children()[1]  # el segundo hijo es el container
            self._build_sliders(container, terrain, self.current_params)

    def _close_params_window(self):
        if self.params_window is not None:
            self.params_window.destroy()
            self.params_window = None
        # Los valores ya están guardados en self.current_params (se actualizan en tiempo real)

    def _on_terrain_changed(self, *args):
        # Si la ventana de ajustes está abierta, refrescar su contenido
        if self.params_window is not None and self.params_window.winfo_exists():
            self.current_params = None  # para que tome los nuevos por defecto
            terrain = self.terrain_var.get()
            default_params = DEFAULT_PARAMS.get(terrain, {})
            self.current_params = default_params.copy()
            container = self.params_window.winfo_children()[1]
            self._build_sliders(container, terrain, self.current_params)

    def _generate_map(self):
        try:
            width = int(self.width_var.get())
            height = int(self.height_var.get())
            if width <= 0 or height <= 0 or width > 500 or height > 500:
                messagebox.showerror("Error", "Dimensiones inválidas. Máximo 500x500.")
                return
        except ValueError:
            messagebox.showerror("Error", "Dimensiones inválidas.")
            return

        seed = None
        if self.seed_var.get().strip():
            try:
                seed = int(self.seed_var.get())
            except ValueError:
                pass

        terrain_type = self.terrain_var.get()
        
        # OBTENER PARÁMETROS DE LOS SLIDERS
        if self.current_params is None:
            params = DEFAULT_PARAMS.get(terrain_type, {})
        else:
            default_params = DEFAULT_PARAMS.get(terrain_type, {})
            params = default_params.copy()
            params.update(self.current_params)
        
        # Deshabilitar botón de generar mientras se procesa
        self.status_bar.configure(text=f"Generando {terrain_type} {width}x{height}... (esto puede tomar un momento)")
        
        # Crear una ventana de progreso
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Generando Mapa...")
        progress_window.geometry("300x100")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        tk.Label(progress_window, text=f"Generando {terrain_type} {width}x{height}", 
                font=("Consolas", 10)).pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, length=250, mode='indeterminate')
        progress_bar.pack(pady=10)
        progress_bar.start(10)
        
        # Función para generar en un hilo separado
        def generate_in_thread():
            try:
                generator = GATGenerator(width, height, seed=seed)
                
                terrain_map = {
                    'pradera': generator.generate_pradera,
                    'selva': generator.generate_selva,
                    'cerros': generator.generate_cerros,
                    'desierto': generator.generate_desierto,
                    'isla': generator.generate_isla,
                    'paramo': generator.generate_paramo,
                    'volcano': generator.generate_volcano,
                    'swamp': generator.generate_swamp
                }
                
                # Generar el mapa con los parámetros
                self.current_gat = terrain_map[terrain_type](**params)
                
                # Actualizar la interfaz en el hilo principal
                self.root.after(0, self._on_generation_complete, progress_window, terrain_type, width, height)
                
            except Exception as e:
                self.root.after(0, self._on_generation_error, progress_window, str(e))
        
        # Iniciar el hilo
        thread = threading.Thread(target=generate_in_thread, daemon=True)
        thread.start()

    def _on_generation_complete(self, progress_window, terrain_type, width, height):
        """Callback cuando la generación se completa"""
        progress_window.destroy()
        self._render_map()
        self._update_stats()
        self.status_bar.configure(text=f"Mapa '{terrain_type}' generado: {width}x{height}")

    def _on_generation_error(self, progress_window, error_msg):
        """Callback cuando hay un error en la generación"""
        progress_window.destroy()
        messagebox.showerror("Error", f"Error al generar el mapa:\n{error_msg}")
        self.status_bar.configure(text="Error al generar el mapa")

    def _render_map(self):
        if not self.current_gat:
            return

        self.canvas.delete("all")

        gat = self.current_gat
        cell_size = self.cell_size

        # Configurar scroll region
        self.canvas.configure(scrollregion=(0, 0, gat.width * cell_size, gat.height * cell_size))

        # Dibujar celdas
        for y in range(gat.height):
            for x in range(gat.width):
                idx = y * gat.width + x
                flag = gat.cells[idx][4]
                info = FLAG_INFO.get(flag, FLAG_INFO[0])

                x1 = x * cell_size
                y1 = y * cell_size
                x2 = x1 + cell_size
                y2 = y1 + cell_size

                # Rectángulo de color
                self.canvas.create_rectangle(
                    x1, y1, x2, y2,
                    fill=info["color"], outline="#1a1a1a", width=1,
                    tags=f"cell_{x}_{y}"
                )

                # Carácter ASCII si la celda es suficientemente grande
                if cell_size >= 10:
                    self.canvas.create_text(
                        x1 + cell_size // 2, y1 + cell_size // 2,
                        text=info["char"], fill="white" if flag != 0 else "black",
                        font=("Consolas", max(6, cell_size - 4)),
                        tags=f"text_{x}_{y}"
                    )

    def _on_canvas_click(self, event):
        self._paint_cell(event)

    def _on_canvas_drag(self, event):
        self._paint_cell(event)

    def _paint_cell(self, event):
        if not self.current_gat:
            return

        # Convertir coordenadas del canvas a coordenadas de celda
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)

        cell_size = self.cell_size
        x = int(canvas_x // cell_size)
        y = int(canvas_y // cell_size)

        if 0 <= x < self.current_gat.width and 0 <= y < self.current_gat.height:
            self.current_gat.set_flag_at(x, y, self.selected_flag)

            # Redibujar solo esa celda
            idx = y * self.current_gat.width + x
            flag = self.current_gat.cells[idx][4]
            info = FLAG_INFO.get(flag, FLAG_INFO[0])

            x1 = x * cell_size
            y1 = y * cell_size
            x2 = x1 + cell_size
            y2 = y1 + cell_size

            self.canvas.delete(f"cell_{x}_{y}")
            self.canvas.delete(f"text_{x}_{y}")

            self.canvas.create_rectangle(
                x1, y1, x2, y2,
                fill=info["color"], outline="#1a1a1a", width=1,
                tags=f"cell_{x}_{y}"
            )

            if cell_size >= 10:
                self.canvas.create_text(
                    x1 + cell_size // 2, y1 + cell_size // 2,
                    text=info["char"], fill="white" if flag != 0 else "black",
                    font=("Consolas", max(6, cell_size - 4)),
                    tags=f"text_{x}_{y}"
                )

            self._update_stats()

    def _update_stats(self):
        if not self.current_gat:
            return

        stats = self.current_gat.get_statistics()
        text = f"""Celdas: {stats['total_cells']}
WALKABLE (.) : {stats['walkable']} ({stats['walkable']/stats['total_cells']*100:.1f}%)
BLOCKED (#)  : {stats['blocked']} ({stats['blocked']/stats['total_cells']*100:.1f}%)
WATER (~)    : {stats['water']} ({stats['water']/stats['total_cells']*100:.1f}%)
BLOCKED_WATER(=) : {stats['blocked_water']} ({stats['blocked_water']/stats['total_cells']*100:.1f}%)
SPECIAL (!)  : {stats['special']} ({stats['special']/stats['total_cells']*100:.1f}%)
BLOCKED_SPECIAL(@) : {stats['blocked_special']} ({stats['blocked_special']/stats['total_cells']*100:.1f}%)
Altura min: {stats['min_height']:.2f}
Altura max: {stats['max_height']:.2f}
Altura avg: {stats['avg_height']:.2f}"""

        self.stats_label.configure(text=text)

    def _save_gat(self):
        if not self.current_gat:
            messagebox.showwarning("Advertencia", "No hay mapa para guardar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".gat",
            filetypes=[("Archivos GAT", "*.gat"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            self.current_gat.save(filepath)
            self.status_bar.configure(text=f"Guardado: {filepath}")

    def _load_gat(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Archivos GAT", "*.gat"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.current_gat = GATFile.load(filepath)
                self.width_var.set(str(self.current_gat.width))
                self.height_var.set(str(self.current_gat.height))
                self._render_map()
                self._update_stats()
                self.status_bar.configure(text=f"Cargado: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el archivo:\n{e}")

    def _export_csv(self):
        if not self.current_gat:
            messagebox.showwarning("Advertencia", "No hay mapa para exportar.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            self.current_gat.export_to_csv(filepath, include_heights=True)
            self.status_bar.configure(text=f"CSV exportado: {filepath}")

    def _import_csv(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")]
        )
        if filepath:
            try:
                self.current_gat = GATFile.import_from_csv(filepath)
                self.width_var.set(str(self.current_gat.width))
                self.height_var.set(str(self.current_gat.height))
                self._render_map()
                self._update_stats()
                self.status_bar.configure(text=f"CSV importado: {filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo importar el CSV:\n{e}")

# ============================================================
# FUNCIONES DE RUIDO PERLIN - VERSIÓN PROBADA
# ============================================================

def snoise2(x, y, octaves=1, persistence=0.5, lacunarity=2.0, repeatx=0, repeaty=0, base=0):
    """
    Versión simplificada de ruido usando random con semilla.
    """
    import random
    
    def fade(t):
        return t * t * t * (t * (t * 6 - 15) + 10)
    
    def lerp(a, b, t):
        return a + t * (b - a)
    
    def hash_2d(px, py, seed):
        # Usar random con semilla determinista
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


def test_noise():
    """Prueba para verificar valores del ruido"""
    print("=== GENERANDO VALORES DE RUIDO ===")
    valores = []
    
    # Probar con los mismos parámetros que usa el generador
    for y in range(5):
        for x in range(5):
            val = snoise2(x/80.0, y/80.0, octaves=4, persistence=0.4, lacunarity=2.0, 
                         repeatx=100, repeaty=100, base=42)
            valores.append(val)
            print(f"({x},{y}): {val:.6f}")
    
    print(f"\nMin: {min(valores):.6f}")
    print(f"Max: {max(valores):.6f}")
    print(f"Promedio: {sum(valores)/len(valores):.6f}")
    print("================================")

def test_height_distribution():
    """Muestra la distribución de alturas después de la normalización"""
    print("=== DISTRIBUCIÓN DE ALTURAS NORMALIZADAS ===")
    generator = GATGenerator(50, 50, seed=42)
    heightmap = generator._generate_heightmap(scale=80.0, octaves=4, persistence=0.4, lacunarity=2.0)
    
    # Aplanar el array
    flat = heightmap.flatten()
    
    print(f"Min: {flat.min():.4f}")
    print(f"Max: {flat.max():.4f}")
    print(f"Promedio: {flat.mean():.4f}")
    print(f"Mediana: {np.median(flat):.4f}")
    
    # Percentiles
    for p in [10, 25, 50, 75, 90]:
        print(f"Percentil {p}: {np.percentile(flat, p):.4f}")
    
    print("================================")

def main():
    test_noise()  # Prueba de valores de ruido
    test_height_distribution()  # Prueba de distribución normalizada
    root = tk.Tk()
    app = GATGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()