# Stage 1: Build the Go binary
FROM golang:1.21 as builder

WORKDIR /app

COPY go.mod go.sum main.go .

RUN go get -d -v ./...
RUN go build -o builder main.go

# Stage 2: Create the final image with a minimal Debian-based image
FROM debian:bookworm-slim

# Install build-essential and ca-certs for SSL support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /app/builder /app/builder

WORKDIR /app

ENTRYPOINT ["/app/builder"]

LABEL org.opencontainers.image.source=https://github.com/stenius/cforge
LABEL org.opencontainers.image.description="CForge Builder"
LABEL org.opencontainers.image.licenses=BSD

