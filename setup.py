import os
from setuptools import setup

def read(fname):
    with open(fname) as fhandle:
        return fhandle.read()

def readMD(fname):
    # Utility function to read the README file.
    full_fname = os.path.join(os.path.dirname(__file__), fname)
    if 'PANDOC_PATH' in os.environ:
        import pandoc
        pandoc.core.PANDOC_PATH = os.environ['PANDOC_PATH']
        doc = pandoc.Document()
        with open(full_fname) as fhandle:
            doc.markdown = fhandle.read()
        return doc.rst
    else:
        return read(fname)

version = '2.0.2'
required = [req.strip() for req in read('requirements.txt').splitlines() if req.strip()]
setup(
    name='CacheMan',
    version=version,
    author='Matthew Seal',
    author_email='mseal@opengov.us',
    description='A dependent cache manager',
    long_description=readMD('README.md'),
    install_requires=required,
    license='New BSD',
    packages=['cacheman'],
    test_suite='tests',
    zip_safe=False,
    url='https://github.com/OpenGov/py_cache_manager',
    download_url='https://github.com/OpenGov/py_cache_manager/tarball/v' + version,
    keywords=['tables', 'data', 'analysis', 'extraction'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Topic :: Utilities',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Programming Language :: Python :: 2 :: Only'
    ]
)
