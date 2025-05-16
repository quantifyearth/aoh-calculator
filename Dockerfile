from ghcr.io/osgeo/gdal:ubuntu-small-3.11.0

RUN apt-get update -qqy && \
	apt-get install -qy \
		git \
		python3-pip \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm -rf /var/cache/apt/*

# You must install numpy before anything else otherwise
# gdal's python bindings are sad. Pandas we pull out as its slow
# to build, and this means it'll be cached
RUN rm /usr/lib/python3.*/EXTERNALLY-MANAGED
RUN pip install --upgrade pip
RUN pip install numpy
RUN pip install gdal[numpy]==3.11.0
RUN pip install pandas

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt

COPY ./ /root/aoh
WORKDIR /root/aoh

RUN pylint *.py
RUN python -m pytest ./tests

RUN chmod 755 *.py
