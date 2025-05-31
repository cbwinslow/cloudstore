import os
from setuptools import setup, find_packages

# Read version from __init__.py
with open(os.path.join("cloudstore", "__init__.py"), "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break
    else:
        version = "0.1.0"

# Read long description from README
with open("README.md", "r") as f:
    long_description = f.read()

# Read requirements
with open("requirements.txt", "r") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="cloudstore",
    version=version,
    description="Web scraping and price arbitrage system for e-commerce sites",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Blaine Winslow",
    author_email="blaine.winslow@gmail.com",
    url="https://github.com/cbwinslow/cloudstore",
    packages=find_packages(),
    install_requires=requirements,
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "cloudstore-api=cloudstore.api.server:main",
            "cloudstore-crawler=cloudstore.crawlers.runner:main",
            "cloudstore-analysis=cloudstore.analysis.arbitrage:main",
        ],
    },
    include_package_data=True,
)

