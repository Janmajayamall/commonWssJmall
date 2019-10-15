import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="commonWsJmall",
    version="0.0.1",
    author="Janmajaya Mall",
    author_email="janmajayamall18@gmail.com",
    description="WSS connection to all exchanges",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    packages=['common_wss'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)