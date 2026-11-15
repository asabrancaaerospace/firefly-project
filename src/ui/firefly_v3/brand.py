"""Lê cores da marca sem modificar a imagem ou a configuração das outras versões."""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import re

DEFAULT={'blue':'#142D4E','orange':'#B94E00','text':'#142D4E','origin':'fallback'}


def logo_path(base):
    return next((Path(base)/'assets'/('firefly_logo'+ext) for ext in ('.png','.svg','.jpg','.jpeg')
                 if (Path(base)/'assets'/('firefly_logo'+ext)).is_file()),None)


def palette_from_pixels(pixels):
    blues,oranges=Counter(),Counter()
    for r,g,b,a in pixels:
        if a<200:continue
        if b>80 and b>r*1.4 and b>g*1.2:blues[(r,g,b)]+=1
        if r>100 and r>g*1.25 and g>b*1.4 and g>35:oranges[(r,g,b)]+=1
    out=dict(DEFAULT)
    for name,counts in [('blue',blues),('orange',oranges)]:
        if counts:
            rgb=counts.most_common(1)[0][0];out[name]='#'+''.join(f'{v:02X}' for v in rgb)
    if blues and oranges:out['origin']='logo'
    elif blues or oranges:out['origin']='logo_partial'
    return out


@lru_cache(maxsize=4)
def _read(path,mtime):
    if Path(path).suffix.lower()=='.svg':
        # Somente leitura de cores literais; não executa scripts nem carrega URLs.
        text=Path(path).read_text(encoding='utf-8-sig')
        colors=re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b',text)
        pixels=[]
        for color in colors:
            h=color[1:];h=''.join(c*2 for c in h) if len(h)==3 else h
            pixels.append((*[int(h[i:i+2],16) for i in (0,2,4)],255))
        return palette_from_pixels(pixels)
    from PIL import Image
    with Image.open(path) as im:
        # Amostragem em memória apenas; nunca salva ou modifica a logotipo.
        im=im.convert('RGBA');im.thumbnail((256,256))
        return palette_from_pixels(list(im.getdata()))


def palette(base):
    path=logo_path(base)
    return dict(DEFAULT) if path is None else _read(str(path),path.stat().st_mtime_ns).copy()


def contrast_text(hex_color):
    rgb=[int(hex_color[i:i+2],16)/255 for i in (1,3,5)]
    linear=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in rgb]
    luminance=sum(a*b for a,b in zip(linear,[0.2126,0.7152,0.0722]))
    return '#FFFFFF' if 1.05/(luminance+0.05)>=(luminance+0.05)/0.05 else '#000000'

COLORS=palette(Path(__file__).resolve().parents[3])
