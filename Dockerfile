FROM runpod/worker-comfyui:5.7.1-base

WORKDIR /workspace

RUN cp /handler.py /handler_base.py

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential git python3-dev ffmpeg \
  && rm -rf /var/lib/apt/lists/*

RUN cd /comfyui && git fetch origin && git checkout c011fb520c79b9dfbe7f885d613771774f746eef
RUN pip install --no-cache-dir --break-system-packages comfy-kitchen==0.2.8 comfy-aimdo==0.3.0

COPY requirements.txt /workspace/requirements.txt
RUN /opt/venv/bin/python -m pip install --no-cache-dir -r /workspace/requirements.txt \
  && /opt/venv/bin/python -c "import sageattention; import triton"

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git /comfyui/custom_nodes/ComfyUI-VideoHelperSuite \
  && git -C /comfyui/custom_nodes/ComfyUI-VideoHelperSuite checkout 2984ec4c4b93292421888f38db74a5e8802a8ff8 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt; fi

RUN git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git /comfyui/custom_nodes/ComfyUI-LTXVideo \
  && git -C /comfyui/custom_nodes/ComfyUI-LTXVideo checkout 2acf7af8991f33b5cc06ec26753cb6e88e057d04 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt; fi

RUN git clone https://github.com/kijai/ComfyUI-KJNodes.git /comfyui/custom_nodes/ComfyUI-KJNodes \
  && git -C /comfyui/custom_nodes/ComfyUI-KJNodes checkout fca78c93f034c6e36080d64da83afe00bd5dbba6 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-KJNodes/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-KJNodes/requirements.txt; fi

RUN git clone https://github.com/city96/ComfyUI-GGUF.git /comfyui/custom_nodes/ComfyUI-GGUF \
  && git -C /comfyui/custom_nodes/ComfyUI-GGUF checkout 6ea2651e7df66d7585f6ffee804b20e92fb38b8a \
  && if [ -f /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt; fi

RUN git clone https://github.com/kijai/ComfyUI-MelBandRoFormer.git /comfyui/custom_nodes/ComfyUI-MelBandRoFormer \
  && git -C /comfyui/custom_nodes/ComfyUI-MelBandRoFormer checkout 92c86854e6654f4aacc97484471af95c98ea16d4 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-MelBandRoFormer/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-MelBandRoFormer/requirements.txt; fi

RUN git clone https://github.com/1038lab/ComfyUI-RMBG.git /comfyui/custom_nodes/ComfyUI-RMBG \
  && git -C /comfyui/custom_nodes/ComfyUI-RMBG checkout d7402513f23f58db7d56754b02a4f51a148b4941 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-RMBG/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-RMBG/requirements.txt; fi

RUN git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git /comfyui/custom_nodes/ComfyUI_Comfyroll_CustomNodes \
  && git -C /comfyui/custom_nodes/ComfyUI_Comfyroll_CustomNodes checkout d78b780ae43fcf8c6b7c6505e6ffb4584281ceca

RUN git clone https://github.com/chflame163/ComfyUI_LayerStyle.git /comfyui/custom_nodes/ComfyUI_LayerStyle \
  && git -C /comfyui/custom_nodes/ComfyUI_LayerStyle checkout d94bef1ee5ed3656f5ff1bb2830a4ffd94f40935 \
  && if [ -f /comfyui/custom_nodes/ComfyUI_LayerStyle/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI_LayerStyle/requirements.txt; fi

RUN git clone https://github.com/cubiq/ComfyUI_essentials.git /comfyui/custom_nodes/ComfyUI_essentials \
  && git -C /comfyui/custom_nodes/ComfyUI_essentials checkout 9d9f4bedfc9f0321c19faf71855e228c93bd0dc9 \
  && if [ -f /comfyui/custom_nodes/ComfyUI_essentials/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI_essentials/requirements.txt; fi

RUN git clone https://github.com/yolain/ComfyUI-Easy-Use.git /comfyui/custom_nodes/ComfyUI-Easy-Use \
  && git -C /comfyui/custom_nodes/ComfyUI-Easy-Use checkout 130c1b5796d9876a5f853fa0bea88e808cfda4ad \
  && if [ -f /comfyui/custom_nodes/ComfyUI-Easy-Use/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-Easy-Use/requirements.txt; fi

RUN git clone https://github.com/alisson-anjos/ComfyUI-BFSNodes.git /comfyui/custom_nodes/ComfyUI-BFSNodes \
  && git -C /comfyui/custom_nodes/ComfyUI-BFSNodes checkout f25c9dd1ec803104c1abb73fb368545f38e73cc3 \
  && if [ -f /comfyui/custom_nodes/ComfyUI-BFSNodes/requirements.txt ]; then pip install --no-cache-dir --break-system-packages -r /comfyui/custom_nodes/ComfyUI-BFSNodes/requirements.txt; fi

COPY vendor/ComfyUI-VideoOutputBridge /comfyui/custom_nodes/ComfyUI-VideoOutputBridge

ENV COMFY_ROOT=/comfyui
ENV NETWORK_VOLUME_ROOT=/runpod-volume
ENV NETWORK_VOLUME_CACHE_MODE=read_only
ENV PYTHONPATH=/workspace

COPY asset-manifest.json /workspace/asset-manifest.json
COPY workflows /workspace/workflows
COPY workflow_builder.py /workspace/workflow_builder.py
COPY bootstrap.py /workspace/bootstrap.py
COPY handler.py /handler.py

CMD ["/start.sh"]
