# Admin Portal container image (Node/Express)
# Build context: admin-portal/

FROM node:20-slim

WORKDIR /app

# Install only production dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Copy the app source
COPY . .

ENV NODE_ENV=production
# App Service for Containers will set PORT via app settings; default is fine for local.
ENV PORT=3000

EXPOSE 3000

# Run node directly so platform SIGTERM (restart/recycle) does not surface as npm "command failed".
CMD ["node", "server.js"]
