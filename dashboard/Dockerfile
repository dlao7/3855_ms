FROM nginx

LABEL maintainer="dlao7@my.bcit.ca"

COPY index.html plane.jpg /usr/share/nginx/html

COPY style.css /usr/share/nginx/html

COPY updateStatsProd.js /usr/share/nginx/html

COPY config/nginx.conf  /etc/nginx/conf.d/

EXPOSE 80