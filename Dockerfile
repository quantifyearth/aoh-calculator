from  ghcr.io/osgeo/gdal:ubuntu-small-3.8.1

RUN apt-get update -qqy && \
	apt-get install -qy \
		git \
		python3-pip \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm -rf /var/cache/apt/*

# You must install numpy before anything else otherwise
# gdal's python bindings are sad. Pandas we pull out as its slow
# to build, and this means it'll be cached
RUN pip install --upgrade pip
RUN pip install numpy
RUN pip install gdal[numpy]==3.8.1
RUN pip install pandas

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

COPY ./ /root/
WORKDIR /root/

RUN pylint *.py

RUN chmod 755 *.py
