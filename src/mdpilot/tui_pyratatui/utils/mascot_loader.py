"""
Mascot pixel loader for MDPilot TUI.

Loads the 32x32 octopus pilot mascot from assets.
"""
import os
from typing import List, Tuple, Optional
from pathlib import Path


# Mascot pixel data (32x32) - extracted from draw_mascot_custom.py
# Color palette
C00 = (34, 157, 255)   # #229DFF - Blue
C01 = (255, 254, 254)  # #FFFEFE - White
C02 = (62, 179, 255)   # #3EB3FF - Light blue
C03 = (59, 59, 59)     # #3B3B3B - Dark gray
C04 = (168, 168, 171)  # #A8A8AB - Gray
C05 = (82, 82, 82)     # #525252 - Medium gray
C06 = (48, 48, 48)     # #303030 - Very dark gray
C07 = (56, 56, 56)     # #383838 - Dark gray
C08 = (0, 0, 0)        # #000000 - Black
C09 = (23, 106, 173)   # #176AAD - Dark blue
C10 = (242, 105, 146)  # #F26992 - Pink
C11 = (191, 190, 190)  # #BFBEBE - Light gray
C12 = (126, 210, 255)  # #7ED2FF - Sky blue

TRANSPARENT = (0, 0, 0, 0)


def load_mascot_pixels() -> List[List[Optional[Tuple[int, int, int]]]]:
    """
    Load 32x32 mascot pixel data.
    
    Returns:
        32x32 array of RGB tuples, None for transparent pixels
    """
    # Initialize 32x32 transparent canvas
    pixels = [[None for _ in range(32)] for _ in range(32)]
    
    # Row 7
    for x in range(9, 23):
        pixels[7][x] = C03
    
    # Row 8
    for x in range(7, 9):
        pixels[8][x] = C07
    for x in range(9, 11):
        pixels[8][x] = C03
    pixels[8][11] = C11
    for x in range(12, 14):
        pixels[8][x] = C04
    for x in range(14, 18):
        pixels[8][x] = C05
    pixels[8][18] = C11
    for x in range(19, 21):
        pixels[8][x] = C04
    for x in range(21, 23):
        pixels[8][x] = C03
    for x in range(23, 25):
        pixels[8][x] = C07
    
    # Row 9
    pixels[9][7] = C06
    pixels[9][8] = C07
    for x in range(9, 11):
        pixels[9][x] = C06
    pixels[9][11] = C04
    pixels[9][12] = C12
    for x in range(13, 19):
        pixels[9][x] = C04
    pixels[9][19] = C12
    pixels[9][20] = C04
    for x in range(21, 23):
        pixels[9][x] = C06
    pixels[9][23] = C07
    pixels[9][24] = C06
    
    # Row 10
    pixels[10][7] = C06
    pixels[10][8] = C07
    for x in range(9, 11):
        pixels[10][x] = C06
    for x in range(11, 14):
        pixels[10][x] = C04
    for x in range(14, 18):
        pixels[10][x] = C06
    for x in range(18, 21):
        pixels[10][x] = C04
    for x in range(21, 23):
        pixels[10][x] = C06
    pixels[10][23] = C07
    pixels[10][24] = C06
    
    # Row 11
    pixels[11][7] = C06
    pixels[11][8] = C07
    for x in range(9, 23):
        pixels[11][x] = C05
    pixels[11][23] = C07
    pixels[11][24] = C06
    
    # Row 12
    pixels[12][7] = C07
    pixels[12][8] = C00
    for x in range(9, 14):
        pixels[12][x] = C01
    for x in range(14, 18):
        pixels[12][x] = C00
    for x in range(18, 23):
        pixels[12][x] = C01
    pixels[12][23] = C00
    pixels[12][24] = C07
    
    # Row 13
    pixels[13][8] = C00
    pixels[13][9] = C01
    for x in range(10, 13):
        pixels[13][x] = C08
    pixels[13][13] = C01
    for x in range(14, 18):
        pixels[13][x] = C00
    for x in range(18, 20):
        pixels[13][x] = C01
    for x in range(20, 22):
        pixels[13][x] = C08
    pixels[13][22] = C01
    pixels[13][23] = C00
    
    # Row 14
    pixels[14][8] = C00
    pixels[14][9] = C01
    for x in range(10, 13):
        pixels[14][x] = C08
    pixels[14][13] = C01
    for x in range(14, 18):
        pixels[14][x] = C00
    pixels[14][18] = C01
    for x in range(19, 22):
        pixels[14][x] = C08
    pixels[14][22] = C01
    pixels[14][23] = C00
    
    # Row 15
    for x in range(8, 10):
        pixels[15][x] = C10
    for x in range(10, 14):
        pixels[15][x] = C01
    for x in range(14, 18):
        pixels[15][x] = C00
    for x in range(18, 22):
        pixels[15][x] = C01
    for x in range(22, 24):
        pixels[15][x] = C10
    
    # Row 16
    for x in range(9, 20):
        pixels[16][x] = C00
    for x in range(20, 23):
        pixels[16][x] = C09
    
    # Row 17
    for x in range(9, 20):
        pixels[17][x] = C00
    for x in range(20, 23):
        pixels[17][x] = C09
    
    # Row 18
    for x in range(9, 13):
        pixels[18][x] = C02
    pixels[18][14] = C02
    pixels[18][17] = C02
    pixels[18][19] = C02
    pixels[18][20] = C00
    for x in range(21, 23):
        pixels[18][x] = C02
    
    # Row 19
    pixels[19][9] = C02
    pixels[19][11] = C02
    pixels[19][14] = C02
    pixels[19][17] = C02
    pixels[19][20] = C02
    pixels[19][22] = C02
    
    # Row 20
    pixels[20][8] = C09
    pixels[20][11] = C09
    pixels[20][13] = C02
    pixels[20][18] = C02
    pixels[20][20] = C09
    pixels[20][23] = C09
    
    # Row 21
    pixels[21][7] = C02
    pixels[21][10] = C02
    pixels[21][13] = C02
    pixels[21][18] = C02
    pixels[21][21] = C02
    pixels[21][24] = C02
    
    # Row 22
    pixels[22][6] = C02
    pixels[22][25] = C02
    
    return pixels


def get_mascot_dimensions() -> Tuple[int, int]:
    """
    Get mascot dimensions.
    
    Returns:
        (width, height) tuple
    """
    return (32, 32)
