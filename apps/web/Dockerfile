FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p /tools/3d-assets && cp ./tools/3d-assets/meshopt-fallback-compat.mjs /tools/3d-assets/meshopt-fallback-compat.mjs
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ARG NEXT_PUBLIC_SUPABASE_URL=
ARG NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=$NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public ./public
RUN test -s ./public/icon.svg \
    && test -s ./public/asset-manifest.json \
    && test -s ./public/assets/slides/slide_welcome_3d_1793022854882.jpg \
    && test -s ./public/assets/slides/slide_cinema_3d_1793023017033.jpg \
    && test -s ./public/assets/slides/slide_livestage_3d_1793023043430.jpg \
    && test -s ./public/assets/menggu3d/district_spatial.jpg \
    && test -s ./public/assets/menggu3d/landmark_citadel.jpg
USER nextjs
EXPOSE 3000
CMD ["node", "server.js"]
