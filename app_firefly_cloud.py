"""Cloud entrypoint. The approved local entrypoint remains unchanged."""
from pathlib import Path
from urllib.parse import urlsplit
import streamlit as st
from firefly_cloud_setup import prepare

BASE = Path(__file__).resolve().parent
st.set_page_config(page_title='Firefly | Firefly Project', layout='wide')


def safe_http_diagnostic(exc):
    """Return only an allowlisted service label and an HTTP status, never a URL/token."""
    seen = set()
    current = exc
    for _ in range(8):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        response = getattr(current, 'response', None)
        code = getattr(current, 'code', None)
        if not isinstance(code, int):
            code = getattr(response, 'status_code', None)
        url = getattr(current, 'url', None) or getattr(response, 'url', '')
        if isinstance(code, int) and 100 <= code <= 599:
            host = urlsplit(str(url)).hostname or ''
            if host == 'api.github.com':
                service = 'GitHub data API'
            elif host == 'ntrs.nasa.gov':
                service = 'NASA NTRS PDF'
            elif host == 'huggingface.co' or host.endswith('.huggingface.co') or host.endswith('.hf.co'):
                service = 'Hugging Face model download'
            else:
                service = 'External download service'
            return f'{service} | HTTP {code}'
        current = getattr(current, '__cause__', None) or getattr(current, '__context__', None)
    return None


@st.cache_resource(show_spinner=False)
def initialize():
    prepare(BASE, lambda: st.secrets)
    return True


try:
    with st.spinner('Preparing verified research data and search. The first start may take several minutes.'):
        initialize()
except Exception as exc:
    st.error('Firefly could not complete startup. Please ask the project team to check the deployment.')
    diagnostic = safe_http_diagnostic(exc)
    if diagnostic:
        st.caption('Startup HTTP diagnostic: ' + diagnostic)
        print('Firefly startup: ' + diagnostic, flush=True)
    else:
        st.caption('Startup error type: ' + type(exc).__name__)
    # Never display exception bodies, request headers, full URLs or credentials.
    st.stop()

from src.ui.firefly_v3.dashboard import executar
executar(BASE)
