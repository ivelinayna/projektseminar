#Ein Image für alles: Notebooks (JupyterLab), Pipeline-Befehle, Dashboard und Doku.
#Daten, Ergebnisse und Modellpakete kommen nicht ins Image, sondern werden beim Start
#als Ordner eingehängt (siehe docker-compose.yml).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    MPLBACKEND=Agg

#libgomp1 braucht XGBoost, git nur für den Code-Stand in den Modellpaketen
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

#PyTorch ohne Grafikkarte, sonst wird das Image mehrere GB größer
RUN pip install --index-url https://download.pytorch.org/whl/cpu "torch>=2.4"

#Erst nur die Paketlisten kopieren, dann bleibt diese Schicht bei Codeänderungen im Cache
COPY requirements.txt /tmp/requirements.txt
COPY docs/requirements.txt /tmp/requirements-docs.txt
RUN pip install -r /tmp/requirements.txt -r /tmp/requirements-docs.txt "jupyterlab>=4" "pytest>=8"

COPY . .

EXPOSE 8888 8000 8001 8501

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", \
     "--ServerApp.root_dir=/app", "--IdentityProvider.token="]
