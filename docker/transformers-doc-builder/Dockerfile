FROM python:3.10
LABEL maintainer="Hugging Face"

RUN apt update
RUN git clone https://github.com/huggingface/transformers

RUN python3 -m pip install --no-cache-dir --upgrade pip && python3 -m pip install --no-cache-dir git+https://github.com/huggingface/doc-builder ./myTransformers[dev]
RUN apt-get -y update && apt-get install -y libsndfile1-dev && apt install -y tesseract-ocr

# Torch needs to be installed before deepspeed
RUN python3 -m pip install --no-cache-dir ./myTransformers[deepspeed]

RUN python3 -m pip install --no-cache-dir torchvision git+https://github.com/facebookresearch/detectron2.git pytesseract
RUN python3 -m pip install -U "itsdangerous<2.1.0"

# Test if the image could successfully build the doc. before publishing the image
RUN doc-builder build myTransformers myTransformers/docs/source/en --build_dir doc-build-dev --notebook_dir notebooks/transformers_doc --clean
RUN rm -rf doc-build-dev