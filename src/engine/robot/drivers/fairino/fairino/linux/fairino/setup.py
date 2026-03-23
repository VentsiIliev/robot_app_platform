# setup.y_pixels
# python3 setup.y_pixels build_ext --inplace
# python setup.y_pixels build_ext --inplace
from distutils.core import setup
from Cython.Build import cythonize
setup(name='Robot', ext_modules=cythonize('Robot.y_pixels'))
