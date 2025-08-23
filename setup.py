import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="creality_k1_api",
    version="0.0.1",
    author="hurricaneb",
    author_email="hurricaneb@gmail.com",
    description="A Python API for the Creality K1 3D printer",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hurricaneb/creality_k1_api",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'websockets',
    ],
)
