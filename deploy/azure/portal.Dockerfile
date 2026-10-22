FROM nginx:alpine

COPY shared/frontend/ /usr/share/nginx/html/

RUN rm -f /etc/nginx/conf.d/default.conf \
    /usr/share/nginx/html/nginx.conf \
    /usr/share/nginx/html/Dockerfile

COPY deploy/azure/portal.conf.template \
    /etc/nginx/templates/default.conf.template

ENV NGINX_ENVSUBST_FILTER=".*_HOST$"

EXPOSE 80