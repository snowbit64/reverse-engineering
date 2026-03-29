#!/usr/bin/env python3
"""
Decodificador de arquivos .p2d (formato ETC1 com header proprietario)

Formato do header (20 bytes):
  [0-3]   uint32 LE: header_size (sempre 12, mas o header real tem 20 bytes)
  [4-7]   uint32 LE: width
  [8-11]  uint32 LE: height
  [12-15] uint32 LE: format (9 = ETC1)
  [16-19] uint32 LE: flags (0)

Dados: ETC1 compressed texture com mip maps, offset 20
"""

import struct
import sys
import os
from PIL import Image

# ETC1 modifier table
ETC1_MOD_TABLE = [
    (2, 8), (5, 17), (9, 29), (13, 42),
    (18, 60), (24, 80), (33, 106), (47, 183)
]

def clamp(val, lo=0, hi=255):
    return max(lo, min(hi, val))

def decode_etc1_block(block):
    """Decode a single ETC1 block (8 bytes) to 4x4 RGB pixels"""
    b0, b1, b2, b3 = block[0], block[1], block[2], block[3]
    
    diff = (b3 >> 1) & 1
    flip = b3 & 1
    
    table_idx0 = (b3 >> 5) & 7
    table_idx1 = (b3 >> 2) & 7
    
    if diff:
        r0_5 = (b0 >> 3) & 0x1F
        g0_5 = (b1 >> 3) & 0x1F
        b0_5 = (b2 >> 3) & 0x1F
        dr = ((b0 & 7) ^ 4) - 4
        dg = ((b1 & 7) ^ 4) - 4
        db = ((b2 & 7) ^ 4) - 4
        r1_5 = r0_5 + dr
        g1_5 = g0_5 + dg
        b1_5 = b0_5 + db
        r0 = (r0_5 << 3) | (r0_5 >> 2)
        g0 = (g0_5 << 3) | (g0_5 >> 2)
        b0_val = (b0_5 << 3) | (b0_5 >> 2)
        r1 = (r1_5 << 3) | (r1_5 >> 2)
        g1 = (g1_5 << 3) | (g1_5 >> 2)
        b1_val = (b1_5 << 3) | (b1_5 >> 2)
    else:
        r0_4 = (b0 >> 4) & 0xF
        r1_4 = b0 & 0xF
        g0_4 = (b1 >> 4) & 0xF
        g1_4 = b1 & 0xF
        b0_4 = (b2 >> 4) & 0xF
        b1_4 = b2 & 0xF
        r0 = (r0_4 << 4) | r0_4
        g0 = (g0_4 << 4) | g0_4
        b0_val = (b0_4 << 4) | b0_4
        r1 = (r1_4 << 4) | r1_4
        g1 = (g1_4 << 4) | g1_4
        b1_val = (b1_4 << 4) | b1_4
    
    base_colors = [(r0, g0, b0_val), (r1, g1, b1_val)]
    
    # Pixel indices (big-endian)
    lsb = struct.unpack_from('>H', block, 4)[0]
    msb = struct.unpack_from('>H', block, 6)[0]
    
    pixels = [[None]*4 for _ in range(4)]
    for y in range(4):
        for x in range(4):
            bit_idx = x * 4 + y  # ETC1 column-major
            pixel_idx = ((msb >> bit_idx) & 1) << 1 | ((lsb >> bit_idx) & 1)
            
            if flip:
                sub = 0 if y < 2 else 1
            else:
                sub = 0 if x < 2 else 1
            
            base = base_colors[sub]
            mod = ETC1_MOD_TABLE[table_idx0 if sub == 0 else table_idx1]
            
            if pixel_idx == 0:
                modifier = mod[0]
            elif pixel_idx == 1:
                modifier = -mod[0]
            elif pixel_idx == 2:
                modifier = mod[1]
            else:
                modifier = -mod[1]
            
            pixels[y][x] = (
                clamp(base[0] + modifier),
                clamp(base[1] + modifier),
                clamp(base[2] + modifier)
            )
    
    return pixels

def decode_p2d(filepath):
    """Decode a .p2d file to a PIL Image"""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    # Parse header
    header_size = struct.unpack_from('<I', data, 0)[0]
    width = struct.unpack_from('<I', data, 4)[0]
    height = struct.unpack_from('<I', data, 8)[0]
    fmt = struct.unpack_from('<I', data, 12)[0]
    flags = struct.unpack_from('<I', data, 16)[0]
    
    print(f"  Header: size={header_size}, {width}x{height}, format={fmt}, flags={flags}")
    
    if fmt != 9:
        print(f"  AVISO: formato {fmt} desconhecido (esperado 9=ETC1)")
    
    # Data starts at offset 20
    payload = data[20:]
    
    blocks_x = width // 4
    blocks_y = height // 4
    
    img = Image.new('RGB', (width, height))
    pixels = img.load()
    
    for by in range(blocks_y):
        for bx in range(blocks_x):
            block_idx = by * blocks_x + bx
            offset = block_idx * 8
            block_data = payload[offset:offset + 8]
            if len(block_data) < 8:
                break
            
            block_pixels = decode_etc1_block(block_data)
            for dy in range(4):
                for dx in range(4):
                    px = bx * 4 + dx
                    py = by * 4 + dy
                    if px < width and py < height:
                        pixels[px, py] = block_pixels[dy][dx]
    
    return img

def main():
    input_dir = '/home/ubuntu/upload'
    output_dir = '/home/ubuntu/decoded'
    os.makedirs(output_dir, exist_ok=True)
    
    p2d_files = sorted([f for f in os.listdir(input_dir) if f.endswith('.p2d')])
    
    print(f"Encontrados {len(p2d_files)} arquivos .p2d")
    print()
    
    for filename in p2d_files:
        filepath = os.path.join(input_dir, filename)
        output_name = filename.replace('.p2d', '.png')
        output_path = os.path.join(output_dir, output_name)
        
        print(f"Decodificando {filename}...")
        try:
            img = decode_p2d(filepath)
            img.save(output_path)
            print(f"  -> {output_name} ({img.size[0]}x{img.size[1]})")
        except Exception as e:
            print(f"  ERRO: {e}")
        print()
    
    print("Concluido!")

if __name__ == '__main__':
    main()
