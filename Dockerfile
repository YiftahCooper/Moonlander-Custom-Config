FROM debian:bookworm-20260713-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    python3 \
    python3-pip \
    sudo \
    build-essential \
    gcc-arm-none-eabi \
    libnewlib-arm-none-eabi \
    avrdude \
    dfu-util \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install \
    qmk==1.2.0 \
    appdirs==1.4.4 \
    --break-system-packages

WORKDIR /root
