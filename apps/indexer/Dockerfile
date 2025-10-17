# Dockerfile for the blockchain indexer service.
#
# This image installs dependencies, compiles the TypeScript sources to
# JavaScript and starts the indexer. The RPC URLs for each chain are
# provided at runtime via environment variables.

FROM node:18 AS build
WORKDIR /app

# Install dependencies early to leverage Docker cache when code changes are made.
COPY package.json package*.json* ./
RUN npm install

# Copy the full source tree and build the TypeScript code.
COPY . .
RUN npm run build

FROM node:18 AS runtime
WORKDIR /app

# Copy only the necessary files from the build stage. The dist directory
# contains compiled JavaScript and the node_modules directory contains
# runtime dependencies.
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY --from=build /app/abis ./abis
COPY --from=build /app/config.json ./config.json

# The indexer script is started via npm run start, which invokes
# node dist/index.js as defined in package.json.
CMD ["npm", "run", "start"]