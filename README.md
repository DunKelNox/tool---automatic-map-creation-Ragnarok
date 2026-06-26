# 🗺️ RO Map Generator Suite

Suite de herramientas para generar mapas de Ragnarok Online (rAthena) desde cero de forma automatica.

## 📋 Descripción

Este paquete incluye tres generadores visuales que permiten crear mapas completos para Ragnarok Online:

| Herramienta | Archivo | Descripción |
|-------------|---------|-------------|
| **GAT Generator** | `gat_generator_visual.py` | Genera el terreno (caminable, bloqueado, agua, etc.) |
| **GND Generator** | `gnd_generator_visual.py` | Convierte GAT a GND con texturas 3D |
| **RSW Generator** | `rsw_generator_visual.py` | Añade objetos 3D, luces, sonidos y efectos |

## ✨ Características

- 🎨 **Interfaz gráfica** completa (Tkinter)
- 🌍 **8 biomas** diferentes: pradera, selva, cerros, desierto, isla, páramo, volcán, pantano
- 🎲 **Generación procedural** con ruido Perlin
- ✏️ **Editor de pinceles** para modificar celdas manualmente
- 💾 **Exportación** a GAT, GND, RSW y CSV
- 📊 **Estadísticas** en tiempo real del mapa
- 🖼️ **Vista previa** visual del terreno

### Requisitos

```bash
pip install numpy Pillow

#### Como Usar

python gat_generator_visual.py
python gnd_generator_visual.py
python rsw_generator_visual.py
