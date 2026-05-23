FROM node:22-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY . .

EXPOSE 5180

CMD ["npm", "run", "dev"]
