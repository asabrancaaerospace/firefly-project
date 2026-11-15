"""Cloud entrypoint. The approved local entrypoint remains unchanged."""
from pathlib import Path
import streamlit as st
from firefly_cloud_setup import prepare

BASE = Path(__file__).resolve().parent
st.set_page_config(page_title='Firefly | Firefly Project', layout='wide')


@st.cache_resource(show_spinner=False)
def initialize():
    prepare(BASE, lambda: st.secrets)
    return True


try:
    with st.spinner('Preparing verified research data and search. The first start may take several minutes.'):
        initialize()
except Exception as exc:
    st.error('Firefly could not complete startup. Please ask the project team to check the deployment.')
    # Never print secrets or authenticated request headers.
    st.caption('Startup error type: ' + type(exc).__name__)
    st.stop()

from src.ui.firefly_v3.dashboard import executar
executar(BASE)
