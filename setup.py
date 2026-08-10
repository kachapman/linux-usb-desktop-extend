"""Setup script for USB Desktop Extend."""

from setuptools import setup, find_packages
from pathlib import Path

here = Path(__file__).parent.resolve()
long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="usb-desktop-extend",
    version="0.1.0",
    description="Turn your Android tablet into a second monitor over USB",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kachapman/linux-usb-desktop-extend",
    author="kachapman",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "PyQt6>=6.5.0",
    ],
    entry_points={
        "console_scripts": [
            "usb-desktop-extend=usb_desktop_extend.main:main",
        ],
    },
    package_data={
        "": ["assets/*.png"],
    },
    data_files=[
        ("share/applications", ["usb-desktop-extend.desktop"]),
    ],
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: System :: Hardware",
        "Topic :: Utilities",
    ],
)
