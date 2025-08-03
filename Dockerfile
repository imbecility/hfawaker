FROM mcr.microsoft.com/playwright/python:v1.53.0-noble
RUN mkdir -p /.cache && \
    chmod 777 /.cache && \
    pip uninstall playwright && \
    pip install --no-cache-dir --upgrade fastapi patchright prlps_fakeua uvicorn && \
    patchright install --with-deps chromium
WORKDIR /code
COPY . .
# для заглушки:
RUN git clone --depth 1 https://huggingface.co/spaces/Xenova/the-tokenizer-playground static && \
    chmod -R 777 /code > /dev/null 2>&1 && \
    chmod -R 777 / > /dev/null 2>&1 || true
CMD ["python", "/code/app.py"]