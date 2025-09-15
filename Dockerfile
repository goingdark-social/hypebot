FROM python:3-alpine

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY ./hype /app/hype

RUN pip install -r requirements.txt

# Create a non-root user
RUN addgroup -g 1000 hype && \
    adduser -D -u 1000 -G hype hype

# Create necessary directories and set ownership
RUN mkdir -p /app/config/ /app/secrets/ /app/logs/ && \
    chown -R hype:hype /app

VOLUME /app/config

COPY ./config/* /app/config/

# Ensure config files are owned by hype user
RUN chown -R hype:hype /app/config/

# Switch to non-root user
USER hype

ENTRYPOINT ["python", "-m", "hype"]
