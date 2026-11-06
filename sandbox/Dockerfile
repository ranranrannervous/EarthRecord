# EarthRecord sandbox: a Python geospatial stack, preinstalled because the container has no network when it runs.
#   docker build -t earthrecord-sandbox:1.0 sandbox/
FROM mambaorg/micromamba:2.0.5-ubuntu24.04
USER root
RUN micromamba install -y -n base -c conda-forge python=3.12 gdal=3.10 rasterio xarray rioxarray netcdf4 h5netcdf \
      numpy pandas scipy scikit-learn scikit-image statsmodels matplotlib geopandas shapely pyproj pyogrio dask \
      pillow tqdm pyyaml jq git \
    && micromamba clean -a -y
ENV PATH=/opt/conda/bin:$PATH PROJ_DATA=/opt/conda/share/proj GDAL_DATA=/opt/conda/share/gdal
# support for Inspect's text editor tool inside the sandbox
RUN pip install --no-cache-dir inspect-tool-support && inspect-tool-support post-install || true
RUN useradd -m -u 1500 -s /bin/bash agent && mkdir -p /data /work && chown agent:agent /work
ENV HOME=/work MPLCONFIGDIR=/work/.config/matplotlib XDG_CACHE_HOME=/work/.cache
USER agent
WORKDIR /work
CMD ["tail", "-f", "/dev/null"]
