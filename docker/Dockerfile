FROM ghcr.io/linuxserver/baseimage-kasmvnc:debianbookworm

# --build-arg UPDATE_PACKAGES=true  → runs apt-get upgrade during build
ARG UPDATE_PACKAGES=false

LABEL maintainer="rohanjq"

ENV TITLE=Metatrader5
ENV WINEPREFIX="/data/wine"
ENV WINEDEBUG=-all

# System packages + Wine (single layer)
RUN apt-get update \
    && if [ "$UPDATE_PACKAGES" = "true" ]; then apt-get upgrade -y; fi \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv \
        python3-xdg \
        wget curl gnupg2 software-properties-common ca-certificates \
    && mkdir -pm755 /etc/apt/keyrings \
    && wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key \
    && wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/debian/dists/bookworm/winehq-bookworm.sources \
    && dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install --install-recommends -y winehq-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Copy startup scripts + bundled MQL5 source files
COPY docker/Metatrader /Metatrader
COPY MQL5 /Metatrader/MQL5
RUN chmod +x /Metatrader/start.sh

# KasmVNC defaults (autostart, right-click menu)
COPY docker/root /

EXPOSE 3000 8001
VOLUME /config /data
