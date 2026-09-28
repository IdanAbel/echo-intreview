
# Dependency Bump - libssl3

FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gettext-base \
    libpcre2-8-0 \
    zlib1g \
    && apt-get --only-upgrade install -y libssl3 openssl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 101 nginx \
    && useradd --system --gid 101 --no-create-home --home /nonexistent --comment "nginx user" --shell /bin/false --uid 101 nginx

COPY build/output/nginx_1.25.5-1_patched.deb /tmp/nginx.deb
RUN dpkg -i /tmp/nginx.deb && rm /tmp/nginx.deb

RUN rm -rf /etc/nginx/html /etc/nginx/*.default /etc/nginx/koi-* /etc/nginx/win-utf /etc/nginx/fastcgi.conf \
    && mkdir -p /var/cache/nginx /var/log/nginx /etc/nginx/conf.d /usr/share/nginx/html /usr/lib/nginx/modules \
    && ln -sfn /usr/lib/nginx/modules /etc/nginx/modules \
    && chown -R nginx:nginx /var/cache/nginx /var/log/nginx

COPY build/index.html /usr/share/nginx/html/index.html
RUN printf '%s\n' '<html>' '<head><title>50x Error</title></head>' '<body>' '<center><h1>50x Error</h1></center>' '<hr><center>nginx</center>' '</body>' '</html>' > /usr/share/nginx/html/50x.html

RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log

COPY runtime/nginx.conf /etc/nginx/nginx.conf
COPY runtime/default.conf /etc/nginx/conf.d/default.conf

COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY docker-entrypoint.d/ /docker-entrypoint.d/
RUN chmod +x /docker-entrypoint.sh /docker-entrypoint.d/*

EXPOSE 80
STOPSIGNAL SIGQUIT

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
