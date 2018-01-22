import os
import sys
from setuptools import setup

python_2 = sys.version_info[0] == 2
def read(fname):
    with open(fname, 'rU' if python_2 else 'r') as fhandle:
        return fhandle.read()

def pandoc_read_md(fname):
    if 'PANDOC_PATH' not in os.environ:
        raise ImportError("No pandoc path to use")
    import pandoc
    pandoc.core.PANDOC_PATH = os.environ['PANDOC_PATH']
    doc = pandoc.Document()
    doc.markdown = read(fname)
    return doc.rst

def pypandoc_read_md(fname):
    import pypandoc
    os.environ.setdefault('PYPANDOC_PANDOC', os.environ['PANDOC_PATH'])
    return pypandoc.convert_text(read(fname), 'rst', format='md')

def read_md(fname):
    # Utility function to read the README file.
    full_fname = os.path.join(os.path.dirname(__file__), fname)

    try:
        return pandoc_read_md(full_fname)
    except (ImportError, AttributeError):
        try:
            return pypandoc_read_md(full_fname)
        except (ImportError, AttributeError):
            return read(fname)
    else:
        return read(fname)

version = '2.0.8'
required = [req.strip() for req in read('requirements.txt').splitlines() if req.strip()]
setup(
    name='CacheMan',
    version=version,
    author='Matthew Seal',
    author_email='mseal007@gmail.com',
    description='A dependent cache manager',
    long_description=read_md('README.md'),
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
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3'
    ]
)
