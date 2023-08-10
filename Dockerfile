FROM node:18

# For TimeZone Setting. NOT for alpine OS.
ENV TZ=Asia/Seoul
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime

WORKDIR /usr/app

# Copy all except .dockerignore
COPY . .
RUN npm install --production

CMD ["npm", "run", "start:prod"]