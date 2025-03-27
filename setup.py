from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = fh.read().splitlines()

setup(
    name="scrapy-toolkit",
    version="1.0.0",
    author="Scrapy Contributors",
    author_email="author@example.com",
    description="A comprehensive toolkit for web scraping and data extraction",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/scrapy",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        'viz': [
            'matplotlib>=3.5.1',
            'seaborn>=0.11.2',
            'plotly>=5.6.0',
            'wordcloud>=1.8.1',
            'networkx>=2.7.1'
        ],
        'api': [
            'flask>=2.0.2',
            'fastapi>=0.73.0',
            'uvicorn>=0.17.4',
            'pyjwt>=2.3.0'
        ],
        'distributed': [
            'celery>=5.2.3',
            'dask>=2022.2.0',
            'distributed>=2022.2.0',
            'ray>=1.11.0'
        ],
        'ai': [
            'tensorflow>=2.8.0',
            'transformers>=4.16.2',
            'scikit-learn>=1.0.2'
        ],
        'dev': [
            'pytest>=7.0.0',
            'pytest-cov>=3.0.0',
            'mock>=5.0.0',
            'flake8>=4.0.1',
            'black>=22.1.0',
            'mypy>=0.931',
            'isort>=5.10.1',
            'pre-commit>=2.17.0',
            'tox>=3.24.5',
            'sphinx>=4.4.0',
            'sphinx-rtd-theme>=1.0.0'
        ],
        'all': [
            'matplotlib>=3.5.1',
            'seaborn>=0.11.2',
            'plotly>=5.6.0',
            'wordcloud>=1.8.1',
            'networkx>=2.7.1',
            'flask>=2.0.2',
            'fastapi>=0.73.0',
            'uvicorn>=0.17.4',
            'pyjwt>=2.3.0',
            'celery>=5.2.3',
            'dask>=2022.2.0',
            'distributed>=2022.2.0',
            'tensorflow>=2.8.0',
            'transformers>=4.16.2',
            'scikit-learn>=1.0.2'
        ]
    },
    entry_points={
        'console_scripts': [
            'scrapy-toolkit=cli.scrapy_cli:main',
        ],
    },
    include_package_data=True,
    package_data={
        'scraping_project': ['data/*.json', 'data/*.yaml'],
    },
)
