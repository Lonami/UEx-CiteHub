# Image bases: https://hub.docker.com/search?q=&type=image&image_filter=official

# Stage 0: build Svelte frontend
FROM node:14
    WORKDIR /src/client
        COPY client/package.json ./
        COPY client/rollup.config.js ./

        # for some reason this copies the contents and not the directory itself...
        COPY client/src ./src

        RUN npm install
        RUN npm run build

# Stage 1: run Python server
FROM python:3.8
    WORKDIR /src/client/public
        COPY --from=0 /src/client/public/build/ ./build
        COPY client/public/index.html ./

        COPY client/public/global.css ./
        COPY client/public/favicon.svg ./
        COPY client/public/img/ ./

    WORKDIR /src/server
        COPY server/ ./

    WORKDIR /src
        COPY requirements.txt ./
        RUN pip install -r requirements.txt

        COPY server-config.ini ./
        EXPOSE 8080
        ENTRYPOINT python
        CMD -m server
