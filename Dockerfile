FROM python:3-alpine

# Build arguments for customizable UID/GID
ARG USER_UID=1000
ARG USER_GID=1000
ARG USER_NAME=hype

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY ./hype /app/hype

RUN pip install -r requirements.txt

# Create a non-root user with configurable UID/GID
RUN addgroup -g ${USER_GID} ${USER_NAME} && \
    adduser -D -u ${USER_UID} -G ${USER_NAME} ${USER_NAME}

# Create necessary directories and set ownership
RUN mkdir -p /app/config/ /app/secrets/ /app/logs/ && \
    chown -R ${USER_UID}:${USER_GID} /app

VOLUME /app/config

COPY ./config/* /app/config/

# Ensure config files are owned by the specified user
RUN chown -R ${USER_UID}:${USER_GID} /app/config/

# Switch to non-root user using numeric UID:GID for Kubernetes compatibility
USER ${USER_UID}:${USER_GID}

ENTRYPOINT ["python", "-m", "hype"]
