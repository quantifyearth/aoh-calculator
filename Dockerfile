from ghcr.io/osgeo/gdal:ubuntu-small-3.11.0

RUN apt-get update -qqy && \
	apt-get install -qy \
		git \
		python3-pip \
		r-base \
		libtirpc-dev \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm -rf /var/cache/apt/*

RUN R -e "install.packages(c('lme4', 'lmerTest'), repos='https://cran.rstudio.com/')"

# You must install numpy before anything else otherwise
# gdal's python bindings are sad. Pandas we pull out as its slow
# to build, and this means it'll be cached
RUN rm /usr/lib/python3.*/EXTERNALLY-MANAGED
RUN pip install numpy
RUN pip install gdal[numpy]==3.11.0
RUN pip install pandas

COPY ./ /root/aoh
WORKDIR /root/aoh
RUN pip install -e .[dev,validation]

RUN python3 -m pylint .
RUN python3 -m mypy .
RUN python3 -m pytest .
