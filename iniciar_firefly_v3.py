"""Inicia v3 com cores locais da marca; não sobrescreve .streamlit/config.toml."""
from pathlib import Path
import subprocess
import sys
from src.ui.firefly_v3.brand import palette,logo_path

if __name__=='__main__':
    base=Path(__file__).resolve().parent
    cores=palette(base)
    print('Logotipo:',logo_path(base) or 'não encontrado; usando nome em texto',flush=True)
    print('Cores:',cores,flush=True)
    command=[sys.executable,'-m','streamlit','run',str(base/'app_firefly_v3.py'),
             '--server.address','127.0.0.1','--theme.base','light',
             '--theme.primaryColor',cores['blue'],'--theme.backgroundColor','#FFFFFF',
             '--theme.secondaryBackgroundColor','#F3F5F8','--theme.textColor',cores['text']]
    try:subprocess.run(command,cwd=base,check=True)
    except KeyboardInterrupt:pass
