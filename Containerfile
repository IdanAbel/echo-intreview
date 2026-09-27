
# Dependency Bump - libssl3

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    libpcre2-8-0 \
    zlib1g \
    && apt-get --only-upgrade install -y libssl3 openssl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 101 nginx \
    && useradd --system --gid 101 --no-create-home --home /nonexistent --comment "nginx user" --shell /bin/false --uid 101 nginx

COPY build/output/nginx_1.25.5-1_patched.deb /tmp/nginx.deb
RUN dpkg -i /tmp/nginx.deb && rm /tmp/nginx.deb

RUN mkdir -p /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /etc/nginx/html /usr/share/nginx \
    && ln -sf /etc/nginx/html /usr/share/nginx/html \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx

COPY build/index.html /etc/nginx/html/index.html
COPY build/index.html /usr/share/nginx/html/index.html
RUN echo '<!DOCTYPE html><html><head><title>500 Internal Server Error</title></head><body><center><h1>An error occurred.</h1></center></body></html>' > /etc/nginx/html/50x.html

RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    location / { \
    root /etc/nginx/html; \
    index index.html index.htm; \
    } \
    error_page 500 502 503 504 /50x.html; \
    location = /50x.html { \
    root /etc/nginx/html; \
    } \
    }' > /etc/nginx/conf.d/default.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh && mkdir -p /docker-entrypoint.d

EXPOSE 80
STOPSIGNAL SIGQUIT

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]