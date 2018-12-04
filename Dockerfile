FROM alpine

LABEL description "uWSGI + Flask based on Alpine Linux"

# Copy python requirements file
COPY tippicserver/requirements.txt /tmp/requirements.txt

RUN apk add --no-cache \
    build-base \
    gcc \
    git \ 
    python3 \
    python3-dev \
    bash \
    postgresql-dev \
    uwsgi \
    uwsgi-python3 && \
    pip3 install --upgrade pip setuptools && \
    pip3 install -r /tmp/requirements.txt && \
    pip3 install git+https://github.com/kinecosystem/kin-core-python.git && \
    rm -r /root/.cache


# Add the tippicserver app
COPY setup.py /app/
COPY tippicserver /app/tippicserver/
WORKDIR /app/
RUN pip3 install . --upgrade

RUN apk add --update uwsgi-python

RUN mkdir /opt/tippic-server -p

CMD ["uwsgi --plugin /usr/lib/uwsgi/python3_plugin.so --socket 0.0.0.0:8000 --protocol=http --wsgi-file /app/tippicserver/wsgi.py --enable-threads"]