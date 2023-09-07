FROM ubuntu:bionic-20220531

# setup installation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Installing Neurodebian and nodejs packages
COPY neurodebian.gpg /usr/local/etc/neurodebian.gpg
RUN curl -sL https://deb.nodesource.com/setup_14.x | bash - && \
    curl -sSL "http://neuro.debian.net/lists/$( lsb_release -c | cut -f2 ).us-ca.full" >> /etc/apt/sources.list.d/neurodebian.sources.list && \
    apt-key add /usr/local/etc/neurodebian.gpg && \
    (apt-key adv --refresh-keys --keyserver hkp://ha.pool.sks-keyservers.net 0xA5D32F012649A5A9 || true)

# get dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    datalad nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install and set up miniconda
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-py38_4.9.2-Linux-x86_64.sh && \
    bash Miniconda3-py38_4.9.2-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-py38_4.9.2-Linux-x86_64.sh

# Set CPATH for packages relying on compiled libs (e.g. indexed_gzip)
ENV PATH="/usr/local/miniconda/bin:$PATH" \
    CPATH="/usr/local/miniconda/include:$CPATH" \
    LANG="C.UTF-8" \
    LC_ALL="C.UTF-8" \
    PYTHONNOUSERSITE=1

# Install precomputed python packages
RUN conda install -y \
        python=3.9 \
        pip; \
    sync && \
    chmod -R a+rX /usr/local/miniconda; sync && \
    chmod +x /usr/local/miniconda/bin/*; sync && \
    conda clean -y --all; sync && \
    conda clean -tipsy; sync && \
    rm -rf ~/.conda ~/.cache/pip/*; sync


# get the validator
RUN npm install -g yarn && \
    npm install -g bids-validator

COPY . /src/CuBIDS
RUN python --version && \
    pip3 --version && \
    pip3 install --no-cache-dir "/src/CuBIDS"

ENTRYPOINT [ "/bin/bash"]
