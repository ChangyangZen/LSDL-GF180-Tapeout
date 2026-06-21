# LibreLane build environment for the wafer.space gf180mcu-project-template.
# Modeled on the gf180mcu-precheck Dockerfile: a Nix base image that builds the
# template's flake (which pulls LibreLane + the EDA toolchain) into a cached
# dev profile, bakes in the PDK, and exposes a dev-shell entrypoint so
# `docker run <image> make librelane` runs inside the nix environment — no host
# Nix required.
FROM nixos/nix:latest

LABEL org.opencontainers.image.title="lsdl-tapeout-librelane"
LABEL org.opencontainers.image.description="LibreLane Chip-flow env for the LSDL GF180MCU tapeout (wafer.space template)."

# Enable flakes + the fossi-foundation binary cache (prebuilt EDA tools).
RUN echo "experimental-features = nix-command flakes" >> /etc/nix/nix.conf && \
    echo "extra-substituters = https://cache.nixos.org https://nix-cache.fossi-foundation.org" >> /etc/nix/nix.conf && \
    echo "extra-trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY= nix-cache.fossi-foundation.org:3+K59iFwXqKsL7BNu6Guy0v+uTlwsxYQxjspXzqLYQs=" >> /etc/nix/nix.conf

WORKDIR /workspace

# Build + cache the dev environment first (best layer caching).
COPY flake.nix flake.lock ./
RUN nix develop --accept-flake-config --profile /nix/var/nix/profiles/dev-profile --command python3 --version
RUN nix develop --accept-flake-config --offline --profile /nix/var/nix/profiles/dev-profile --command python3 --version

# Bake the PDK into the image (offline-capable), via the template Makefile.
COPY Makefile ./
RUN nix develop --accept-flake-config --offline --profile /nix/var/nix/profiles/dev-profile --command make clone-pdk

# Copy the rest of the repo (src, librelane configs, ip/ macro views, etc.).
COPY . .

ENV PDK_ROOT=/workspace/gf180mcu
ENV PDK=gf180mcuD
ENV PATH=/usr/local/bin:$PATH

# Run all commands inside the nix dev environment.
COPY scripts/dev-shell /usr/local/bin/dev-shell
RUN chmod +x /usr/local/bin/dev-shell
ENTRYPOINT ["dev-shell"]
