FROM python:3.6.3-alpine3.6

RUN apk update && apk add --no-cache build-base libffi-dev openssl-dev gmp-dev git

# karlfloersch/pyethereum need this https://github.com/ethereum/pyethereum/pull/831
RUN pip install --no-cache-dir setuptools==37.0.0 tinyrpc==0.6

WORKDIR /ethereum
RUN git clone https://github.com/ethereum/vyper.git &&\
    cd vyper &&\
    git reset --hard a154d579062ae67cc3d79c942a30a384bcc1b24e &&\
    python setup.py develop
RUN git clone https://github.com/karlfloersch/pyethereum.git &&\
    cd pyethereum &&\
    git reset --hard 9089d8ecd914c23b233f27c4a6b65d346695f844

COPY ./casper pyethereum/casper/casper

RUN cd pyethereum && python setup.py develop