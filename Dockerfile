# Frontend Dockerfile
FROM node:22-alpine as build

WORKDIR /app

# Copy package config
COPY package*.json ./
RUN npm ci

# Copy source code and build
COPY . .
RUN npm run build

# Serve Stage
FROM node:22-alpine
WORKDIR /app

RUN npm install -g serve
COPY --from=build /app/dist ./dist

EXPOSE 5173

# Serve on 5173 to match Vite's default dev port for backward compatibility
CMD ["serve", "-s", "dist", "-l", "5173"]
