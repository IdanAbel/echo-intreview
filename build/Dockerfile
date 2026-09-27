# Backport patch - CVE-2024-7347

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpcre2-dev \
    zlib1g-dev \
    libssl-dev \
    patch \
    fakeroot \
    dpkg-dev \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/src

ARG NGINX_VERSION=1.25.5
RUN curl -fSL "https://nginx.org/download/nginx-${NGINX_VERSION}.tar.gz" -o nginx.tar.gz \
    && tar -zxvf nginx.tar.gz \
    && rm nginx.tar.gz

WORKDIR /usr/src/nginx-${NGINX_VERSION}

COPY patches/ /usr/src/patches/
RUN for p in /usr/src/patches/*.patch; do \
    if [ -f "$p" ]; then \
    echo "===> Applying patch: $p <===" && patch -p1 < "$p"; \
    fi; \
    done

RUN ./configure \
    --prefix=/etc/nginx \
    --sbin-path=/usr/sbin/nginx \
    --modules-path=/usr/lib/nginx/modules \
    --conf-path=/etc/nginx/nginx.conf \
    --error-log-path=/var/log/nginx/error.log \
    --http-log-path=/var/log/nginx/access.log \
    --pid-path=/var/run/nginx.pid \
    --lock-path=/var/run/nginx.lock \
    --http-client-body-temp-path=/var/cache/nginx/client_temp \
    --http-proxy-temp-path=/var/cache/nginx/proxy_temp \
    --http-fastcgi-temp-path=/var/cache/nginx/fastcgi_temp \
    --http-uwsgi-temp-path=/var/cache/nginx/uwsgi_temp \
    --http-scgi-temp-path=/var/cache/nginx/scgi_temp \
    --user=nginx \
    --group=nginx \
    --with-compat \
    --with-file-aio \
    --with-threads \
    --with-http_addition_module \
    --with-http_auth_request_module \
    --with-http_dav_module \
    --with-http_flv_module \
    --with-http_gunzip_module \
    --with-http_gzip_static_module \
    --with-http_mp4_module \
    --with-http_random_index_module \
    --with-http_realip_module \
    --with-http_secure_link_module \
    --with-http_slice_module \
    --with-http_ssl_module \
    --with-http_stub_status_module \
    --with-http_sub_module \
    --with-http_v2_module \
    --with-http_v3_module \
    --with-stream \
    --with-stream_realip_module \
    --with-stream_ssl_module \
    --with-stream_ssl_preread_module

RUN make -j$(nproc) && make DESTDIR=/tmp/pkg install

RUN mkdir -p /tmp/pkg/DEBIAN && \
    echo "Package: nginx" > /tmp/pkg/DEBIAN/control && \
    echo "Version: 1.25.5-1~custom.patched" >> /tmp/pkg/DEBIAN/control && \
    echo "Section: httpd" >> /tmp/pkg/DEBIAN/control && \
    echo "Priority: optional" >> /tmp/pkg/DEBIAN/control && \
    echo "Architecture: $(dpkg --print-architecture)" >> /tmp/pkg/DEBIAN/control && \
    echo "Depends: libc6, libpcre2-8-0, libssl3, zlib1g" >> /tmp/pkg/DEBIAN/control && \
    echo "Maintainer: Echo Security Candidate <security@candidate.local>" >> /tmp/pkg/DEBIAN/control && \
    echo "Description: High performance web server (custom patched drop-in replacement)" >> /tmp/pkg/DEBIAN/control

RUN mkdir -p /output && \
    dpkg-deb --build /tmp/pkg /output/nginx_1.25.5-1_patched.deb