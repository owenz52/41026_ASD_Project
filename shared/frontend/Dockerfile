FROM nginx:alpine

COPY nginx.conf.template /etc/nginx/templates/default.conf.template

COPY . /usr/share/nginx/html

# Remove files that shouldn't be publicly served
RUN rm -f /usr/share/nginx/html/nginx.conf.template \
          /usr/share/nginx/html/Dockerfile

EXPOSE 80