# Deployment checklist

GitHub hosts the repository. A Streamlit hosting service runs the application.
GitHub Pages cannot execute this Python application.

1. Review code, license, dependency pins and the resource manifest.
2. Provide authorized runtime data, preserving hashes and relative paths.
3. Choose a Python version available on the host and resolve compatible package
   versions. Test that environment; do not change versions merely to silence an
   error. Install CPU-only PyTorch if appropriate for the chosen host.
4. Download the E5 model and build the matching index in the target environment.
   The current app does not automate that first-run setup. Add a bootstrap or
   deployment build step before expecting a clean host to serve the search.
5. Configure theme colors in `.streamlit/config.toml`: hosting the entrypoint
   directly does not execute the local launcher's theme command-line flags.
6. On Streamlit Community Cloud, select the repository, branch `main` and entry
   file `app_firefly_v3.py`. Use its secrets settings if credentials are needed;
   do not commit secrets. The local `127.0.0.1` launcher is not the cloud entrypoint.
7. Check logs, startup time, model memory and search behavior on the actual host.
8. In an anonymous browser session, test English/Portuguese, all navigation,
   filters, plots, comparisons, calculator, citations and downloads. Run one
   English and one Portuguese search and inspect source support.
9. Add the verified live URL, screenshot, short demonstration and setup status
   to README. Submit both the repository URL and live application URL.

Do not mark the hosted MVP ready based only on local UI tests. A public repository
alone does not make the dashboard interactive for evaluators.

Official guides:
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app
- https://docs.github.com/en/get-started/start-your-journey/uploading-a-project-to-github
