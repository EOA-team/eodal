# get OS and install development tools
FROM ubuntu:latest
RUN apt-get -y update
RUN apt-get -y install git
RUN apt -y install python3-pip
RUN apt-get install 'ffmpeg'\
    'libsm6'\ 
    'libxext6'  -y

# define working directory
WORKDIR /metadb-setup

# install AgriSatPy
# Step 1: COPY source code
COPY . .
# Step 2: run setup.py and install packages including Jupyter Lab
RUN python3 setup.py bdist_wheel
RUN pip3 install rasterio==1.3a3
RUN pip3 install jupyterlab
RUN pip3 install dist/*
RUN rm -rf dist/

# start the jupyter server
EXPOSE 8888
ENTRYPOINT ["jupyter", "lab","--ip=0.0.0.0","--allow-root"]

