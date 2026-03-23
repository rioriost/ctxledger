ARG POSTGRES_BASE_IMAGE=postgres:17
FROM ${POSTGRES_BASE_IMAGE}

ARG APACHE_AGE_REF=PG17/v1.7.0-rc0
ARG PGVECTOR_REF=v0.8.2
ARG POSTGRES_MAJOR=17

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bison \
        build-essential \
        ca-certificates \
        clang \
        flex \
        git \
        make \
        "postgresql-server-dev-${POSTGRES_MAJOR}" \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp

RUN git clone --branch "${APACHE_AGE_REF}" --depth 1 https://github.com/apache/age.git apache-age \
    && $(pg_config --bindir)/pg_config --version \
    && make -C apache-age \
    && make -C apache-age install

RUN git clone --branch "${PGVECTOR_REF}" --depth 1 https://github.com/pgvector/pgvector.git pgvector \
    && make -C pgvector clean \
    && make -C pgvector OPTFLAGS="" \
    && make -C pgvector install

WORKDIR /

RUN rm -rf /tmp/apache-age /tmp/pgvector

LABEL org.opencontainers.image.title="ctxledger-postgres-age" \
      org.opencontainers.image.description="Minimal PostgreSQL scaffold with Apache AGE and pgvector source-built for ctxledger local/dev AGE prototype work"

CMD ["postgres"]
