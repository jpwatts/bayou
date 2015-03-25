from distutils.core import setup


setup(
    name="Bayou",
    version="0.0.1",
    description="An event stream server",
    author="Joel Watts",
    author_email="joel@joelwatts.com",
    url="http://github.com/jpwatts/bayou",
    packages=[
        "bayou",
    ],
    install_requires=[
        "aiohttp",
        "click",
        "simplejson",
    ],
    entry_points={
        'console_scripts': [
            "bayou = bayou.cli:main",
        ],
    }
)
