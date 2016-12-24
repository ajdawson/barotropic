# A spectral barotropic model in Python

This repository contains a package `barotropic` that conatains code for
solving the non-divergent barotropic vorticity equation using a spectral
method.


## Requirements

The `barotropic` package requires the following dependencies:

* [numpy](http://www.numpy.org/)
* [netCDF4](http://unidata.github.io/netcdf4-python/)
* [pyspharm](https://github.com/jswhit/pyspharm)

*[pyspharm is not available on 64-bit Windows, or 32-/64-bit Windows combined
with Python 3]*

The example notebook requires in addition:

* [jupyter](http://jupyter.org/)
* [iris](http://scitools.org.uk/iris/)
* [cube_browser](http://scitools.github.io/cube_browser/)


## Using the model

See the example notebook [`simple_models.ipynb`](http://nbviewer.jupyter.org/github/ajdawson/barotropic/blob/master/simple_models.ipynb).
