FROM ghcr.io/osgeo/gdal:ubuntu-small-3.13.3

RUN apt-get update -qqy && \
	apt-get install -qy \
		git \
		python3-pip \
        python3-venv \
        python3-dev \
		r-base \
		libtirpc-dev \
        make \
        g++ \
	&& rm -rf /var/lib/apt/lists/* \
	&& rm -rf /var/cache/apt/*

RUN R -e "install.packages(c('lme4', 'lmerTest'), repos='https://cran.rstudio.com/')"

ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN pip install gdal[numpy]==3.13.3

COPY ./ /root/aoh
WORKDIR /root/aoh
RUN pip install -e .[dev,validation]

RUN python3 -m pylint .
RUN python3 -m mypy .
RUN python3 -m pytest .
