# bash script to install the package locally from source (without PyPi)

pip uninstall eodal -y

python setup.py bdist_wheel
pip install dist/*
rm -rf dist/
