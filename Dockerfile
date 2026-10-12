# Models never enter the build context or image. Target: L40S / RTX 6000 Ada 48GB.
ARG CUDA_VERSION=12.8.1
FROM nvidia/cuda:${CUDA_VERSION}-devel-ubuntu24.04 AS engine-build
ARG SD_COMMIT=2988060a4338a5dcd94721c964a8e87003c1ac8b
ARG CUDA_ARCHITECTURES=86;89
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git cmake ninja-build build-essential \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /src
RUN git init && git remote add origin https://github.com/leejet/stable-diffusion.cpp.git \
    && git fetch --depth 1 origin ${SD_COMMIT} && git checkout --detach FETCH_HEAD \
    && git submodule update --init --recursive --depth 1
RUN cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
      -DSD_CUDA=ON -DSD_BUILD_EXAMPLES=ON -DSD_SERVER_BUILD_FRONTEND=OFF \
      -DGGML_NATIVE=OFF -DCMAKE_CUDA_ARCHITECTURES="${CUDA_ARCHITECTURES}" \
    && cmake --build build --target sd-server --parallel 2

FROM nvidia/cuda:${CUDA_VERSION}-runtime-ubuntu24.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH OMP_NUM_THREADS=4 \
    MODEL_VOLUME_ROOT=/runpod-volume ENGINE_START_TIMEOUT=300 JOB_TIMEOUT_SECONDS=900
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates python3.12 python3.12-venv libgomp1 tini \
    && rm -rf /var/lib/apt/lists/* \
    && python3.12 -m venv /opt/venv
COPY --from=engine-build /src/build/bin/sd-server /usr/local/bin/sd-server
# libcuda is injected by the NVIDIA runtime on GPU workers. The toolkit stub
# enables CPU-only --help checks; it is deliberately outside the runtime search
# path and is used only by smoke.py, never by the inference process.
COPY --from=engine-build /usr/local/cuda/lib64/stubs/libcuda.so /opt/cuda-stubs/libcuda.so.1
COPY --from=engine-build /src/LICENSE /usr/share/licenses/stable-diffusion.cpp/LICENSE
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY model-lock.json handler.py ./
COPY worker ./worker
COPY scripts/smoke.py ./scripts/smoke.py
# CPU-only import/flag checks do not initialize CUDA or load models.
RUN python scripts/smoke.py
LABEL org.opencontainers.image.source="https://github.com/Alfa-jim/darkcoal-qwen-image-21" \
      org.opencontainers.image.description="Network-volume Qwen Image 2.1 Turbo AD-Q4_K RunPod worker"
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-u", "handler.py"]
