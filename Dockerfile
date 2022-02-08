FROM ubuntu:bionic-20200921

# get the validator branch skip_session_check
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

# get the validator branch skip_session_check
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    datalad nodejs python3 python3-pip python3-setuptools && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# RUN npm install -g yarn && \
#     npm install -g bids-validator

RUN npm install -g yarn && \
   mkdir -p /home/validator && \
    cd /home/validator && \
    git clone https://github.com/bids-standard/bids-validator.git  && \
    cd /home/validator/bids-validator && \
    yarn && \
    cd bids-validator && npm install -g

COPY . /src/CuBIDS
RUN pip3 install --no-cache-dir "/src/CuBIDS"

ENTRYPOINT [ "/bin/bash"]
