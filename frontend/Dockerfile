FROM node:24-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

# Expose port
EXPOSE 5173

# Run the vite dev server explicitly on 0.0.0.0
CMD ["npm", "run", "dev", "--", "--host"]
