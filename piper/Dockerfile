FROM python:3.12-slim
ARG PIPER_VERSION=1.8.0
ARG PIPER_UID=1000
RUN python -m pip install --no-cache-dir "piper-tts[http]==${PIPER_VERSION}"
COPY patch-http-server.py /tmp/patch-http-server.py
RUN python /tmp/patch-http-server.py && rm /tmp/patch-http-server.py
RUN useradd --create-home --uid ${PIPER_UID} piper && mkdir -p /voices && chown -R piper:piper /voices
COPY --chmod=755 entrypoint.sh /usr/local/bin/piper-entrypoint
USER piper
WORKDIR /voices
EXPOSE 5000
ENTRYPOINT ["/usr/local/bin/piper-entrypoint"]
