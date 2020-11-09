FROM python:3

# install conda
RUN curl -sSLO https://repo.continuum.io/miniconda/Miniconda3-4.5.12-Linux-x86_64.sh && \
    bash Miniconda3-4.5.12-Linux-x86_64.sh -b -p /usr/local/miniconda && \
    rm Miniconda3-4.5.12-Linux-x86_64.sh

ENV PATH=/usr/local/miniconda/bin:$PATH

# activate conda environment
RUN echo "source activate base" > ~/.bashrc

RUN which conda

# get the validator branch skip_session_check
RUN apt-get update && \
    apt-get install -y git

# USE CONDA FOR INSTALLING NPM
RUN conda install nodejs

RUN npm --version

RUN npm install -g yarn

RUN mkdir -p /home/validator && \
    cd /home/validator && \
    git clone -b skip_session_checks --single-branch https://github.com/bids-standard/bids-validator.git


RUN ls /home/validator/bids-validator
RUN cd /home/validator/bids-validator && \
    yarn && \
    npm install -g bids-validator

RUN which bids-validator

# prepare env
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT [ "bids-validator"]
